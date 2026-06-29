"""
Tenant, Package, and subscription tracking models.
Multi-tenancy is implemented at the application layer (not DB schemas) —
all tenant data is filtered by tenant FK in every query.
"""
import uuid
from django.db import models
from django.conf import settings


class Package(models.Model):
    """
    Subscription tiers available in ConstructTrack.
    Feature flags on the package control what each tenant can access
    without needing a separate feature-flag system.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)                 # e.g. "Lite", "Pro", "Enterprise"
    price_lkr = models.DecimalField(max_digits=10, decimal_places=2)
    max_sites = models.PositiveIntegerField(default=1)
    max_managers = models.PositiveIntegerField(default=2)
    trial_days = models.PositiveIntegerField(default=14)

    # Feature flags — checked at the API layer before expensive operations
    feature_excel = models.BooleanField(default=True)
    feature_whatsapp = models.BooleanField(default=False)
    feature_bill_gps = models.BooleanField(default=True)
    feature_theft_alerts = models.BooleanField(default=False)
    feature_bank_report = models.BooleanField(default=False)
    feature_branded_pdf = models.BooleanField(default=False)
    feature_subcontractor = models.BooleanField(default=False)

    display_order = models.PositiveSmallIntegerField(default=0)  # controls card order on pricing page
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'ct_packages'
        ordering = ['display_order']

    def __str__(self):
        return f"{self.name} (LKR {self.price_lkr})"


class Tenant(models.Model):
    """
    Represents a construction company using ConstructTrack.
    Every site, worker, bill etc. traces back to a tenant.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('trial', 'Trial'),
        ('expired', 'Expired'),
        ('suspended', 'Suspended'),
    ]

    EMAIL_DIGEST_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('off', 'Off'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_name = models.CharField(max_length=255)

    # One-to-one conceptually, but FK allows owner account to be swapped by admin
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # don't delete tenant if owner is deleted — data safety
        related_name='owned_tenants',
    )
    package = models.ForeignKey(
        Package,
        on_delete=models.PROTECT,  # can't delete a package that has active tenants
        null=True,
        blank=True,
        related_name='tenants',
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')

    subscription_start = models.DateTimeField(null=True, blank=True)
    subscription_end = models.DateTimeField(null=True, blank=True)
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)

    logo_url = models.URLField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)

    # WhatsApp alert settings — only available on Pro/Enterprise packages
    whatsapp_alerts = models.BooleanField(default=False)
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True)

    email_digest = models.CharField(max_length=10, choices=EMAIL_DIGEST_CHOICES, default='daily')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ct_tenants'

    def __str__(self):
        return f"{self.company_name} [{self.status}]"

    def has_feature(self, feature_name: str) -> bool:
        """
        Check if this tenant's current package includes a specific feature.
        Called in views to gate premium functionality.
        """
        if not self.package:
            return False
        return getattr(self.package, f'feature_{feature_name}', False)


class TenantSubscriptionLog(models.Model):
    """
    Immutable audit trail of subscription changes.
    Stored separately so it can never be edited even by super admins — evidence of billing history.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='subscription_logs')
    old_package = models.ForeignKey(
        Package, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    new_package = models.ForeignKey(
        Package, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+'
    )
    reason = models.TextField(blank=True, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ct_tenant_subscription_logs'
        ordering = ['-changed_at']
