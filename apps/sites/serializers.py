from rest_framework import serializers
from .models import Site, SiteManager, Alert


class SiteSerializer(serializers.ModelSerializer):
    manager_count = serializers.SerializerMethodField()

    class Meta:
        model = Site
        fields = [
            'id', 'name', 'address', 'project_type', 'current_stage',
            'budget_lkr', 'start_date', 'end_date', 'is_active',
            'manager_count', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_manager_count(self, obj):
        return obj.site_managers.filter(is_active=True).count()


class SiteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = [
            'name', 'address', 'project_type', 'current_stage',
            'budget_lkr', 'start_date', 'end_date',
        ]


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = [
            'id', 'alert_type', 'message', 'is_resolved',
            'resolved_at', 'created_at',
        ]
