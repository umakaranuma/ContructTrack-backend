"""
Daily progress logs and photo evidence for construction sites.
Progress logs are the primary accountability mechanism — managers must submit one per day.
Missing logs trigger alerts visible to owners (and WhatsApp notifications on Pro+).
"""
import uuid
from django.db import models
from django.conf import settings


BLOCKER_CHOICES = [
    ('material_shortage', 'Material Shortage'),
    ('worker_noshow', 'Workers Did Not Show Up'),
    ('equipment_fault', 'Equipment Fault'),
    ('rain', 'Rain'),
    ('awaiting_owner', 'Awaiting Owner Decision'),
    ('other', 'Other'),
]

TOMORROW_STATUS_CHOICES = [
    ('working', 'Working'),
    ('rain_hold', 'Rain Hold'),
    ('material_wait', 'Waiting for Materials'),
    ('awaiting_owner', 'Awaiting Owner'),
]


class ProgressLog(models.Model):
    """
    End-of-day report submitted by the site manager.
    stage is snapshot of current_stage at log time — allows tracking stage history.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='progress_logs')
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='progress_logs',
    )
    log_date = models.DateField()

    # Snapshot the stage so historical logs remain accurate after stage advance
    stage = models.CharField(max_length=30)

    work_done_today = models.TextField(help_text='Free text description of work completed today.')

    blockers = models.CharField(
        max_length=30,
        choices=BLOCKER_CHOICES,
        null=True,
        blank=True,
        help_text='Primary reason if work was impeded.',
    )
    blocker_note = models.TextField(blank=True, null=True)
    tomorrow_status = models.CharField(
        max_length=100,
        default='working',
        help_text='Preset or custom status for the next working day.',
    )
    tomorrow_plan = models.TextField(
        blank=True, null=True,
        help_text='Free-text plan of what the team intends to do tomorrow.',
    )

    is_synced = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ct_progress_logs'
        unique_together = [('site', 'log_date')]  # one log per site per day
        ordering = ['-log_date']

    def __str__(self):
        return f"Progress @ {self.site.name} on {self.log_date}"


class ProgressPhoto(models.Model):
    """
    Photo evidence attached to a progress log.
    GPS + timestamp validates the photo was taken on-site at the right time.
    Multiple photos per log allowed.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    progress_log = models.ForeignKey(ProgressLog, on_delete=models.CASCADE, related_name='photos')
    photo_url = models.URLField()
    gps_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    gps_lng = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    taken_at = models.DateTimeField(null=True, blank=True)
    caption = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'ct_progress_photos'
        ordering = ['taken_at']
