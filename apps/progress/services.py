"""Shared progress-log helpers for owner dashboard and mobile APIs."""
from collections import Counter

from apps.bills.models import Bill
from apps.attendance.models import AttendanceSummary
from .models import ProgressLog, ProgressPhoto
from .serializers import SiteDailyLogSerializer


def daily_log_context_for_date(site, log_date):
    bills_by_date = Counter(
        Bill.objects.filter(site=site, log_date=log_date).values_list('log_date', flat=True)
    )
    attendance_by_date = {
        s.log_date: s
        for s in AttendanceSummary.objects.filter(site=site, log_date=log_date)
    }
    return {'bills_by_date': bills_by_date, 'attendance_by_date': attendance_by_date}


def serialize_site_daily_log(site, log):
    return SiteDailyLogSerializer(log).data


def fetch_daily_log_detail(site, log):
    """Build owner-dashboard daily log detail payload for a single log."""
    from apps.attendance.models import DailyAttendance, AttendanceSummary
    from .serializers import ProgressPhotoSerializer, DailyLogDetailSerializer

    log_date = log.log_date
    attendance_qs = (
        DailyAttendance.objects.filter(site=site, log_date=log_date)
        .select_related('worker')
        .order_by('worker__full_name')
    )
    attendance_rows = [
        {
            'id': str(rec.id),
            'worker_id': str(rec.worker_id),
            'worker_name': rec.worker.full_name,
            'role': rec.worker.role,
            'status': rec.status,
            'overtime_hours': rec.overtime_hours,
            'total_earned_lkr': rec.total_earned_lkr,
            'is_paid': rec.is_paid,
        }
        for rec in attendance_qs
    ]

    summary = AttendanceSummary.objects.filter(site=site, log_date=log_date).first()
    attendance_summary = None
    if summary:
        attendance_summary = {
            'total_present': summary.total_present,
            'total_half': summary.total_half,
            'total_absent': summary.total_absent,
            'total_wage_lkr': float(summary.total_wage_lkr),
        }

    bills = Bill.objects.filter(site=site, log_date=log_date).order_by('-created_at')
    bill_rows = [
        {
            'id': str(b.id),
            'supplier_name': b.supplier_name,
            'material_type': b.material_type,
            'material_label': b.get_material_type_display(),
            'total_amount_lkr': b.total_amount_lkr,
            'bill_photo_url': b.bill_photo_url,
            'payment_method': b.payment_method,
        }
        for b in bills
    ]

    photos = ProgressPhoto.objects.filter(progress_log=log).order_by('taken_at')

    payload = {
        'id': str(log.id),
        'log_date': log_date,
        'stage': log.stage,
        'work_done_today': log.work_done_today,
        'tomorrow_status': log.tomorrow_status,
        'blockers': log.blockers,
        'blocker_note': log.blocker_note,
        'manager': log.logged_by.full_name if log.logged_by else None,
        'site_name': site.name,
        'created_at': log.created_at,
        'attendance': attendance_rows,
        'attendance_summary': attendance_summary,
        'bills': bill_rows,
        'photos': ProgressPhotoSerializer(photos, many=True).data,
    }
    return DailyLogDetailSerializer(payload).data


def upsert_progress_log(site, logged_by, validated_data):
    """
    One log per site per day — create or update if the date already exists.
    Returns (log, created).
    """
    log_date = validated_data['log_date']
    defaults = {k: v for k, v in validated_data.items() if k != 'log_date'}
    defaults['logged_by'] = logged_by
    defaults['stage'] = defaults.get('stage') or site.current_stage

    return ProgressLog.objects.update_or_create(
        site=site,
        log_date=log_date,
        defaults=defaults,
    )
