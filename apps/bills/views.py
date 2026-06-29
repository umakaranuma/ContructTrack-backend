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
    site_ids = Site.objects.filter(tenant=tenant, is_active=True).values_list('id', flat=True)

    bills_qs = Bill.objects.filter(site_id__in=site_ids)
    if month_str:
        try:
            year, month = month_str.split('-')
            bills_qs = bills_qs.filter(log_date__year=int(year), log_date__month=int(month))
        except (ValueError, AttributeError):
            return error_response('month must be in YYYY-MM format.', {}, 400)

    total_materials = bills_qs.aggregate(total=Sum('total_amount_lkr'))['total'] or 0

    from apps.attendance.models import DailyAttendance
    wages_qs = DailyAttendance.objects.filter(site_id__in=site_ids)
    if month_str:
        try:
            wages_qs = wages_qs.filter(log_date__year=int(year), log_date__month=int(month))
        except Exception:
            pass
    total_wages = wages_qs.aggregate(total=Sum('total_earned_lkr'))['total'] or 0

    return success_response('Finance summary.', {
        'month': month_str,
        'total_material_spend_lkr': float(total_materials),
        'total_wage_spend_lkr': float(total_wages),
        'total_spend_lkr': float(total_materials) + float(total_wages),
    })


@api_view(['GET'])
@permission_classes([IsOwner])
def finance_bills(request):
    """GET /api/finances/bills/ — paginated bill ledger for the owner."""
    tenant, err = _get_tenant_or_error(request.user)
    if err:
        return err

    site_ids = Site.objects.filter(tenant=tenant).values_list('id', flat=True)
    bills = Bill.objects.filter(site_id__in=site_ids).select_related('site', 'logged_by')

    material = request.query_params.get('material')
    if material:
        bills = bills.filter(material_type=material)

    site_id = request.query_params.get('site_id')
    if site_id:
        bills = bills.filter(site_id=site_id)

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
def finance_wages(request):
    """GET /api/finances/wages/ — daily wage summary."""
    tenant, err = _get_tenant_or_error(request.user)
    if err:
        return err

    from apps.attendance.models import AttendanceSummary
    from apps.attendance.serializers import AttendanceSummarySerializer

    site_ids = Site.objects.filter(tenant=tenant).values_list('id', flat=True)
    summaries = AttendanceSummary.objects.filter(site_id__in=site_ids).order_by('-log_date')

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
def finance_by_site(request):
    """GET /api/finances/by-site/ — per-site spend breakdown."""
    tenant, err = _get_tenant_or_error(request.user)
    if err:
        return err

    sites = Site.objects.filter(tenant=tenant, is_active=True)
    result = []
    for site in sites:
        mat = Bill.objects.filter(site=site).aggregate(t=Sum('total_amount_lkr'))['t'] or 0
        from apps.attendance.models import DailyAttendance
        wag = DailyAttendance.objects.filter(site=site).aggregate(t=Sum('total_earned_lkr'))['t'] or 0
        result.append({
            'site_id': str(site.id),
            'site_name': site.name,
            'material_spend_lkr': float(mat),
            'wage_spend_lkr': float(wag),
            'total_lkr': float(mat) + float(wag),
        })
    return success_response('Spend by site.', result)
