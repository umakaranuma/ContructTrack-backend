"""
Serializers for packages, tenants, and subscription logs.
"""
from rest_framework import serializers
from .models import Package, Tenant, TenantSubscriptionLog


class PackageSerializer(serializers.ModelSerializer):
    """Public-facing package listing — no internal pricing metadata."""

    class Meta:
        model = Package
        fields = [
            'id', 'name', 'price_lkr', 'max_sites', 'max_managers', 'trial_days',
            'feature_excel', 'feature_whatsapp', 'feature_bill_gps',
            'feature_theft_alerts', 'feature_bank_report',
            'feature_branded_pdf', 'feature_subcontractor',
            'display_order',
        ]


class TenantSerializer(serializers.ModelSerializer):
    """Full tenant detail — used in admin and owner settings."""
    package = PackageSerializer(read_only=True)
    package_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = Tenant
        fields = [
            'id', 'company_name', 'owner', 'package', 'package_id',
            'status', 'subscription_start', 'subscription_end',
            'trial_start', 'trial_end',
            'logo_url', 'address', 'contact_email', 'contact_phone',
            'whatsapp_alerts', 'whatsapp_number', 'email_digest',
            'created_at',
        ]
        read_only_fields = ['id', 'owner', 'status', 'created_at']


class TenantSettingsUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/settings/ — owner can update company info and notification prefs."""

    class Meta:
        model = Tenant
        fields = [
            'company_name', 'address', 'contact_email', 'contact_phone',
            'whatsapp_alerts', 'whatsapp_number', 'email_digest',
        ]


class SubscriptionLogSerializer(serializers.ModelSerializer):
    old_package_name = serializers.SerializerMethodField()
    new_package_name = serializers.SerializerMethodField()
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TenantSubscriptionLog
        fields = [
            'id', 'old_package_name', 'new_package_name',
            'changed_by_name', 'reason', 'changed_at',
        ]

    def get_old_package_name(self, obj):
        return obj.old_package.name if obj.old_package else None

    def get_new_package_name(self, obj):
        return obj.new_package.name if obj.new_package else None

    def get_changed_by_name(self, obj):
        return obj.changed_by.full_name if obj.changed_by else 'System'
