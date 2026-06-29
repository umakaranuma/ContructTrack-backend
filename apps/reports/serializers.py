from rest_framework import serializers
from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            'id', 'report_type', 'site', 'date_from', 'date_to',
            'format', 'file_url', 'status', 'created_at',
        ]
        read_only_fields = ['id', 'file_url', 'status', 'created_at']


class ReportGenerateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['report_type', 'site', 'date_from', 'date_to', 'format']
