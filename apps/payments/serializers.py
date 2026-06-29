from rest_framework import serializers
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    tenant_name = serializers.SerializerMethodField()
    package_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'id', 'tenant', 'tenant_name', 'package', 'package_name',
            'amount_lkr', 'method', 'gateway_ref', 'status',
            'payment_date', 'validity_months', 'internal_note',
            'recorded_by', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_tenant_name(self, obj):
        return obj.tenant.company_name

    def get_package_name(self, obj):
        return obj.package.name if obj.package else None
