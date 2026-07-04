"""
Worker roster and daily attendance tracking.
Workers are site-specific (not global) — same person at two sites = two Worker records.
DailyAttendance.total_earned_lkr is pre-computed at write time to speed up finance queries.
"""
import uuid
from django.db import models
from django.conf import settings


class Worker(models.Model):
    """
    A labourer or skilled worker on a specific construction site.
    daily_rate_lkr can change over time; DailyAttendance snapshots it on log.
    """
    CONTRACT_TYPES = [
        ('daily', 'Daily Rate'),
        ('monthly', 'Monthly Rate'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='workers')
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=100, help_text='e.g. Mason, Labourer, Electrician')
    nic = models.CharField(max_length=30, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    daily_rate_lkr = models.DecimalField(max_digits=10, decimal_places=2)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPES, default='daily')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ct_workers'
        ordering = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.role}) @ {self.site.name}"


class DailyAttendance(models.Model):
    """
    Single attendance record per worker per day.
    total_earned_lkr = daily_rate_lkr * (1 for present, 0.5 for half) + overtime.
    Computed on creation so finance queries are fast aggregations.
    """
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('half', 'Half Day'),
        ('absent', 'Absent'),
    ]

    ABSENT_REASON_CHOICES = [
        ('sick', 'Sick / Medical'),
        ('personal', 'Personal Leave'),
        ('no_show', 'Did Not Show Up'),
        ('rain', 'Rain Day'),
        ('other_site', 'Working at Another Site'),
        ('terminated', 'No Longer Employed'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='attendance_records')
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='attendance')
    log_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    overtime_hours = models.DecimalField(max_digits=4, decimal_places=1, default=0)

    # Only meaningful when status == 'absent' — captures why the worker missed the day.
    absent_reason = models.CharField(
        max_length=20, choices=ABSENT_REASON_CHOICES, blank=True, null=True,
    )
    note = models.CharField(max_length=255, blank=True, null=True)

    # Snapshot rate at time of log — rate may change but historical records must not
    daily_rate_lkr = models.DecimalField(max_digits=10, decimal_places=2)

    # Pre-computed to avoid recalculating during report generation
    total_earned_lkr = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    is_paid = models.BooleanField(default=False, help_text='Was cash payment made today?')
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='logged_attendance',
    )
    is_rain_day = models.BooleanField(default=False)
    is_synced = models.BooleanField(default=True)

    class Meta:
        db_table = 'ct_daily_attendance'
        unique_together = [('site', 'worker', 'log_date')]
        ordering = ['-log_date']

    def save(self, *args, **kwargs):
        """Auto-compute total_earned_lkr on every save."""
        rate = float(self.daily_rate_lkr or 0)
        if self.status == 'present':
            base = rate
        elif self.status == 'half':
            base = rate * 0.5
        else:
            base = 0
        overtime_pay = (rate / 8) * float(self.overtime_hours) * 1.5
        self.total_earned_lkr = round(base + overtime_pay, 2)
        super().save(*args, **kwargs)


class AttendanceSummary(models.Model):
    """
    Daily roll-up submitted by the manager at end of day.
    Stores aggregate totals so the owner dashboard loads instantly.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='attendance_summaries')
    log_date = models.DateField()
    total_present = models.PositiveIntegerField(default=0)
    total_half = models.PositiveIntegerField(default=0)
    total_absent = models.PositiveIntegerField(default=0)
    total_wage_lkr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_synced = models.BooleanField(default=True)

    class Meta:
        db_table = 'ct_attendance_summaries'
        unique_together = [('site', 'log_date')]
        ordering = ['-log_date']
