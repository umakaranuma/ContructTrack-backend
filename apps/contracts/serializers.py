from rest_framework import serializers
from .models import SiteContract, PaymentCertificate, Subcontract, SubcontractPayment


class PaymentCertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCertificate
        fields = [
            'id', 'cert_number', 'amount_lkr', 'stage_milestone',
            'submitted_date', 'received_date', 'status', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class SiteContractSerializer(serializers.ModelSerializer):
    payment_certs       = PaymentCertificateSerializer(many=True, read_only=True)
    total_received_lkr  = serializers.SerializerMethodField()
    total_submitted_lkr = serializers.SerializerMethodField()
    outstanding_lkr     = serializers.SerializerMethodField()
    received_pct        = serializers.SerializerMethodField()
    site_name           = serializers.SerializerMethodField()

    class Meta:
        model = SiteContract
        fields = [
            'id', 'site', 'site_name', 'client_name', 'contract_value_lkr',
            'contract_date', 'status', 'notes', 'created_at', 'updated_at',
            'payment_certs',
            'total_received_lkr', 'total_submitted_lkr', 'outstanding_lkr', 'received_pct',
        ]
        read_only_fields = ['id', 'site', 'created_at', 'updated_at']

    def get_total_received_lkr(self, obj):
        return obj.total_received_lkr

    def get_total_submitted_lkr(self, obj):
        return obj.total_submitted_lkr

    def get_outstanding_lkr(self, obj):
        return obj.outstanding_lkr

    def get_received_pct(self, obj):
        val = float(obj.contract_value_lkr)
        if val <= 0:
            return 0
        return round(obj.total_received_lkr / val * 100, 1)

    def get_site_name(self, obj):
        return obj.site.name


class SiteContractWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteContract
        fields = ['client_name', 'contract_value_lkr', 'contract_date', 'status', 'notes']


class SubcontractPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubcontractPayment
        fields = [
            'id', 'amount_lkr', 'payment_date', 'payment_method',
            'reference_no', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class SubcontractSerializer(serializers.ModelSerializer):
    payments        = SubcontractPaymentSerializer(many=True, read_only=True)
    total_paid_lkr  = serializers.SerializerMethodField()
    balance_lkr     = serializers.SerializerMethodField()
    paid_pct        = serializers.SerializerMethodField()

    class Meta:
        model = Subcontract
        fields = [
            'id', 'site', 'company_name', 'contact_person', 'contact_phone',
            'scope_of_work', 'contract_value_lkr', 'start_date', 'end_date',
            'status', 'notes', 'created_at', 'updated_at',
            'payments', 'total_paid_lkr', 'balance_lkr', 'paid_pct',
        ]
        read_only_fields = ['id', 'site', 'created_at', 'updated_at']

    def get_total_paid_lkr(self, obj):
        return obj.total_paid_lkr

    def get_balance_lkr(self, obj):
        return obj.balance_lkr

    def get_paid_pct(self, obj):
        val = float(obj.contract_value_lkr)
        if val <= 0:
            return 0
        return round(obj.total_paid_lkr / val * 100, 1)


class SubcontractWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subcontract
        fields = [
            'company_name', 'contact_person', 'contact_phone',
            'scope_of_work', 'contract_value_lkr',
            'start_date', 'end_date', 'status', 'notes',
        ]


class ContractSummarySerializer(serializers.ModelSerializer):
    """Compact shape for the Finance page cross-site overview."""
    site_name           = serializers.SerializerMethodField()
    total_received_lkr  = serializers.SerializerMethodField()
    outstanding_lkr     = serializers.SerializerMethodField()
    received_pct        = serializers.SerializerMethodField()
    subcontract_count   = serializers.SerializerMethodField()
    subcontract_committed_lkr = serializers.SerializerMethodField()
    subcontract_paid_lkr      = serializers.SerializerMethodField()

    class Meta:
        model = SiteContract
        fields = [
            'id', 'site', 'site_name', 'client_name',
            'contract_value_lkr', 'contract_date', 'status',
            'total_received_lkr', 'outstanding_lkr', 'received_pct',
            'subcontract_count', 'subcontract_committed_lkr', 'subcontract_paid_lkr',
        ]

    def get_site_name(self, obj):
        return obj.site.name

    def get_total_received_lkr(self, obj):
        return obj.total_received_lkr

    def get_outstanding_lkr(self, obj):
        return obj.outstanding_lkr

    def get_received_pct(self, obj):
        val = float(obj.contract_value_lkr)
        if val <= 0:
            return 0
        return round(obj.total_received_lkr / val * 100, 1)

    def get_subcontract_count(self, obj):
        return obj.site.subcontracts.filter(status__in=['pending', 'active']).count()

    def get_subcontract_committed_lkr(self, obj):
        from django.db.models import Sum
        result = obj.site.subcontracts.aggregate(t=Sum('contract_value_lkr'))['t'] or 0
        return float(result)

    def get_subcontract_paid_lkr(self, obj):
        from django.db.models import Sum
        from .models import SubcontractPayment
        sub_ids = obj.site.subcontracts.values_list('id', flat=True)
        result = SubcontractPayment.objects.filter(
            subcontract_id__in=sub_ids
        ).aggregate(t=Sum('amount_lkr'))['t'] or 0
        return float(result)
