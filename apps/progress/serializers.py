from rest_framework import serializers
from .models import ProgressLog, ProgressPhoto


class DailyLogAttendanceRowSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    worker_id = serializers.UUIDField()
    worker_name = serializers.CharField()
    role = serializers.CharField()
    status = serializers.CharField()
    overtime_hours = serializers.DecimalField(max_digits=4, decimal_places=1)
    total_earned_lkr = serializers.DecimalField(max_digits=12, decimal_places=2)
    is_paid = serializers.BooleanField()


class DailyLogBillRowSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    supplier_name = serializers.CharField()
    material_type = serializers.CharField()
    material_label = serializers.CharField()
    total_amount_lkr = serializers.DecimalField(max_digits=14, decimal_places=2)
    bill_photo_url = serializers.URLField()
    payment_method = serializers.CharField()


class ProgressPhotoSerializer(serializers.ModelSerializer):
    log_date = serializers.DateField(source='progress_log.log_date', read_only=True)

    class Meta:
        model = ProgressPhoto
        fields = ['id', 'photo_url', 'gps_lat', 'gps_lng', 'taken_at', 'caption', 'log_date']


class DailyLogDetailSerializer(serializers.Serializer):
    """Full daily log view — log entry plus same-day attendance, bills, and photos."""
    id = serializers.UUIDField()
    log_date = serializers.DateField()
    stage = serializers.CharField()
    work_done_today = serializers.CharField()
    tomorrow_status = serializers.CharField()
    blockers = serializers.CharField(allow_null=True)
    blocker_note = serializers.CharField(allow_null=True)
    manager = serializers.CharField(allow_null=True)
    site_name = serializers.CharField()
    created_at = serializers.DateTimeField()
    attendance = DailyLogAttendanceRowSerializer(many=True)
    attendance_summary = serializers.DictField(allow_null=True)
    bills = DailyLogBillRowSerializer(many=True)
    photos = ProgressPhotoSerializer(many=True)


class ProgressLogSerializer(serializers.ModelSerializer):
    photos = ProgressPhotoSerializer(many=True, read_only=True)
    logged_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ProgressLog
        fields = [
            'id', 'site', 'logged_by', 'logged_by_name', 'log_date', 'stage',
            'work_done_today', 'blockers', 'blocker_note', 'tomorrow_status',
            'is_synced', 'created_at', 'photos',
        ]
        read_only_fields = ['id', 'site', 'logged_by', 'logged_by_name', 'created_at']

    def get_logged_by_name(self, obj):
        return obj.logged_by.full_name if obj.logged_by else None


class SiteDailyLogSerializer(serializers.ModelSerializer):
    """List-row shape for the owner-dashboard daily logs table."""
    date = serializers.DateField(source='log_date', read_only=True)
    manager = serializers.SerializerMethodField()

    class Meta:
        model = ProgressLog
        fields = [
            'id', 'log_date', 'date', 'stage', 'work_done_today', 'tomorrow_status',
            'manager', 'created_at',
        ]

    def get_manager(self, obj):
        return obj.logged_by.full_name if obj.logged_by else None


class ProgressLogCreateSerializer(serializers.ModelSerializer):
    stage = serializers.CharField(max_length=30, required=False, allow_blank=True)
    tomorrow_status = serializers.CharField(max_length=100, required=False, default='working')
    blockers = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = ProgressLog
        fields = [
            'log_date', 'stage', 'work_done_today',
            'blockers', 'blocker_note', 'tomorrow_status', 'is_synced',
        ]
