from rest_framework import serializers
from .models import Worker, DailyAttendance, AttendanceSummary


class WorkerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Worker
        fields = [
            'id', 'site', 'full_name', 'role', 'nic', 'phone',
            'daily_rate_lkr', 'contract_type', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'site', 'created_at']


class WorkerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Worker
        fields = ['full_name', 'role', 'nic', 'phone', 'daily_rate_lkr', 'contract_type']


class DailyAttendanceSerializer(serializers.ModelSerializer):
    worker_name = serializers.SerializerMethodField()

    class Meta:
        model = DailyAttendance
        fields = [
            'id', 'worker', 'worker_name', 'log_date', 'status',
            'overtime_hours', 'daily_rate_lkr', 'total_earned_lkr',
            'is_paid', 'is_rain_day', 'is_synced', 'created_at' if False else 'log_date',
        ]
        # Use log_date as list key to avoid duplicate field
        fields = [
            'id', 'worker', 'worker_name', 'log_date', 'status',
            'overtime_hours', 'daily_rate_lkr', 'total_earned_lkr',
            'is_paid', 'is_rain_day', 'is_synced',
        ]
        read_only_fields = ['id', 'worker_name', 'daily_rate_lkr', 'total_earned_lkr']

    def get_worker_name(self, obj):
        return obj.worker.full_name


class AttendanceBulkCreateSerializer(serializers.Serializer):
    """
    Used by mobile to submit a full day's attendance in one request.
    Each entry is {worker_id, status, overtime_hours, is_rain_day}.
    """
    log_date = serializers.DateField()
    is_rain_day = serializers.BooleanField(default=False)
    records = serializers.ListField(child=serializers.DictField())


class AttendanceSummarySerializer(serializers.ModelSerializer):
    site_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceSummary
        fields = [
            'id', 'site', 'site_name', 'log_date',
            'total_present', 'total_half', 'total_absent',
            'total_wage_lkr', 'submitted_at',
        ]

    def get_site_name(self, obj):
        return obj.site.name
