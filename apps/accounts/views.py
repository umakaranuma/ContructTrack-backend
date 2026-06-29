"""
Auth views: register, login, logout, JWT refresh, profile read/update.
Managers and owners share some endpoints but diverge on registration and data access.
"""
import logging
from django.db import transaction
from django.contrib.auth import authenticate
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from apps.core.utils import success_response, error_response
from apps.core.permissions import IsOwner, IsAdminUser
from .models import User
from .serializers import (
    OwnerRegistrationSerializer,
    ManagerRegistrationSerializer,
    LoginSerializer,
    UserProfileSerializer,
    UserUpdateSerializer,
    ManagerListSerializer,
)

logger = logging.getLogger(__name__)


class AuthRateThrottle(AnonRateThrottle):
    # Stricter rate limit for auth endpoints to slow brute-force attacks
    rate = '5/min'
    scope = 'auth'


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def register_owner(request):
    """
    Owner registration + tenant creation in one atomic operation.
    If any step fails (e.g. package lookup), the whole thing rolls back.
    """
    serializer = OwnerRegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)

    data = serializer.validated_data

    try:
        with transaction.atomic():
            # Import here to avoid circular dependency at module level
            from apps.tenants.models import Tenant, Package

            user = User.objects.create_user(
                email=data['email'],
                full_name=data['full_name'],
                password=data['password'],
                phone=data.get('phone', ''),
                user_type='owner',
            )

            # Find the selected package; fall back to Lite if none provided
            package = None
            if data.get('package_id'):
                try:
                    package = Package.objects.get(id=data['package_id'], is_active=True)
                except Package.DoesNotExist:
                    pass
            if not package:
                package = Package.objects.filter(is_active=True).order_by('price_lkr').first()

            from django.utils import timezone
            import datetime

            # Start with trial if package has trial days
            trial_days = package.trial_days if package else 14
            now = timezone.now()
            tenant = Tenant.objects.create(
                company_name=data['company_name'],
                owner=user,
                package=package,
                status='trial',
                trial_start=now,
                trial_end=now + datetime.timedelta(days=trial_days),
                subscription_start=now,
                subscription_end=now + datetime.timedelta(days=trial_days),
            )

        token = RefreshToken.for_user(user)
        return success_response('Registration successful.', {
            'access_token': str(token.access_token),
            'refresh_token': str(token),
            'user': UserProfileSerializer(user).data,
            'tenant_id': str(tenant.id),
        }, 201)

    except Exception as exc:
        logger.exception('Owner registration failed: %s', exc)
        return error_response('Registration failed. Please try again.', {}, 500)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def register_manager(request):
    """
    Manager self-registration (mobile app).
    No tenant is assigned yet — the owner invites and assigns separately.
    """
    serializer = ManagerRegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)

    user = serializer.save()
    token = RefreshToken.for_user(user)
    return success_response('Manager account created.', {
        'access_token': str(token.access_token),
        'refresh_token': str(token),
        'user': UserProfileSerializer(user).data,
    }, 201)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthRateThrottle])
def login_view(request):
    """
    JWT login for both owners and managers.
    Returns both access + refresh tokens so the client can stay logged in.
    """
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)

    user = authenticate(
        request,
        username=serializer.validated_data['email'],
        password=serializer.validated_data['password'],
    )
    if not user:
        return error_response('Invalid email or password.', {}, 401)

    if not user.is_active:
        return error_response('Your account has been deactivated.', {}, 403)

    if user.is_suspended:
        return error_response('Your account has been suspended. Please contact support.', {}, 403)

    # Admin users should use /api/admin/auth/login/ — enforce separation
    if user.user_type == 'admin':
        return error_response('Admin accounts must use the admin login endpoint.', {}, 403)

    token = RefreshToken.for_user(user)

    # Attach tenant info to response for owners so the client stores tenant_id
    extra = {}
    if user.user_type == 'owner':
        from apps.tenants.models import Tenant
        tenant = Tenant.objects.filter(owner=user).first()
        if tenant:
            extra['tenant_id'] = str(tenant.id)
            extra['tenant_status'] = tenant.status

    return success_response('Login successful.', {
        'access_token': str(token.access_token),
        'refresh_token': str(token),
        'user': UserProfileSerializer(user).data,
        **extra,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Blacklists the refresh token so it can no longer be used.
    The access token expires naturally (8h) — we don't store it server-side.
    """
    try:
        refresh_token = request.data.get('refresh_token')
        if not refresh_token:
            return error_response('refresh_token is required.', {}, 400)
        token = RefreshToken(refresh_token)
        token.blacklist()
        return success_response('Logged out successfully.')
    except TokenError:
        return error_response('Invalid or already-expired token.', {}, 400)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """
    GET  — return authenticated user's profile
    PATCH — allow self-editing of non-sensitive fields
    """
    if request.method == 'GET':
        return success_response('Profile retrieved.', UserProfileSerializer(request.user).data)

    # PATCH
    serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)
    serializer.save()
    return success_response('Profile updated.', UserProfileSerializer(request.user).data)


# ---------------------------------------------------------------------------
# Manager management (owner-facing)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsOwner])
def list_managers(request):
    """GET /api/managers/ — owner sees all managers registered on the platform."""
    from apps.sites.models import SiteManager
    from apps.tenants.models import Tenant

    tenant = Tenant.objects.filter(owner=request.user).first()
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    # Only show managers assigned to this tenant's sites
    assigned_user_ids = SiteManager.objects.filter(
        site__tenant=tenant, is_active=True
    ).values_list('manager_id', flat=True)

    managers = User.objects.filter(
        user_type='manager',
        id__in=assigned_user_ids,
    )
    return success_response('Managers retrieved.', ManagerListSerializer(managers, many=True).data)


@api_view(['GET'])
@permission_classes([IsOwner])
def resolve_manager_by_code(request):
    """GET /api/managers/resolve/?code=MGR-4821 — owner looks up a manager before assigning."""
    code = request.query_params.get('code', '').strip().upper()
    if not code:
        return error_response('code query parameter is required.', {}, 400)
    try:
        manager = User.objects.get(reference_code=code, user_type='manager')
    except User.DoesNotExist:
        return error_response('No manager found with that reference code.', {}, 404)
    return success_response('Manager found.', ManagerListSerializer(manager).data)


@api_view(['GET'])
@permission_classes([IsOwner])
def search_manager_by_email(request):
    """GET /api/managers/search/?email=x"""
    email = request.query_params.get('email', '').strip().lower()
    if not email:
        return error_response('email query parameter is required.', {}, 400)
    managers = User.objects.filter(email__icontains=email, user_type='manager')
    return success_response('Search results.', ManagerListSerializer(managers, many=True).data)


@api_view(['POST'])
@permission_classes([IsOwner])
def invite_manager(request):
    """
    POST /api/managers/invite/
    Placeholder — in production this sends an SMS/email with a sign-up link.
    For now it records intent and returns instructions.
    """
    phone = request.data.get('phone', '')
    email = request.data.get('email', '')
    if not phone and not email:
        return error_response('Provide at least phone or email to send invite.', {}, 400)
    # TODO: trigger Celery task to send WhatsApp/SMS invite via Dialog LK
    return success_response('Invitation queued. Manager will receive instructions shortly.', {
        'phone': phone,
        'email': email,
    })


@api_view(['POST'])
@permission_classes([IsOwner])
def assign_manager(request, manager_id):
    """
    POST /api/managers/:id/assign/
    Assigns an existing manager to one of the owner's sites.
    """
    from apps.tenants.models import Tenant
    from apps.sites.models import Site, SiteManager

    tenant = Tenant.objects.filter(owner=request.user).first()
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    try:
        manager = User.objects.get(id=manager_id, user_type='manager')
    except User.DoesNotExist:
        return error_response('Manager not found.', {}, 404)

    site_id = request.data.get('site_id')
    if not site_id:
        return error_response('site_id is required.', {}, 400)

    try:
        site = Site.objects.get(id=site_id, tenant=tenant)
    except Site.DoesNotExist:
        return error_response('Site not found in your tenant.', {}, 404)

    assignment, created = SiteManager.objects.get_or_create(
        site=site,
        manager=manager,
        defaults={'is_active': True},
    )
    if not created:
        assignment.is_active = True
        assignment.removed_at = None
        assignment.save()

    return success_response('Manager assigned to site.', {
        'site_id': str(site.id),
        'manager_id': str(manager.id),
    }, 201)


@api_view(['DELETE'])
@permission_classes([IsOwner])
def remove_manager_from_site(request, manager_id, site_id):
    """DELETE /api/managers/:id/assign/:siteId/"""
    from apps.tenants.models import Tenant
    from apps.sites.models import SiteManager
    from django.utils import timezone

    tenant = Tenant.objects.filter(owner=request.user).first()
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    updated = SiteManager.objects.filter(
        manager_id=manager_id,
        site_id=site_id,
        site__tenant=tenant,
        is_active=True,
    ).update(is_active=False, removed_at=timezone.now())

    if not updated:
        return error_response('Assignment not found.', {}, 404)

    return success_response('Manager removed from site.')


@api_view(['PATCH'])
@permission_classes([IsOwner])
def deactivate_manager(request, manager_id):
    """PATCH /api/managers/:id/deactivate/"""
    try:
        manager = User.objects.get(id=manager_id, user_type='manager')
    except User.DoesNotExist:
        return error_response('Manager not found.', {}, 404)

    manager.is_active = False
    manager.save(update_fields=['is_active'])
    return success_response('Manager deactivated.')
