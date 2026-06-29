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

    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'phone', 'reference_code',
                  'is_active', 'is_suspended', 'created_at']
