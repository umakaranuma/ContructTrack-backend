"""
Mobile API views — optimised for low-bandwidth, offline-first mobile apps.
All data is scoped to the authenticated manager's assigned sites.
The sync endpoint handles batch upload of offline-created records.
"""
import logging
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.core.utils import success_response, error_response
from apps.core.permissions import IsOwnerOrManager, IsManager
from apps.sites.models import Site, SiteManager
from apps.bills.models import Bill
from apps.bills.serializers import BillSerializer, BillCreateSerializer
from apps.attendance.models import Worker, DailyAttendance, AttendanceSummary
from apps.attendance.serializers import WorkerSerializer, WorkerCreateSerializer, DailyAttendanceSerializer
from apps.progress.models import ProgressLog, ProgressPhoto
from apps.progress.serializers import ProgressLogSerializer, ProgressLogCreateSerializer, ProgressPhotoSerializer

logger = logging.getLogger(__name__)


def _get_manager_sites(user):
    """Manager sees only assigned sites; owner sees all their tenant sites."""
    if user.user_type == 'manager':
        assigned_ids = SiteManager.objects.filter(
            manager=user, is_active=True
        ).values_list('site_id', flat=True)
        return Site.objects.filter(id__in=assigned_ids, is_active=True)
    elif user.user_type == 'owner':
        from apps.tenants.models import Tenant
        tenant = Tenant.objects.filter(owner=user).first()
        if tenant:
            return Site.objects.filter(tenant=tenant, is_active=True)
    return Site.objects.none()


def _get_site_or_error(user, site_id):
    """Get a site the user has access to, or return an error response."""
    try:
        return _get_manager_sites(user).get(id=site_id), None
    except Site.DoesNotExist:
        return None, error_response('Site not found or not accessible.', {}, 404)


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def mobile_sites(request):
    """GET /api/mobile/sites/ — compact site list for the mobile home screen."""
    sites = _get_manager_sites(request.user)
    data = [{
        'id': str(s.id),
        'name': s.name,
        'current_stage': s.current_stage,
        'project_type': s.project_type,
        'is_active': s.is_active,
    } for s in sites]
    return success_response('Sites retrieved.', data)


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def mobile_site_params(request, site_id):
    """
    GET /api/mobile/sites/:id/params/
    Returns all configuration a manager needs to work offline:
    workers list, current stage, allowed bill categories, etc.
    """
    site, err = _get_site_or_error(request.user, site_id)
    if err:
        return err

    workers = Worker.objects.filter(site=site, is_active=True).values(
        'id', 'full_name', 'role', 'daily_rate_lkr', 'contract_type'
    )

    return success_response('Site params retrieved.', {
        'site_id': str(site.id),
        'site_name': site.name,
        'current_stage': site.current_stage,
        'project_type': site.project_type,
        'workers': list(workers),
        'material_types': ['cement', 'sand', 'steel', 'blocks', 'aggregate', 'other'],
        'payment_methods': ['cash', 'credit', 'bank_transfer'],
        'purposes': ['foundation', 'columns', 'slab', 'walls', 'finishing', 'other'],
    })


# ---------------------------------------------------------------------------
# Bills
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsOwnerOrManager])
def mobile_bills(request, site_id):
    site, err = _get_site_or_error(request.user, site_id)
    if err:
        return err

    if request.method == 'GET':
        bills = Bill.objects.filter(site=site).order_by('-log_date')[:50]
        return success_response('Bills retrieved.', BillSerializer(bills, many=True).data)

    # POST — create new bill
    serializer = BillCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)

    bill = serializer.save(site=site, logged_by=request.user)
    return success_response('Bill logged.', BillSerializer(bill).data, 201)


@api_view(['POST'])
@permission_classes([IsOwnerOrManager])
def mobile_bill_photo(request, site_id, bill_id):
    """
    POST /api/mobile/sites/:id/bills/:billId/photo/
    Updates bill_photo_url after the client uploads directly to Supabase.
    Called when GPS photo upload completes on the mobile.
    """
    site, err = _get_site_or_error(request.user, site_id)
    if err:
        return err

    try:
        bill = Bill.objects.get(id=bill_id, site=site)
    except Bill.DoesNotExist:
        return error_response('Bill not found.', {}, 404)

    photo_url = request.data.get('photo_url')
    if not photo_url:
        return error_response('photo_url is required.', {}, 400)

    bill.bill_photo_url = photo_url
    bill.photo_gps_lat = request.data.get('gps_lat')
    bill.photo_gps_lng = request.data.get('gps_lng')
    bill.photo_taken_at = request.data.get('taken_at')
    bill.save(update_fields=['bill_photo_url', 'photo_gps_lat', 'photo_gps_lng', 'photo_taken_at'])

    return success_response('Bill photo updated.', BillSerializer(bill).data)


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsOwnerOrManager])
def mobile_workers(request, site_id):
    site, err = _get_site_or_error(request.user, site_id)
    if err:
        return err

    if request.method == 'GET':
        workers = Worker.objects.filter(site=site, is_active=True)
        return success_response('Workers retrieved.', WorkerSerializer(workers, many=True).data)

    serializer = WorkerCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)
    worker = serializer.save(site=site)
    return success_response('Worker added.', WorkerSerializer(worker).data, 201)


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsOwnerOrManager])
def mobile_attendance(request, site_id):
    """
    POST /api/mobile/sites/:id/attendance/
    Bulk-submit a full day's attendance.
    Body: { log_date, is_rain_day, records: [{worker_id, status, overtime_hours}] }
    """
    site, err = _get_site_or_error(request.user, site_id)
    if err:
        return err

    log_date = request.data.get('log_date')
    is_rain_day = request.data.get('is_rain_day', False)
    records = request.data.get('records', [])

    if not log_date:
        return error_response('log_date is required.', {}, 400)
    if not records:
        return error_response('records list cannot be empty.', {}, 400)

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

            att, created = DailyAttendance.objects.update_or_create(
                site=site,
                worker=worker,
                log_date=log_date,
                defaults={
                    'status': rec.get('status', 'present'),
                    'overtime_hours': rec.get('overtime_hours', 0),
                    'daily_rate_lkr': worker.daily_rate_lkr,  # snapshot current rate
                    'logged_by': request.user,
                    'is_rain_day': is_rain_day,
                    'is_synced': True,
                }
            )
            if created:
                created_count += 1

        # Compute and store daily summary
        from django.db.models import Sum, Count
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
                'submitted_by': request.user,
            }
        )

    return success_response('Attendance submitted.', {
        'log_date': log_date,
        'created': created_count,
        'errors': errors,
    }, 201)


@api_view(['PATCH'])
@permission_classes([IsOwnerOrManager])
def mobile_attendance_pay(request, site_id, log_date):
    """
    PATCH /api/mobile/sites/:id/attendance/:date/pay/
    Mark all present/half-day workers as paid for the day.
    """
    site, err = _get_site_or_error(request.user, site_id)
    if err:
        return err

    updated = DailyAttendance.objects.filter(
        site=site, log_date=log_date, is_paid=False
    ).exclude(status='absent').update(is_paid=True)

    return success_response(f'Marked {updated} records as paid.')


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsOwnerOrManager])
def mobile_progress(request, site_id):
    site, err = _get_site_or_error(request.user, site_id)
    if err:
        return err

    if request.method == 'GET':
        date_filter = request.query_params.get('date', '')
        logs = ProgressLog.objects.filter(site=site).prefetch_related('photos')
        if date_filter == 'today':
            from django.utils.timezone import localdate
            logs = logs.filter(log_date=localdate())
        elif date_filter:
            logs = logs.filter(log_date=date_filter)
        return success_response('Progress logs.', ProgressLogSerializer(logs[:30], many=True).data)

    # POST — create or update (one log per site per day)
    from apps.progress.services import upsert_progress_log

    serializer = ProgressLogCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)

    log, created = upsert_progress_log(site, request.user, serializer.validated_data)
    message = 'Progress logged.' if created else 'Progress log updated for this date.'
    return success_response(message, ProgressLogSerializer(log).data, 201 if created else 200)


@api_view(['POST'])
@permission_classes([IsOwnerOrManager])
def mobile_progress_photos(request, site_id, log_id):
    """
    POST /api/mobile/sites/:id/progress/:logId/photos/
    Attach photos to a progress log after direct Supabase upload.
    """
    site, err = _get_site_or_error(request.user, site_id)
    if err:
        return err

    try:
        log = ProgressLog.objects.get(id=log_id, site=site)
    except ProgressLog.DoesNotExist:
        return error_response('Progress log not found.', {}, 404)

    photos_data = request.data.get('photos', [])
    if not photos_data:
        return error_response('photos list is required.', {}, 400)

    created_photos = []
    for p in photos_data:
        photo = ProgressPhoto.objects.create(
            progress_log=log,
            photo_url=p.get('photo_url', ''),
            gps_lat=p.get('gps_lat'),
            gps_lng=p.get('gps_lng'),
            taken_at=p.get('taken_at'),
            caption=p.get('caption', ''),
        )
        created_photos.append(photo)

    return success_response('Photos added.', ProgressPhotoSerializer(created_photos, many=True).data, 201)


# ---------------------------------------------------------------------------
# Bulk sync endpoint
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsOwnerOrManager])
def mobile_sync(request):
    """
    POST /api/mobile/sync/
    Accepts a batch of records created offline and upserts them.
    This is the core offline-first sync mechanism — the mobile app accumulates
    records locally and pushes when connectivity is restored.
    Body: { bills: [...], attendance: [...], progress: [...] }
    """
    bills_data = request.data.get('bills', [])
    attendance_data = request.data.get('attendance', [])
    progress_data = request.data.get('progress', [])

    results = {
        'bills': {'synced': 0, 'errors': []},
        'attendance': {'synced': 0, 'errors': []},
        'progress': {'synced': 0, 'errors': []},
    }

    manager_site_ids = set(str(sid) for sid in _get_manager_sites(request.user).values_list('id', flat=True))

    with transaction.atomic():
        # Sync bills
        for b in bills_data:
            if str(b.get('site')) not in manager_site_ids:
                results['bills']['errors'].append(f"No access to site {b.get('site')}")
                continue
            try:
                serializer = BillCreateSerializer(data=b)
                if serializer.is_valid():
                    site = Site.objects.get(id=b['site'])
                    bill = serializer.save(site=site, logged_by=request.user, is_synced=True)
                    results['bills']['synced'] += 1
                else:
                    results['bills']['errors'].append(serializer.errors)
            except Exception as exc:
                results['bills']['errors'].append(str(exc))

        # Sync attendance
        for rec in attendance_data:
            try:
                site_id = rec.get('site')
                if str(site_id) not in manager_site_ids:
                    results['attendance']['errors'].append(f"No access to site {site_id}")
                    continue
                site = Site.objects.get(id=site_id)
                worker = Worker.objects.get(id=rec.get('worker'), site=site)
                DailyAttendance.objects.update_or_create(
                    site=site, worker=worker, log_date=rec['log_date'],
                    defaults={
                        'status': rec.get('status', 'present'),
                        'overtime_hours': rec.get('overtime_hours', 0),
                        'daily_rate_lkr': worker.daily_rate_lkr,
                        'logged_by': request.user,
                        'is_rain_day': rec.get('is_rain_day', False),
                        'is_synced': True,
                    }
                )
                results['attendance']['synced'] += 1
            except Exception as exc:
                results['attendance']['errors'].append(str(exc))

        # Sync progress
        for p in progress_data:
            try:
                site_id = p.get('site')
                if str(site_id) not in manager_site_ids:
                    results['progress']['errors'].append(f"No access to site {site_id}")
                    continue
                site = Site.objects.get(id=site_id)
                ProgressLog.objects.update_or_create(
                    site=site, log_date=p['log_date'],
                    defaults={
                        'logged_by': request.user,
                        'stage': p.get('stage', site.current_stage),
                        'work_done_today': p.get('work_done_today', ''),
                        'blockers': p.get('blockers'),
                        'blocker_note': p.get('blocker_note', ''),
                        'tomorrow_status': p.get('tomorrow_status', 'working'),
                        'is_synced': True,
                    }
                )
                results['progress']['synced'] += 1
            except Exception as exc:
                results['progress']['errors'].append(str(exc))

    return success_response('Sync complete.', results)
