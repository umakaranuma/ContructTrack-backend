from rest_framework import serializers
from .models import Bill


class SiteBillGridSerializer(serializers.ModelSerializer):
    """Bill shape expected by the owner-dashboard BillPhotoGrid."""
    photo_url = serializers.URLField(source='bill_photo_url', read_only=True)
    supplier = serializers.CharField(source='supplier_name', read_only=True)
    amount = serializers.DecimalField(source='total_amount_lkr', max_digits=14, decimal_places=2, read_only=True)
    date = serializers.DateField(source='log_date', read_only=True)
    material = serializers.SerializerMethodField()

    class Meta:
        model = Bill
        fields = ['id', 'photo_url', 'supplier', 'amount', 'date', 'material', 'bill_photo_url', 'supplier_name', 'total_amount_lkr', 'log_date', 'material_type']

    def get_material(self, obj):
        # get_..._display() returns the raw value for custom (non-choice) labels.
        return obj.get_material_type_display() if obj.material_type else 'Expense'


class BillSerializer(serializers.ModelSerializer):
    logged_by_name = serializers.SerializerMethodField()
    site_name      = serializers.SerializerMethodField()

    class Meta:
        model = Bill
        fields = [
            'id', 'site', 'site_name', 'logged_by', 'logged_by_name',
            'supplier_name', 'material_type', 'quantity', 'unit',
            'unit_price_lkr', 'total_amount_lkr',
            'payment_method', 'purpose', 'delivery_vehicle_no',
            'bill_photo_url', 'photo_gps_lat', 'photo_gps_lng', 'photo_taken_at',
            'log_date', 'is_synced', 'created_at',
        ]
        read_only_fields = ['id', 'site', 'site_name', 'logged_by', 'logged_by_name', 'created_at']

    def get_logged_by_name(self, obj):
        return obj.logged_by.full_name if obj.logged_by else None

    def get_site_name(self, obj):
        return obj.site.name if obj.site_id else ''


class BillCreateSerializer(serializers.ModelSerializer):
    # Supplier and item/category are optional so the form also covers general
    # expenses (crew lunch, transport, tools). material_type is a free CharField
    # rather than a strict ChoiceField so custom expense labels are accepted.
    supplier_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    material_type = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    quantity      = serializers.DecimalField(max_digits=10, decimal_places=3, required=False, default=1)
    unit          = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    unit_price_lkr = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)
    purpose       = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=30)

    class Meta:
        model = Bill
        fields = [
            'supplier_name', 'material_type', 'quantity', 'unit',
            'unit_price_lkr', 'total_amount_lkr',
            'payment_method', 'purpose', 'delivery_vehicle_no',
            'bill_photo_url', 'photo_gps_lat', 'photo_gps_lng', 'photo_taken_at',
            'log_date', 'is_synced',
        ]

    def validate(self, data):
        # Enforce that bill_photo_url is present — core anti-fraud requirement.
        # On partial updates the existing photo is kept, so only check creates
        # or explicit attempts to blank the photo.
        if self.instance is None:
            if not data.get('bill_photo_url'):
                raise serializers.ValidationError({'bill_photo_url': 'A bill photo is required.'})
            # The total amount is the one figure that must always be present.
            if not data.get('total_amount_lkr'):
                raise serializers.ValidationError({'total_amount_lkr': 'An amount is required.'})
        elif 'bill_photo_url' in data and not data['bill_photo_url']:
            raise serializers.ValidationError({'bill_photo_url': 'A bill photo cannot be removed.'})
        return data
