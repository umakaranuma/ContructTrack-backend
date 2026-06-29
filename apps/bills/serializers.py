from rest_framework import serializers
from .models import Bill


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
        # Enforce that bill_photo_url is present — core anti-fraud requirement
        if not data.get('bill_photo_url'):
            raise serializers.ValidationError({'bill_photo_url': 'A bill photo is required.'})
        return data
