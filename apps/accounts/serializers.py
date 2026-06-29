"""
Serializers for account-related operations.
Separate serializers for registration vs profile to control which fields are writable.
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User
from apps.core.utils import generate_manager_reference_code


class UserProfileSerializer(serializers.ModelSerializer):
    """Read-only profile view — returned on /me/ and inside JWT payloads."""

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'phone', 'user_type',
            'admin_role', 'reference_code', 'nic', 'profile_photo_url',
            'is_active', 'is_suspended', 'created_at',
        ]
        read_only_fields = ['id', 'email', 'user_type', 'admin_role', 'reference_code', 'created_at']


class UserUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/auth/me/ — limited fields the user may self-edit."""

    class Meta:
        model = User
        fields = ['full_name', 'phone', 'nic', 'profile_photo_url']


class OwnerRegistrationSerializer(serializers.Serializer):
    """
    POST /api/auth/register/
    Registers a company owner + creates their tenant in one atomic operation.
    Tenant creation logic lives in the view to keep the serializer thin.
    """
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    company_name = serializers.CharField(max_length=255)
    package_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value.lower()

    def validate_password(self, value):
        validate_password(value)  # runs Django's built-in password validators
        return value


class ManagerRegistrationSerializer(serializers.Serializer):
    """
    POST /api/auth/register-mobile/
    Managers self-register; they are not attached to a tenant until an owner assigns them.
    reference_code is auto-generated here.
    """
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    nic = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value.lower()

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            full_name=validated_data['full_name'],
            password=validated_data['password'],
            phone=validated_data.get('phone', ''),
            nic=validated_data.get('nic', ''),
            user_type='manager',
            reference_code=generate_manager_reference_code(),
        )
        return user


class LoginSerializer(serializers.Serializer):
    """POST /api/auth/login/"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class AdminLoginSerializer(serializers.Serializer):
    """POST /api/admin/auth/login/ — same fields, separate serializer for clarity."""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class ManagerListSerializer(serializers.ModelSerializer):
    """Compact manager listing for the owner's manager management screen."""
    # Aliases expected by the owner-dashboard ManagerTable component
    name         = serializers.CharField(source='full_name', read_only=True)
    ref_code     = serializers.CharField(source='reference_code', read_only=True)
    sites        = serializers.SerializerMethodField()
    last_active  = serializers.SerializerMethodField()
    status       = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'name', 'email', 'phone',
            'reference_code', 'ref_code',
            'is_active', 'is_suspended',
            'sites', 'last_active', 'status',
            'created_at',
        ]

    def get_sites(self, obj):
        from apps.sites.models import SiteManager
        return list(
            SiteManager.objects.filter(manager=obj, is_active=True)
            .select_related('site')
            .values_list('site__name', flat=True)
        )

    def get_last_active(self, obj):
        from apps.progress.models import ProgressLog
        log = ProgressLog.objects.filter(logged_by=obj).order_by('-log_date', '-created_at').first()
        if log:
            return log.created_at.isoformat()
        return obj.created_at.isoformat()

    def get_status(self, obj):
        if obj.is_suspended:
            return 'suspended'
        return 'active' if obj.is_active else 'inactive'


class ManagerDetailSerializer(serializers.ModelSerializer):
    """Full manager profile for the owner dashboard detail page."""
    name = serializers.CharField(source='full_name', read_only=True)
    ref_code = serializers.CharField(source='reference_code', read_only=True)
    status = serializers.SerializerMethodField()
    last_active = serializers.SerializerMethodField()
    assigned_sites = serializers.SerializerMethodField()
    experience = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'name', 'email', 'phone', 'nic',
            'reference_code', 'ref_code', 'profile_photo_url',
            'is_active', 'is_suspended', 'status', 'last_active',
            'assigned_sites', 'experience', 'created_at',
        ]

    def _tenant_site_ids(self, obj):
        tenant = self.context.get('tenant')
        from apps.sites.models import SiteManager
        qs = SiteManager.objects.filter(manager=obj, is_active=True)
        if tenant:
            qs = qs.filter(site__tenant=tenant)
        return list(qs.values_list('site_id', flat=True))

    def get_assigned_sites(self, obj):
        from apps.sites.models import SiteManager
        tenant = self.context.get('tenant')
        qs = SiteManager.objects.filter(manager=obj, is_active=True).select_related('site')
        if tenant:
            qs = qs.filter(site__tenant=tenant)
        return [
            {
                'id': str(sm.site.id),
                'name': sm.site.name,
                'location': sm.site.address or '',
                'stage': sm.site.current_stage,
                'status': 'active' if sm.site.is_active else 'inactive',
                'assigned_at': sm.assigned_at.isoformat() if sm.assigned_at else None,
            }
            for sm in qs
        ]

    def get_last_active(self, obj):
        from apps.progress.models import ProgressLog
        site_ids = self._tenant_site_ids(obj)
        log = ProgressLog.objects.filter(
            logged_by=obj, site_id__in=site_ids,
        ).order_by('-created_at').first()
        if log:
            return log.created_at.isoformat()
        if obj.last_login:
            return obj.last_login.isoformat()
        return obj.created_at.isoformat()

    def get_status(self, obj):
        if obj.is_suspended:
            return 'suspended'
        return 'active' if obj.is_active else 'inactive'

    def get_experience(self, obj):
        from django.utils import timezone
        from apps.progress.models import ProgressLog
        from apps.bills.models import Bill
        from apps.attendance.models import AttendanceSummary

        site_ids = self._tenant_site_ids(obj)
        if not site_ids:
            days = (timezone.now() - obj.created_at).days
            return {
                'member_since': obj.created_at.date().isoformat(),
                'days_as_manager': days,
                'total_sites': 0,
                'total_progress_logs': 0,
                'total_bills_logged': 0,
                'total_attendance_submissions': 0,
            }

        total_logs = ProgressLog.objects.filter(logged_by=obj, site_id__in=site_ids).count()
        total_bills = Bill.objects.filter(logged_by=obj, site_id__in=site_ids).count()
        total_attendance = AttendanceSummary.objects.filter(
            submitted_by=obj, site_id__in=site_ids,
        ).count()
        days = (timezone.now() - obj.created_at).days

        return {
            'member_since': obj.created_at.date().isoformat(),
            'days_as_manager': days,
            'total_sites': len(site_ids),
            'total_progress_logs': total_logs,
            'total_bills_logged': total_bills,
            'total_attendance_submissions': total_attendance,
        }
