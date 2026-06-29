"""
Payment records for tenant subscriptions.
Supports PayHere (most common in Sri Lanka), Webxpay, manual bank transfers.
Gateway webhooks update status asynchronously.
"""
import uuid
from django.db import models
from django.conf import settings


class Payment(models.Model):
    METHOD_CHOICES = [
        ('payhere', 'PayHere'),
        ('webxpay', 'Webxpay'),
        ('bank_transfer', 'Bank Transfer'),
        ('manual', 'Manual (Admin)'),
    ]

    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('refunded', 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='payments')
    package = models.ForeignKey(
        'tenants.Package',
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
        help_text='Package purchased in this payment.',
    )
    amount_lkr = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)

    # gateway_ref is PayHere order_id or Webxpay transaction_id
    gateway_ref = models.CharField(max_length=255, blank=True, null=True, unique=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateField(null=True, blank=True)
    validity_months = models.PositiveSmallIntegerField(
        default=1,
        help_text='How many months this payment extends the subscription.',
    )
    internal_note = models.TextField(blank=True, null=True)

    # recorded_by is set for manual payments entered by finance admin
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ct_payments'
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.id} — {self.tenant.company_name} LKR {self.amount_lkr} [{self.status}]"
