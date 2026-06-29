from rest_framework import serializers
from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    site_name = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'id', 'report_type', 'site', 'site_name', 'date_from', 'date_to',
            'format', 'file_url', 'status', 'created_at',
        ]
        read_only_fields = ['id', 'file_url', 'status', 'created_at']

    def get_site_name(self, obj):
        return obj.site.name if obj.site_id else 'All Sites'


class ReportGenerateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['report_type', 'site', 'date_from', 'date_to', 'format']
