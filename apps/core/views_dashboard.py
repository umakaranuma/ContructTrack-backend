"""
Dashboard overview views — owner-facing summary data.
These are the primary data sources for the Overview page of the owner dashboard.
"""
from django.utils import timezone
from django.db.models import Sum, Q
from rest_framework.decorators import api_view, permission_classes

from apps.core.utils import success_response, error_response
from apps.core.permissions import IsOwner
from apps.tenants.models import Tenant
from apps.sites.models import Site, Alert


def _get_tenant(user):
    return Tenant.objects.filter(owner=user).select_related('package').first()


@api_view(['GET'])
@permission_classes([IsOwner])
def overview_stats(request):
    """
    GET /api/dashboard/overview/
    Returns the four KPI cards for the owner dashboard:
      active_sites, max_sites, total_spend_month, workers_on_site,
      open_alerts, spend_vs_last_month, spend_up.
    """
    tenant = _get_tenant(request.user)
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    now = timezone.now()
    site_ids = Site.objects.filter(tenant=tenant, is_active=True).values_list('id', flat=True)

    # Active site count
    active_sites = len(site_ids)
    max_sites = tenant.package.max_sites if tenant.package else 0

    # Total material spend this month
    from apps.bills.models import Bill
    this_month_spend = (
        Bill.objects.filter(
            site_id__in=site_ids,
            log_date__year=now.year,
            log_date__month=now.month,
        ).aggregate(t=Sum('total_amount_lkr'))['t'] or 0
    )

    # Workers on site today — count distinct workers marked present or half-day
    from apps.attendance.models import DailyAttendance
    workers_today = DailyAttendance.objects.filter(
        site_id__in=site_ids,
        log_date=now.date(),
        status__in=['present', 'half'],
    ).count()

    # Open (unresolved) alerts across all sites
    open_alerts = Alert.objects.filter(
        site_id__in=site_ids, is_resolved=False
    ).count()

    # Spend last month for comparison
    if now.month == 1:
        last_year, last_month = now.year - 1, 12
    else:
        last_year, last_month = now.year, now.month - 1

    last_month_spend = (
        Bill.objects.filter(
            site_id__in=site_ids,
            log_date__year=last_year,
            log_date__month=last_month,
        ).aggregate(t=Sum('total_amount_lkr'))['t'] or 0
    )

    if last_month_spend > 0:
        diff_pct = ((float(this_month_spend) - float(last_month_spend)) / float(last_month_spend)) * 100
        spend_vs_last = f"{'+' if diff_pct >= 0 else ''}{diff_pct:.1f}%"
        spend_up = diff_pct >= 0
    else:
        spend_vs_last = '+0.0%'
        spend_up = True

    return success_response('Overview stats retrieved.', {
        'active_sites':        active_sites,
        'max_sites':           max_sites,
        'total_spend_month':   float(this_month_spend),
        'workers_on_site':     workers_today,
        'open_alerts':         open_alerts,
        'spend_vs_last_month': spend_vs_last,
        'spend_up':            spend_up,
    })


@api_view(['GET'])
@permission_classes([IsOwner])
def activity_feed(request):
    """
    GET /api/dashboard/activity/?limit=20
    Returns a unified timeline of recent events from bills, progress logs,
    and attendance across all tenant sites, sorted newest first.
    """
    tenant = _get_tenant(request.user)
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    limit = int(request.query_params.get('limit', 20))
    site_ids = list(Site.objects.filter(tenant=tenant, is_active=True).values_list('id', flat=True))
    site_names = {
        str(s.id): s.name
        for s in Site.objects.filter(id__in=site_ids).only('id', 'name')
    }

    events = []

    # Bill uploads
    from apps.bills.models import Bill
    for bill in Bill.objects.filter(site_id__in=site_ids).order_by('-created_at')[:limit]:
        events.append({
            'id':       f'bill-{bill.id}',
            'severity': 'green',
            'site':     site_names.get(str(bill.site_id), ''),
            'message':  f'New bill uploaded: {bill.material_type} — LKR {bill.total_amount_lkr:,.0f}',
            'ts':       bill.created_at.isoformat(),
        })

    # Progress logs
    from apps.progress.models import ProgressLog
    for log in ProgressLog.objects.filter(site_id__in=site_ids).order_by('-log_date')[:limit]:
        by = log.logged_by.full_name if log.logged_by else 'Manager'
        events.append({
            'id':       f'log-{log.id}',
            'severity': 'green',
            'site':     site_names.get(str(log.site_id), ''),
            'message':  f'Daily log submitted by {by}',
            'ts':       log.created_at.isoformat(),
        })

    # Open alerts
    _danger_types = {'material_cap', 'anomaly'}
    for alert in Alert.objects.filter(site_id__in=site_ids, is_resolved=False).order_by('-created_at')[:limit]:
        events.append({
            'id':       f'alert-{alert.id}',
            'severity': 'red' if alert.alert_type in _danger_types else 'amber',
            'site':     site_names.get(str(alert.site_id), ''),
            'message':  alert.message,
            'ts':       alert.created_at.isoformat(),
        })

    # Sort all events newest first and trim to limit
    events.sort(key=lambda e: e['ts'], reverse=True)

    return success_response('Activity feed retrieved.', events[:limit])


@api_view(['GET'])
@permission_classes([IsOwner])
def all_alerts(request):
    """
    GET /api/dashboard/alerts/
    Returns all unresolved alerts across all tenant sites for the alert drawer.
    """
    tenant = _get_tenant(request.user)
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    from apps.sites.serializers import AlertSerializer
    site_ids = Site.objects.filter(tenant=tenant, is_active=True).values_list('id', flat=True)
    alerts = Alert.objects.filter(
        site_id__in=site_ids, is_resolved=False
    ).select_related('site').order_by('-created_at')

    return success_response('Alerts retrieved.', AlertSerializer(alerts, many=True).data)
