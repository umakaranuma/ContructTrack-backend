from rest_framework import serializers
from .models import Site, SiteManager, Alert


class SiteSerializer(serializers.ModelSerializer):
    manager_count       = serializers.SerializerMethodField()
    # Aliases used by the owner dashboard frontend
    location            = serializers.SerializerMethodField()
    stage               = serializers.CharField(source='current_stage', read_only=True)
    budget              = serializers.DecimalField(source='budget_lkr', max_digits=14, decimal_places=2, allow_null=True, read_only=True)
    manager_name        = serializers.SerializerMethodField()
    manager_last_seen   = serializers.SerializerMethodField()
    material_usage_pct  = serializers.SerializerMethodField()
    workers_today       = serializers.SerializerMethodField()
    monthly_spend       = serializers.SerializerMethodField()
    status              = serializers.SerializerMethodField()

    class Meta:
        model = Site
        fields = [
            'id', 'name', 'address', 'location', 'project_type',
            'current_stage', 'stage',
            'budget_lkr', 'budget',
            'start_date', 'end_date', 'is_active', 'status',
            'manager_count', 'manager_name', 'manager_last_seen',
            'material_usage_pct', 'workers_today', 'monthly_spend',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_manager_count(self, obj):
        return obj.site_managers.filter(is_active=True).count()

    def get_location(self, obj):
        return obj.address or ''

    def get_manager_name(self, obj):
        sm = obj.site_managers.filter(is_active=True).select_related('manager').first()
        if sm:
            return sm.manager.full_name or sm.manager.email or 'Manager'
        return 'No manager assigned'

    def get_manager_last_seen(self, obj):
        from apps.progress.models import ProgressLog
        log = ProgressLog.objects.filter(site=obj).order_by('-log_date', '-created_at').first()
        if log:
            return log.created_at.isoformat()
        return obj.created_at.isoformat()

    def get_material_usage_pct(self, obj):
        from apps.bills.models import Bill
        from django.db.models import Sum
        from django.utils import timezone
        now = timezone.now()
        spent = Bill.objects.filter(
            site=obj, log_date__year=now.year, log_date__month=now.month,
        ).aggregate(t=Sum('total_amount_lkr'))['t'] or 0
        if obj.budget_lkr and obj.budget_lkr > 0:
            return min(int(float(spent) / float(obj.budget_lkr) * 100), 100)
        return 0

    def get_workers_today(self, obj):
        from apps.attendance.models import DailyAttendance
        from django.utils import timezone
        return DailyAttendance.objects.filter(
            site=obj, log_date=timezone.now().date(), status__in=['present', 'half'],
        ).count()

    def get_monthly_spend(self, obj):
        from apps.bills.models import Bill
        from django.db.models import Sum
        from django.utils import timezone
        now = timezone.now()
        result = Bill.objects.filter(
            site=obj, log_date__year=now.year, log_date__month=now.month,
        ).aggregate(t=Sum('total_amount_lkr'))['t'] or 0
        return float(result)

    def get_status(self, obj):
        return 'active' if obj.is_active else 'inactive'


class SiteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = [
            'name', 'address', 'project_type', 'current_stage',
            'budget_lkr', 'start_date', 'end_date',
        ]


class AlertSerializer(serializers.ModelSerializer):
    severity     = serializers.SerializerMethodField()
    acknowledged = serializers.BooleanField(source='is_resolved', read_only=True)
    # 'type' alias expected by AlertDrawer.jsx TYPE_LABELS map
    type         = serializers.CharField(source='alert_type', read_only=True)
    site_name    = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            'id', 'alert_type', 'type', 'message', 'is_resolved', 'acknowledged',
            'severity', 'site_name', 'resolved_at', 'created_at',
        ]

    def get_severity(self, obj):
        danger_types = {'material_cap', 'anomaly'}
        return 'danger' if obj.alert_type in danger_types else 'warning'

    def get_site_name(self, obj):
        return obj.site.name if obj.site_id else ''
