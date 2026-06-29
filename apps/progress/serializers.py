from rest_framework import serializers
from .models import ProgressLog, ProgressPhoto


class ProgressPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgressPhoto
        fields = ['id', 'photo_url', 'gps_lat', 'gps_lng', 'taken_at', 'caption']


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


class ProgressLogCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgressLog
        fields = [
            'log_date', 'stage', 'work_done_today',
            'blockers', 'blocker_note', 'tomorrow_status', 'is_synced',
        ]
