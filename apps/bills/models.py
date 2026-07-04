"""
Material delivery / bill logging models.
Each bill must have a photo (GPS + timestamp embedded) — this is the core
anti-fraud mechanism for construction material tracking in Sri Lanka.
"""
import uuid
from django.db import models
from django.conf import settings


MATERIAL_TYPES = [
    ('cement', 'Cement'),
    ('sand', 'Sand'),
    ('steel', 'Steel'),
    ('blocks', 'Blocks'),
    ('aggregate', 'Aggregate'),
    ('pipes', 'Pipes & Fittings'),
    ('timber', 'Timber'),
    ('bricks', 'Bricks'),
    ('roofing', 'Roofing Materials'),
    ('electrical', 'Electrical Materials'),
    ('plumbing', 'Plumbing Materials'),
    ('tiles', 'Tiles & Flooring'),
    ('paint', 'Paint & Finishing'),
    ('other', 'Other'),
]

PAYMENT_METHODS = [
    ('cash', 'Cash'),
    ('credit', 'Credit'),
    ('bank_transfer', 'Bank Transfer'),
]

PURPOSE_CHOICES = [
    ('foundation', 'Foundation'),
    ('columns', 'Columns'),
    ('slab', 'Slab'),
    ('walls', 'Walls'),
    ('finishing', 'Finishing'),
    ('other', 'Other'),
]


class Bill(models.Model):
    """
    Material delivery record logged by a site manager.
    bill_photo_url is required to deter fake bill entries — the photo
    must be taken on-site at time of delivery (GPS coordinates embedded).
    is_synced tracks whether an offline-created record has been pushed to server.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey('sites.Site', on_delete=models.CASCADE, related_name='bills')
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='logged_bills',
    )

    # Supplier / item are optional so the log also covers general expenses
    # (e.g. crew lunch, transport, small tools) — not just material deliveries.
    supplier_name = models.CharField(max_length=255, blank=True, null=True)
    # choices drive the suggestion list, but any custom label is accepted so
    # managers can record miscellaneous expenses.
    material_type = models.CharField(max_length=50, blank=True, null=True, default='other')
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=1)
    unit = models.CharField(max_length=50, blank=True, null=True, help_text='e.g. bags, cubic meters, kg')
    unit_price_lkr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount_lkr = models.DecimalField(max_digits=14, decimal_places=2)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default='other')

    delivery_vehicle_no = models.CharField(max_length=20, blank=True, null=True)

    # Photo is required — logged in GPS + timestamp metadata on mobile
    bill_photo_url = models.URLField(
        help_text='Supabase URL of the bill photo. Required — no photo = no bill.'
    )
    photo_gps_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    photo_gps_lng = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    photo_taken_at = models.DateTimeField(null=True, blank=True)

    log_date = models.DateField()

    # is_synced = False means this record was created offline and not yet confirmed by server
    is_synced = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ct_bills'
        ordering = ['-log_date', '-created_at']

    def __str__(self):
        return f"{self.material_type or 'expense'} x{self.quantity} at {self.site.name} on {self.log_date}"
