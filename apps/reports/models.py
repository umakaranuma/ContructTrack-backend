"""
Report generation tracking.
Report generation is async (Celery task) — the record is created with status=pending,
a task runs to generate the file, then sets file_url and status=ready.
"""
import uuid
from django.db import models
from django.conf import settings


class Report(models.Model):
    REPORT_TYPES = [
        ('material_consumption', 'Material Consumption'),
        ('attendance_log', 'Attendance Log'),
        ('monthly_spend', 'Monthly Spend'),
        ('bank_loan', 'Bank Loan Report'),
        ('custom', 'Custom'),
        ('subcontractor', 'Subcontractor'),
    ]

    FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='reports')
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES)

    # site is optional — null means "all sites in tenant"
    site = models.ForeignKey(
        'sites.Site',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reports',
    )

    date_from = models.DateField()
    date_to = models.DateField()
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='pdf')

    # file_url is populated by the Celery task after generation
    file_url = models.URLField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ct_reports'
        ordering = ['-created_at']
