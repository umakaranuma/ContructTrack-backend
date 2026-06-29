"""
Finance / bill views.
Finances endpoint aggregates spend data across bills and wages.
"""
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from rest_framework.decorators import api_view, permission_classes

from apps.core.utils import success_response, error_response
from apps.core.permissions import IsOwner
from apps.tenants.models import Tenant
from apps.sites.models import Site
from .models import Bill
from .serializers import BillSerializer


def _get_tenant_or_error(user):
    tenant = Tenant.objects.filter(owner=user).first()
    if not tenant:
        return None, error_response('Tenant not found.', {}, 404)
    return tenant, None


def _parse_month(month_str):
    """Return (year, month) ints from YYYY-MM or None if invalid/empty."""
    if not month_str:
        return None
    try:
        year, month = month_str.split('-')
        return int(year), int(month)
    except (ValueError, AttributeError):
        return None


def _tenant_site_ids(tenant, site_id=None):
    qs = Site.objects.filter(tenant=tenant)
    if site_id:
        qs = qs.filter(id=site_id)
    return qs.values_list('id', flat=True)


@api_view(['GET'])
@permission_classes([IsOwner])
def finance_summary(request):
    """
    GET /api/finances/summary/?month=2025-06
    Returns total spend breakdown (materials + wages) for the requested month.
    """
    tenant, err = _get_tenant_or_error(request.user)
    if err:
        return err

    month_str = request.query_params.get('month', '')
    site_id = request.query_params.get('site_id')
    site_ids = _tenant_site_ids(tenant, site_id)
    if site_id and not site_ids:
        return error_response('Site not found.', {}, 404)

    bills_qs = Bill.objects.filter(site_id__in=site_ids)
    parsed = _parse_month(month_str)
    if month_str and not parsed:
        return error_response('month must be in YYYY-MM format.', {}, 400)
    if parsed:
        year, month = parsed
        bills_qs = bills_qs.filter(log_date__year=year, log_date__month=month)

    total_materials = bills_qs.aggregate(total=Sum('total_amount_lkr'))['total'] or 0

    from apps.attendance.models import DailyAttendance
    wages_qs = DailyAttendance.objects.filter(site_id__in=site_ids)
    if parsed:
        wages_qs = wages_qs.filter(log_date__year=year, log_date__month=month)
    total_wages = wages_qs.aggregate(total=Sum('total_earned_lkr'))['total'] or 0

    # Prev-month comparison for change indicators
    if parsed:
        y, m = parsed
        prev_y, prev_m = (y - 1, 12) if m == 1 else (y, m - 1)
        prev_mat = Bill.objects.filter(
            site_id__in=site_ids, log_date__year=prev_y, log_date__month=prev_m
        ).aggregate(t=Sum('total_amount_lkr'))['t'] or 0
        from apps.attendance.models import DailyAttendance as _DA
        prev_wag = _DA.objects.filter(
            site_id__in=site_ids, log_date__year=prev_y, log_date__month=prev_m
        ).aggregate(t=Sum('total_earned_lkr'))['t'] or 0
    else:
        prev_mat, prev_wag = 0, 0

    def _pct_change(current, prev):
        if not prev:
            return '+0%'
        diff = ((float(current) - float(prev)) / float(prev)) * 100
        return f"{'+' if diff >= 0 else ''}{diff:.0f}%"

    prev_total = float(prev_mat) + float(prev_wag)
    total_mat  = float(total_materials)
    total_wag  = float(total_wages)

    active_sites = Site.objects.filter(
        tenant=tenant, is_active=True, id__in=site_ids
    ).count() if site_id else Site.objects.filter(tenant=tenant, is_active=True).count()

    return success_response('Finance summary.', {
        'month':                 month_str,
        # Field names match the frontend Finances.jsx component expectations
        'total_material_spend':  total_mat,
        'total_wage_payout':     total_wag,
        'total_site_spend':      total_mat + total_wag,
        'active_sites':          active_sites,
        'vs_prev_material':      _pct_change(total_mat, prev_mat),
        'vs_prev_wages':         _pct_change(total_wag, prev_wag),
        'vs_prev_total':         _pct_change(total_mat + total_wag, prev_total),
        # Also keep lkr-suffixed names for backward compatibility
        'total_material_spend_lkr': total_mat,
        'total_wage_spend_lkr':     total_wag,
        'total_spend_lkr':          total_mat + total_wag,
    })


@api_view(['GET'])
@permission_classes([IsOwner])
def finance_bills(request):
    """GET /api/finances/bills/ — paginated bill ledger for the owner."""
    tenant, err = _get_tenant_or_error(request.user)
    if err:
        return err

    site_ids = _tenant_site_ids(tenant, request.query_params.get('site_id'))
    if request.query_params.get('site_id') and not site_ids:
        return error_response('Site not found.', {}, 404)

    bills = Bill.objects.filter(site_id__in=site_ids).select_related('site', 'logged_by')

    material = request.query_params.get('material')
    if material:
        bills = bills.filter(material_type=material)

    month_str = request.query_params.get('month', '')
    parsed = _parse_month(month_str)
    if month_str and not parsed:
        return error_response('month must be in YYYY-MM format.', {}, 400)
    if parsed:
        year, month = parsed
        bills = bills.filter(log_date__year=year, log_date__month=month)

    from apps.core.utils import paginate_queryset
    page = int(request.query_params.get('page', 1))
    limit = int(request.query_params.get('limit', 20))
    paged, total, pages = paginate_queryset(bills, page, limit)
    return success_response('Bills retrieved.', {
        'results': BillSerializer(paged, many=True).data,
        'total': total, 'page': page, 'total_pages': pages,
    })


@api_view(['GET'])
@permission_classes([IsOwner])
def finance_bill_detail(request, bill_id):
    """GET /api/finances/bills/:id/ — single bill record for detail view."""
    tenant, err = _get_tenant_or_error(request.user)
    if err:
        return err

    site_ids = _tenant_site_ids(tenant)
    try:
        bill = Bill.objects.select_related('site', 'logged_by').get(
            id=bill_id, site_id__in=site_ids
        )
    except Bill.DoesNotExist:
        return error_response('Bill not found.', {}, 404)

    return success_response('Bill retrieved.', BillSerializer(bill).data)


@api_view(['GET'])
@permission_classes([IsOwner])
def finance_wages(request):
    """GET /api/finances/wages/ — daily wage summary."""
    tenant, err = _get_tenant_or_error(request.user)
    if err:
        return err

    from apps.attendance.models import AttendanceSummary
    from apps.attendance.serializers import AttendanceSummarySerializer

    site_ids = _tenant_site_ids(tenant, request.query_params.get('site_id'))
    if request.query_params.get('site_id') and not site_ids:
        return error_response('Site not found.', {}, 404)

    summaries = AttendanceSummary.objects.filter(site_id__in=site_ids).order_by('-log_date')

    month_str = request.query_params.get('month', '')
    parsed = _parse_month(month_str)
    if month_str and not parsed:
        return error_response('month must be in YYYY-MM format.', {}, 400)
    if parsed:
        year, month = parsed
        summaries = summaries.filter(log_date__year=year, log_date__month=month)

    from apps.core.utils import paginate_queryset
    page = int(request.query_params.get('page', 1))
    limit = int(request.query_params.get('limit', 30))
    paged, total, pages = paginate_queryset(summaries, page, limit)
    return success_response('Wage summaries.', {
        'results': AttendanceSummarySerializer(paged, many=True).data,
        'total': total, 'page': page, 'total_pages': pages,
    })


@api_view(['GET'])
@permission_classes([IsOwner])
def finance_wage_detail(request, summary_id):
    """GET /api/finances/wages/:id/ — single wage summary for detail view."""
    tenant, err = _get_tenant_or_error(request.user)
    if err:
        return err

    from apps.attendance.models import AttendanceSummary, DailyAttendance
    from apps.attendance.serializers import AttendanceSummarySerializer, DailyAttendanceSerializer

    site_ids = _tenant_site_ids(tenant)
    try:
        summary = AttendanceSummary.objects.select_related('site').get(
            id=summary_id, site_id__in=site_ids
        )
    except AttendanceSummary.DoesNotExist:
        return error_response('Wage summary not found.', {}, 404)

    workers = DailyAttendance.objects.filter(
        site=summary.site, log_date=summary.log_date
    ).select_related('worker')

    return success_response('Wage summary retrieved.', {
        'summary': AttendanceSummarySerializer(summary).data,
        'workers': DailyAttendanceSerializer(workers, many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsOwner])
def finance_by_site(request):
    """GET /api/finances/by-site/ — per-site spend breakdown."""
    tenant, err = _get_tenant_or_error(request.user)
    if err:
        return err

    site_id = request.query_params.get('site_id')
    sites = Site.objects.filter(tenant=tenant, is_active=True)
    if site_id:
        sites = sites.filter(id=site_id)
        if not sites.exists():
            return error_response('Site not found.', {}, 404)

    month_str = request.query_params.get('month', '')
    parsed = _parse_month(month_str)
    if month_str and not parsed:
        return error_response('month must be in YYYY-MM format.', {}, 400)

    from apps.attendance.models import DailyAttendance

    result = []
    for site in sites:
        bills_qs = Bill.objects.filter(site=site)
        wages_qs = DailyAttendance.objects.filter(site=site)
        if parsed:
            year, month = parsed
            bills_qs = bills_qs.filter(log_date__year=year, log_date__month=month)
            wages_qs = wages_qs.filter(log_date__year=year, log_date__month=month)
        mat = bills_qs.aggregate(t=Sum('total_amount_lkr'))['t'] or 0
        wag = wages_qs.aggregate(t=Sum('total_earned_lkr'))['t'] or 0
        result.append({
            'site_id': str(site.id),
            'site_name': site.name,
            'material_spend_lkr': float(mat),
            'wage_spend_lkr': float(wag),
            'total_lkr': float(mat) + float(wag),
        })
    return success_response('Spend by site.', result)
