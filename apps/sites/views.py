"""
Site management views.
All queries are filtered by tenant — a manager can only see sites they are assigned to;
an owner sees all sites belonging to their tenant.
"""
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


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def site_logs(request, site_id):
    """GET /api/sites/:id/logs/ — combined timeline: bills + progress + attendance."""
    try:
        site = _get_sites_for_user(request.user).get(id=site_id)
    except Site.DoesNotExist:
        return error_response('Site not found.', {}, 404)

    from apps.progress.models import ProgressLog
    from apps.progress.serializers import ProgressLogSerializer

    logs = ProgressLog.objects.filter(site=site).order_by('-log_date')[:50]
    return success_response('Logs retrieved.', ProgressLogSerializer(logs, many=True).data)


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def site_bills(request, site_id):
    """GET /api/sites/:id/bills/"""
    try:
        site = _get_sites_for_user(request.user).get(id=site_id)
    except Site.DoesNotExist:
        return error_response('Site not found.', {}, 404)

    from apps.bills.models import Bill
    from apps.bills.serializers import BillSerializer

    bills = Bill.objects.filter(site=site).order_by('-log_date')
    page = int(request.query_params.get('page', 1))
    limit = int(request.query_params.get('limit', 20))
    paged, total, pages = paginate_queryset(bills, page, limit)
    return success_response('Bills retrieved.', {
        'results': BillSerializer(paged, many=True).data,
        'total': total, 'page': page, 'total_pages': pages,
    })


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def site_attendance(request, site_id):
    """GET /api/sites/:id/attendance/"""
    try:
        site = _get_sites_for_user(request.user).get(id=site_id)
    except Site.DoesNotExist:
        return error_response('Site not found.', {}, 404)

    from apps.attendance.models import DailyAttendance
    from apps.attendance.serializers import DailyAttendanceSerializer

    records = DailyAttendance.objects.filter(site=site).order_by('-log_date')
    page = int(request.query_params.get('page', 1))
    limit = int(request.query_params.get('limit', 50))
    paged, total, pages = paginate_queryset(records, page, limit)
    return success_response('Attendance retrieved.', {
        'results': DailyAttendanceSerializer(paged, many=True).data,
        'total': total, 'page': page, 'total_pages': pages,
    })


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def site_progress_photos(request, site_id):
    """GET /api/sites/:id/progress-photos/"""
    try:
        site = _get_sites_for_user(request.user).get(id=site_id)
    except Site.DoesNotExist:
        return error_response('Site not found.', {}, 404)

    from apps.progress.models import ProgressPhoto
    from apps.progress.serializers import ProgressPhotoSerializer

    photos = ProgressPhoto.objects.filter(progress_log__site=site).order_by('-taken_at')
    return success_response('Photos retrieved.', ProgressPhotoSerializer(photos, many=True).data)


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
def site_daily_logs(request, site_id):
    """GET /api/sites/:id/daily-logs/ — alias for site_logs."""
    return site_logs(request, site_id)


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def site_photos(request, site_id):
    """GET /api/sites/:id/photos/ — alias for site_progress_photos."""
    return site_progress_photos(request, site_id)
