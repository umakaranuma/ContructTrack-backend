from rest_framework import serializers
from .models import ProgressLog, ProgressPhoto


class ProgressPhotoSerializer(serializers.ModelSerializer):
    log_date = serializers.DateField(source='progress_log.log_date', read_only=True)

    class Meta:
        model = ProgressPhoto
        fields = ['id', 'photo_url', 'gps_lat', 'gps_lng', 'taken_at', 'caption', 'log_date']


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
    """Progress log shape expected by the owner-dashboard SiteDetail daily logs table."""
    date = serializers.DateField(source='log_date', read_only=True)
    manager = serializers.SerializerMethodField()
    materials_in = serializers.SerializerMethodField()
    materials_out = serializers.SerializerMethodField()
    workers = serializers.SerializerMethodField()
    total_wage = serializers.SerializerMethodField()

    class Meta:
        model = ProgressLog
        fields = [
            'id', 'log_date', 'date', 'stage', 'work_done_today',
            'manager', 'materials_in', 'materials_out', 'workers', 'total_wage',
            'created_at',
        ]

    def get_manager(self, obj):
        return obj.logged_by.full_name if obj.logged_by else None

    def get_materials_in(self, obj):
        return self.context.get('bills_by_date', {}).get(obj.log_date, 0)

    def get_materials_out(self, obj):
        return 0

    def get_workers(self, obj):
        summary = self.context.get('attendance_by_date', {}).get(obj.log_date)
        return summary.total_present if summary else 0

    def get_total_wage(self, obj):
        summary = self.context.get('attendance_by_date', {}).get(obj.log_date)
        return float(summary.total_wage_lkr) if summary else 0


class ProgressLogCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgressLog
        fields = [
            'log_date', 'stage', 'work_done_today',
            'blockers', 'blocker_note', 'tomorrow_status', 'is_synced',
        ]
