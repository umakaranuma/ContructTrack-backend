"""
Construction site models.
Sites are the primary data container — every bill, attendance record,
and progress log belongs to a site which belongs to a tenant.
"""
import uuid
from django.db import models
from django.conf import settings


CONSTRUCTION_STAGES = [
    ('excavation', 'Excavation'),
    ('foundation', 'Foundation'),
    ('ground_slab', 'Ground Slab'),
    ('columns', 'Columns'),
    ('beams', 'Beams'),
    ('upper_slab', 'Upper Slab'),
    ('walls', 'Walls'),
    ('roof', 'Roof'),
    ('finishing', 'Finishing'),
    ('completed', 'Completed'),
]

PROJECT_TYPES = [
    ('residential', 'Residential'),
    ('commercial', 'Commercial'),
    ('infrastructure', 'Infrastructure'),
]


class Site(models.Model):
    """
    A physical construction site owned by a tenant.
    Owners create sites; managers are assigned to sites and can log data.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,  # deleting a tenant removes all their sites
        related_name='sites',
    )
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    project_type = models.CharField(max_length=30, choices=PROJECT_TYPES, default='residential')
    current_stage = models.CharField(max_length=30, choices=CONSTRUCTION_STAGES, default='excavation')
    budget_lkr = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ct_sites'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.tenant.company_name})"


class SiteManager(models.Model):
    """
    Junction table between Site and User (manager).
    A manager can be assigned to multiple sites; a site can have multiple managers.
    removed_at is set when a manager is removed (soft-delete preserves history).
    """
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='site_managers')
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='managed_sites',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'ct_site_managers'
        unique_together = [('site', 'manager')]


class Alert(models.Model):
    """
    System-generated alerts for a site (e.g. missing daily log, suspicious bill).
    Created by background Celery tasks, dismissed by the owner or manager.
    """
    ALERT_TYPES = [
        ('material_cap', 'Material Cap Exceeded'),
        ('missing_log', 'Missing Progress Log'),
        ('no_bill_photo', 'Bill Without Photo'),
        ('anomaly', 'Anomaly Detected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ct_alerts'
        ordering = ['-created_at']
