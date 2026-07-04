"""
Contract management models.

Flow:
  Site ──► SiteContract (what the client will pay in total)
               └──► PaymentCertificate (each partial payment received from client)

  Site ──► Subcontract (scope given to another company)
               └──► SubcontractPayment (each installment paid to that company)
"""
import uuid
from django.db import models


CONTRACT_STATUS = [
    ('draft',  'Draft'),
    ('active', 'Active'),
    ('closed', 'Closed'),
]

CERT_STATUS = [
    ('pending',   'Pending'),
    ('submitted', 'Submitted'),
    ('received',  'Received'),
]

SUBCONTRACT_STATUS = [
    ('pending',   'Pending'),
    ('active',    'Active'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]

PAYMENT_METHODS = [
    ('cash',          'Cash'),
    ('bank_transfer', 'Bank Transfer'),
    ('cheque',        'Cheque'),
    ('other',         'Other'),
]


class SiteContract(models.Model):
    """
    The formal contract between the construction company and their client.
    Stores the agreed contract value and tracks how much has been received.
    One active contract per site (enforced at view level).
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site            = models.ForeignKey(
        'sites.Site', on_delete=models.CASCADE, related_name='contracts',
    )
    client_name     = models.CharField(max_length=255)
    contract_value_lkr = models.DecimalField(max_digits=14, decimal_places=2)
    contract_date   = models.DateField()
    status          = models.CharField(max_length=20, choices=CONTRACT_STATUS, default='active')
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-contract_date']

    def __str__(self):
        return f"{self.site.name} — {self.client_name} ({self.contract_value_lkr})"

    @property
    def total_received_lkr(self):
        from django.db.models import Sum
        result = self.payment_certs.filter(
            status='received'
        ).aggregate(t=Sum('amount_lkr'))['t'] or 0
        return float(result)

    @property
    def total_submitted_lkr(self):
        from django.db.models import Sum
        result = self.payment_certs.filter(
            status__in=['submitted', 'received']
        ).aggregate(t=Sum('amount_lkr'))['t'] or 0
        return float(result)

    @property
    def outstanding_lkr(self):
        return float(self.contract_value_lkr) - self.total_received_lkr


class PaymentCertificate(models.Model):
    """
    A single partial payment from the client to the construction company.
    Typically issued after a stage milestone is reached and inspected.
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract        = models.ForeignKey(
        SiteContract, on_delete=models.CASCADE, related_name='payment_certs',
    )
    cert_number     = models.PositiveIntegerField()
    amount_lkr      = models.DecimalField(max_digits=14, decimal_places=2)
    stage_milestone = models.CharField(max_length=150, blank=True)
    submitted_date  = models.DateField(null=True, blank=True)
    received_date   = models.DateField(null=True, blank=True)
    status          = models.CharField(max_length=20, choices=CERT_STATUS, default='pending')
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['cert_number']
        unique_together = [['contract', 'cert_number']]

    def __str__(self):
        return f"Cert #{self.cert_number} — {self.contract.site.name}"


class Subcontract(models.Model):
    """
    A scope of work given to an external company or small contractor.
    Tracks the agreed value and payment instalments paid to them.
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site            = models.ForeignKey(
        'sites.Site', on_delete=models.CASCADE, related_name='subcontracts',
    )
    company_name    = models.CharField(max_length=255)
    contact_person  = models.CharField(max_length=255, blank=True)
    contact_phone   = models.CharField(max_length=30, blank=True)
    scope_of_work   = models.CharField(max_length=500)
    contract_value_lkr = models.DecimalField(max_digits=14, decimal_places=2)
    start_date      = models.DateField(null=True, blank=True)
    end_date        = models.DateField(null=True, blank=True)
    status          = models.CharField(max_length=20, choices=SUBCONTRACT_STATUS, default='active')
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company_name} @ {self.site.name}"

    @property
    def total_paid_lkr(self):
        from django.db.models import Sum
        result = self.payments.aggregate(t=Sum('amount_lkr'))['t'] or 0
        return float(result)

    @property
    def balance_lkr(self):
        return float(self.contract_value_lkr) - self.total_paid_lkr


class SubcontractPayment(models.Model):
    """
    An instalment paid to a subcontractor.
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subcontract     = models.ForeignKey(
        Subcontract, on_delete=models.CASCADE, related_name='payments',
    )
    amount_lkr      = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date    = models.DateField()
    payment_method  = models.CharField(max_length=30, choices=PAYMENT_METHODS, default='bank_transfer')
    reference_no    = models.CharField(max_length=100, blank=True)
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"LKR {self.amount_lkr} to {self.subcontract.company_name}"
