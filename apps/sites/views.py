"""
Site management views.
All queries are filtered by tenant — a manager can only see sites they are assigned to;
an owner sees all sites belonging to their tenant.
"""
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.core.utils import success_response, error_response, paginate_queryset
from apps.core.permissions import IsOwner, IsOwnerOrManager
from apps.tenants.models import Tenant
from .models import Site, SiteManager, Alert
from .serializers import SiteSerializer, SiteCreateSerializer, AlertSerializer


def _get_tenant(user):
    """Helper: owners look up via owned_tenants; managers via site assignments."""
    if user.user_type == 'owner':
        return Tenant.objects.filter(owner=user).first()
    return None  # managers don't have a direct tenant FK


def _get_sites_for_user(user):
    """Returns queryset of sites visible to the authenticated user."""
    if user.user_type == 'owner':
        tenant = _get_tenant(user)
        if not tenant:
            return Site.objects.none()
        return Site.objects.filter(tenant=tenant, is_active=True)
    elif user.user_type == 'manager':
        # Manager only sees sites they are actively assigned to
        assigned = SiteManager.objects.filter(manager=user, is_active=True).values_list('site_id', flat=True)
        return Site.objects.filter(id__in=assigned, is_active=True)
    return Site.objects.none()


@api_view(['GET', 'POST'])
@permission_classes([IsOwnerOrManager])
def site_list_create(request):
    if request.method == 'GET':
        sites = _get_sites_for_user(request.user)

        search = request.query_params.get('search', '').strip()
        if search:
            sites = sites.filter(
                Q(name__icontains=search) | Q(address__icontains=search)
            )

        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 20))
        paged, total, pages = paginate_queryset(sites, page, limit)
        return success_response('Sites retrieved.', {
            'results': SiteSerializer(paged, many=True).data,
            'total': total,
            'page': page,
            'total_pages': pages,
        })

    # POST — only owners can create sites
    if request.user.user_type != 'owner':
        return error_response('Only owners can create sites.', {}, 403)

    tenant = _get_tenant(request.user)
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    # Enforce package site limit
    current_count = Site.objects.filter(tenant=tenant, is_active=True).count()
    if tenant.package and current_count >= tenant.package.max_sites:
        return error_response(
            f'Your {tenant.package.name} plan allows max {tenant.package.max_sites} active sites. '
            'Please upgrade or deactivate an existing site.',
            {}, 403
        )

    serializer = SiteCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)

    site = serializer.save(tenant=tenant)
    return success_response('Site created.', SiteSerializer(site).data, 201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsOwnerOrManager])
def site_detail(request, site_id):
    try:
        site = _get_sites_for_user(request.user).get(id=site_id)
    except Site.DoesNotExist:
        return error_response('Site not found.', {}, 404)

    if request.method == 'GET':
        return success_response('Site retrieved.', SiteSerializer(site).data)

    if request.user.user_type != 'owner':
        return error_response('Only owners can modify sites.', {}, 403)

    if request.method == 'PATCH':
        serializer = SiteCreateSerializer(site, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response('Validation failed.', serializer.errors, 422)
        site = serializer.save()
        return success_response('Site updated.', SiteSerializer(site).data)

    if request.method == 'DELETE':
        site.is_active = False
        site.save(update_fields=['is_active'])
        return success_response('Site deactivated.')


def _get_site_for_user_or_none(user, site_id):
    try:
        return _get_sites_for_user(user).get(id=site_id)
    except Site.DoesNotExist:
        return None


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def site_financials(request, site_id):
    """
    GET /api/sites/:id/financials/
    Real chart data for the SiteDetail overview:
      - budget_vs_actual: last 6 months of (monthly budget share, actual spend)
      - material_breakdown: total spend per material type (all-time for this site)
    """
    site = _get_site_for_user_or_none(request.user, site_id)
    if not site:
        return error_response('Site not found.', {}, 404)

    from datetime import date
    from django.db.models import Sum
    from apps.bills.models import Bill
    from apps.attendance.models import DailyAttendance

    today = timezone.now().date()

    # Monthly budget share: total budget spread across the planned project months.
    monthly_budget = 0.0
    if site.budget_lkr:
        if site.start_date and site.end_date and site.end_date > site.start_date:
            months_span = max(
                (site.end_date.year - site.start_date.year) * 12
                + (site.end_date.month - site.start_date.month) + 1,
                1,
            )
        else:
            months_span = 12
        monthly_budget = float(site.budget_lkr) / months_span

    budget_vs_actual = []
    for i in range(5, -1, -1):
        # walk back i months from the current month
        y, m = today.year, today.month - i
        while m <= 0:
            m += 12
            y -= 1
        mat = Bill.objects.filter(
            site=site, log_date__year=y, log_date__month=m,
        ).aggregate(t=Sum('total_amount_lkr'))['t'] or 0
        wag = DailyAttendance.objects.filter(
            site=site, log_date__year=y, log_date__month=m,
        ).aggregate(t=Sum('total_earned_lkr'))['t'] or 0
        budget_vs_actual.append({
            'month':  date(y, m, 1).strftime('%b'),
            'budget': round(monthly_budget, 2),
            'actual': float(mat) + float(wag),
        })

    material_rows = (
        Bill.objects.filter(site=site)
        .values('material_type')
        .annotate(total=Sum('total_amount_lkr'))
        .order_by('-total')
    )
    material_breakdown = [
        {
            'name':  dict(Bill._meta.get_field('material_type').choices).get(
                r['material_type'], r['material_type'],
            ),
            'value': float(r['total'] or 0),
        }
        for r in material_rows
    ]

    total_material = float(
        Bill.objects.filter(site=site).aggregate(t=Sum('total_amount_lkr'))['t'] or 0
    )
    total_labour = float(
        DailyAttendance.objects.filter(site=site).aggregate(t=Sum('total_earned_lkr'))['t'] or 0
    )
    total_spend = total_material + total_labour

    return success_response('Site financials.', {
        'budget_vs_actual':   budget_vs_actual,
        'material_breakdown': material_breakdown,
        'monthly_budget_lkr': round(monthly_budget, 2),
        'totals': {
            'material_lkr':  total_material,
            'labour_lkr':    total_labour,
            'total_spend_lkr': total_spend,
            'budget_lkr':    float(site.budget_lkr) if site.budget_lkr else 0,
            'material_pct':  round(total_material / total_spend * 100) if total_spend > 0 else 0,
            'labour_pct':    round(total_labour / total_spend * 100) if total_spend > 0 else 0,
        },
    })


def _fetch_site_progress_logs(site, limit=50, log_date=None):
    from apps.progress.models import ProgressLog
    from apps.progress.serializers import SiteDailyLogSerializer

    qs = ProgressLog.objects.filter(site=site).select_related('logged_by').order_by('-log_date')
    if log_date:
        qs = qs.filter(log_date=log_date)
    logs = list(qs[:limit])
    if not logs:
        return []
    return SiteDailyLogSerializer(logs, many=True).data


def _fetch_site_progress_photos(site):
    from apps.progress.models import ProgressPhoto
    from apps.progress.serializers import ProgressPhotoSerializer

    photos = ProgressPhoto.objects.filter(progress_log__site=site).select_related('progress_log').order_by('-taken_at')
    return ProgressPhotoSerializer(photos, many=True).data


def _fetch_site_worker_roster(site):
    """Aggregate per-worker attendance stats for the owner-dashboard table."""
    from django.db.models import Sum
    from apps.attendance.models import Worker, DailyAttendance

    roster = []
    for worker in Worker.objects.filter(site=site, is_active=True).order_by('full_name'):
        records = DailyAttendance.objects.filter(worker=worker)
        present = records.filter(status='present').count()
        half = records.filter(status='half').count()
        days = present + half * 0.5
        earned = records.aggregate(t=Sum('total_earned_lkr'))['t'] or 0
        paid = records.filter(is_paid=True).aggregate(t=Sum('total_earned_lkr'))['t'] or 0
        roster.append({
            'id': str(worker.id),
            'name': worker.full_name,
            'role': worker.role,
            'days': days,
            'total_earned': float(earned),
            'total_paid': float(paid),
        })
    return roster


def _submit_site_attendance(user, site, data):
    """Shared bulk attendance submit used by mobile and owner-dashboard."""
    from django.db import transaction
    from django.db.models import Sum
    from apps.attendance.models import Worker, DailyAttendance, AttendanceSummary

    log_date = data.get('log_date')
    is_rain_day = data.get('is_rain_day', False)
    records = data.get('records', [])

    if not log_date:
        return None, error_response('log_date is required.', {}, 400)
    if not records:
        return None, error_response('records list cannot be empty.', {}, 400)

    created_count = 0
    errors = []

    with transaction.atomic():
        for rec in records:
            worker_id = rec.get('worker_id')
            try:
                worker = Worker.objects.get(id=worker_id, site=site)
            except Worker.DoesNotExist:
                errors.append(f'Worker {worker_id} not found.')
                continue

            from apps.attendance.services import resolve_attendance_rate
            rate_lkr = resolve_attendance_rate(worker, rec)

            _, created = DailyAttendance.objects.update_or_create(
                site=site,
                worker=worker,
                log_date=log_date,
                defaults={
                    'status': rec.get('status', 'present'),
                    'overtime_hours': rec.get('overtime_hours', 0),
                    'daily_rate_lkr': rate_lkr,
                    'logged_by': user,
                    'is_rain_day': is_rain_day,
                    'is_synced': True,
                },
            )
            if created:
                created_count += 1

        day_records = DailyAttendance.objects.filter(site=site, log_date=log_date)
        total_wage = day_records.aggregate(t=Sum('total_earned_lkr'))['t'] or 0
        p = day_records.filter(status='present').count()
        h = day_records.filter(status='half').count()
        a = day_records.filter(status='absent').count()

        AttendanceSummary.objects.update_or_create(
            site=site, log_date=log_date,
            defaults={
                'total_present': p, 'total_half': h, 'total_absent': a,
                'total_wage_lkr': total_wage,
                'submitted_by': user,
            },
        )

    return {
        'log_date': log_date,
        'created': created_count,
        'errors': errors,
    }, None


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def site_logs(request, site_id):
    """GET /api/sites/:id/logs/ — combined timeline: bills + progress + attendance."""
    site = _get_site_for_user_or_none(request.user, site_id)
    if not site:
        return error_response('Site not found.', {}, 404)

    data = _fetch_site_progress_logs(site)
    return success_response('Logs retrieved.', data)


@api_view(['GET', 'POST'])
@permission_classes([IsOwnerOrManager])
def site_daily_logs(request, site_id):
    """GET/POST /api/sites/:id/daily-logs/ — owner-dashboard daily log table."""
    site = _get_site_for_user_or_none(request.user, site_id)
    if not site:
        return error_response('Site not found.', {}, 404)

    if request.method == 'GET':
        log_date = request.query_params.get('date', '').strip() or None
        data = _fetch_site_progress_logs(site, log_date=log_date)
        return success_response('Logs retrieved.', {
            'results': data,
            'total': len(data),
        })

    from apps.progress.serializers import ProgressLogCreateSerializer
    from apps.progress.services import upsert_progress_log, serialize_site_daily_log

    serializer = ProgressLogCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)

    log, created = upsert_progress_log(site, request.user, serializer.validated_data)
    message = 'Daily log created.' if created else 'Daily log updated for this date.'
    return success_response(message, serialize_site_daily_log(site, log), 201 if created else 200)


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def site_daily_log_detail(request, site_id, log_id):
    """GET /api/sites/:id/daily-logs/:logId/ — full day view with attendance, bills, photos."""
    site = _get_site_for_user_or_none(request.user, site_id)
    if not site:
        return error_response('Site not found.', {}, 404)

    from apps.progress.models import ProgressLog
    from apps.progress.services import fetch_daily_log_detail

    try:
        log = ProgressLog.objects.select_related('logged_by').get(id=log_id, site=site)
    except ProgressLog.DoesNotExist:
        return error_response('Daily log not found.', {}, 404)

    return success_response('Daily log retrieved.', fetch_daily_log_detail(site, log))


@api_view(['GET', 'POST'])
@permission_classes([IsOwnerOrManager])
def site_workers(request, site_id):
    """GET/POST /api/sites/:id/workers/ — site labour roster."""
    try:
        site = _get_sites_for_user(request.user).get(id=site_id)
    except Site.DoesNotExist:
        return error_response('Site not found.', {}, 404)

    from apps.attendance.models import Worker
    from apps.attendance.serializers import WorkerSerializer, WorkerCreateSerializer

    if request.method == 'POST':
        serializer = WorkerCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('Validation failed.', serializer.errors, 422)
        worker = serializer.save(site=site)
        return success_response('Worker added.', WorkerSerializer(worker).data, 201)

    workers = Worker.objects.filter(site=site, is_active=True)
    return success_response('Workers retrieved.', WorkerSerializer(workers, many=True).data)


@api_view(['GET', 'POST'])
@permission_classes([IsOwnerOrManager])
def site_bills(request, site_id):
    """GET/POST /api/sites/:id/bills/"""
    try:
        site = _get_sites_for_user(request.user).get(id=site_id)
    except Site.DoesNotExist:
        return error_response('Site not found.', {}, 404)

    from apps.bills.models import Bill
    from apps.bills.serializers import SiteBillGridSerializer, BillCreateSerializer

    if request.method == 'POST':
        serializer = BillCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('Validation failed.', serializer.errors, 422)
        bill = serializer.save(site=site, logged_by=request.user)
        return success_response('Bill logged.', SiteBillGridSerializer(bill).data, 201)

    bills = Bill.objects.filter(site=site).order_by('-log_date')
    page = int(request.query_params.get('page', 1))
    limit = int(request.query_params.get('limit', 20))
    paged, total, pages = paginate_queryset(bills, page, limit)
    return success_response('Bills retrieved.', {
        'results': SiteBillGridSerializer(paged, many=True).data,
        'total': total, 'page': page, 'total_pages': pages,
    })


@api_view(['GET', 'POST'])
@permission_classes([IsOwnerOrManager])
def site_attendance(request, site_id):
    """GET/POST /api/sites/:id/attendance/"""
    try:
        site = _get_sites_for_user(request.user).get(id=site_id)
    except Site.DoesNotExist:
        return error_response('Site not found.', {}, 404)

    if request.method == 'POST':
        result, err = _submit_site_attendance(request.user, site, request.data)
        if err:
            return err
        return success_response('Attendance submitted.', result, 201)

    roster = _fetch_site_worker_roster(site)
    return success_response('Attendance retrieved.', {
        'results': roster,
        'total': len(roster),
    })


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def site_progress_photos(request, site_id):
    """GET /api/sites/:id/progress-photos/"""
    site = _get_site_for_user_or_none(request.user, site_id)
    if not site:
        return error_response('Site not found.', {}, 404)

    return success_response('Photos retrieved.', _fetch_site_progress_photos(site))


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def site_alerts(request, site_id):
    """GET /api/sites/:id/alerts/"""
    try:
        site = _get_sites_for_user(request.user).get(id=site_id)
    except Site.DoesNotExist:
        return error_response('Site not found.', {}, 404)

    alerts = Alert.objects.filter(site=site, is_resolved=False).order_by('-created_at')
    return success_response('Alerts retrieved.', AlertSerializer(alerts, many=True).data)


@api_view(['POST'])
@permission_classes([IsOwnerOrManager])
def alert_acknowledge(request, site_id, alert_id):
    """
    POST /api/sites/:id/alerts/:alertId/acknowledge/
    Marks the alert as resolved (model has no separate acknowledged state).
    """
    try:
        site = _get_sites_for_user(request.user).get(id=site_id)
    except Site.DoesNotExist:
        return error_response('Site not found.', {}, 404)

    try:
        alert = Alert.objects.get(id=alert_id, site=site)
    except Alert.DoesNotExist:
        return error_response('Alert not found.', {}, 404)

    # Treat acknowledge as soft-resolved so frontend hides the action buttons
    alert.is_resolved = True
    alert.resolved_at = timezone.now()
    alert.resolved_by = request.user
    alert.save(update_fields=['is_resolved', 'resolved_at', 'resolved_by'])
    return success_response('Alert acknowledged.', AlertSerializer(alert).data)


@api_view(['POST'])
@permission_classes([IsOwnerOrManager])
def alert_resolve(request, site_id, alert_id):
    """POST /api/sites/:id/alerts/:alertId/resolve/"""
    try:
        site = _get_sites_for_user(request.user).get(id=site_id)
    except Site.DoesNotExist:
        return error_response('Site not found.', {}, 404)

    try:
        alert = Alert.objects.get(id=alert_id, site=site)
    except Alert.DoesNotExist:
        return error_response('Alert not found.', {}, 404)

    alert.is_resolved = True
    alert.resolved_at = timezone.now()
    alert.resolved_by = request.user
    alert.save(update_fields=['is_resolved', 'resolved_at', 'resolved_by'])
    return success_response('Alert resolved.', AlertSerializer(alert).data)


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def site_photos(request, site_id):
    """GET /api/sites/:id/photos/ — owner-dashboard alias for progress photos."""
    site = _get_site_for_user_or_none(request.user, site_id)
    if not site:
        return error_response('Site not found.', {}, 404)

    data = _fetch_site_progress_photos(site)
    return success_response('Photos retrieved.', {
        'results': data,
        'total': len(data),
    })
