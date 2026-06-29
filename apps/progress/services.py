"""Shared progress-log helpers for owner dashboard and mobile APIs."""
from collections import Counter

from apps.bills.models import Bill
from apps.attendance.models import AttendanceSummary
from .models import ProgressLog
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
    context = daily_log_context_for_date(site, log.log_date)
    return SiteDailyLogSerializer(log, context=context).data


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
