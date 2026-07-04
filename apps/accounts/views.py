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
    ManagerDetailSerializer,
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
    Client signals logout. Since token_blacklist app is not installed,
    the refresh token is simply discarded by the client. The access token
    expires naturally after 8 hours.
    """
    # Server-side blacklisting requires token_blacklist app which we excluded
    # to avoid extra tables. Logout is enforced client-side (delete tokens from storage).
    return success_response('Logged out successfully. Please delete your tokens.')


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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_account(request):
    """
    POST /api/auth/delete-account/
    Body: { password }
    Permanently deactivates the account after password confirmation.
    We soft-delete (deactivate) rather than hard-delete so historical
    site records (bills, attendance, progress) logged by this manager
    remain intact for the owner's audit trail.
    """
    password = request.data.get('password', '')
    if not password:
        return error_response('Your password is required to delete the account.', {}, 400)

    if not request.user.check_password(password):
        return error_response('Password is incorrect.', {}, 400)

    user = request.user
    # Deactivate and scrub the login so the account can no longer be used.
    user.is_active = False
    user.set_unusable_password()
    user.save(update_fields=['is_active', 'password'])

    # Detach the manager from any active site assignments.
    from apps.sites.models import SiteManager
    SiteManager.objects.filter(manager=user, is_active=True).update(is_active=False)

    return success_response('Your account has been deleted.')


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
    Sends an email invitation so a new person can register on the mobile app
    and join this owner's team. Email is sent via the configured SMTP backend.
    """
    from django.core.mail import send_mail
    from django.conf import settings as django_settings
    from apps.tenants.models import Tenant

    email = request.data.get('email', '').strip().lower()
    site_id = request.data.get('site_id', '').strip()
    personal_message = request.data.get('message', '').strip()

    if not email:
        return error_response('Email address is required.', {}, 400)

    # Resolve owner's company name for a personalised email
    tenant = Tenant.objects.filter(owner=request.user).first()
    company_name = tenant.company_name if tenant else request.user.full_name

    site_name = ''
    if site_id:
        from apps.sites.models import Site
        site = Site.objects.filter(id=site_id, tenant=tenant).first()
        if site:
            site_name = site.name

    # Build plain-text invitation email
    register_url = 'https://constructtrack.lk/register-manager'
    site_line = f'\nYou will be pre-assigned to site: {site_name}' if site_name else ''
    personal_line = (
        f'\nPersonal message from {request.user.full_name}:\n"{personal_message}"\n'
        if personal_message else ''
    )

    subject = f"You're invited to join {company_name} on ConstructTrack"
    body = (
        f"Hello,\n\n"
        f"{request.user.full_name} from {company_name} has invited you to join their "
        f"ConstructTrack account as a Site Manager.{site_line}\n"
        f"{personal_line}\n"
        f"To get started:\n"
        f"1. Download the ConstructTrack mobile app\n"
        f"2. Register using this exact email address: {email}\n"
        f"   (Registration link: {register_url})\n"
        f"3. Share your Manager Reference Code (MGR-XXXX) with {request.user.full_name}\n"
        f"   so they can confirm your access.\n\n"
        f"If you did not expect this invitation, you can safely ignore this email.\n\n"
        f"---\nConstructTrack — Construction Site Management for Sri Lanka\n"
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info('Manager invite sent to %s by owner %s', email, request.user.email)
        return success_response('Invitation email sent successfully.', {
            'email': email,
            'site': site_name or None,
        })
    except Exception as exc:
        logger.exception('Failed to send manager invite email to %s: %s', email, exc)
        return error_response('Could not send invitation email. Please check SMTP settings.', {}, 500)


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


def _get_owner_tenant(user):
    from apps.tenants.models import Tenant
    return Tenant.objects.filter(owner=user).first()


def _manager_in_tenant(manager, tenant):
    if not tenant:
        return False
    from apps.sites.models import SiteManager
    return SiteManager.objects.filter(
        manager=manager, site__tenant=tenant, is_active=True,
    ).exists()


@api_view(['GET', 'DELETE'])
@permission_classes([IsOwner])
def get_manager(request, manager_id):
    """
    GET    /api/managers/:id/ — detail view for a single manager
    DELETE /api/managers/:id/ — remove manager from all tenant sites
    """
    try:
        manager = User.objects.get(id=manager_id, user_type='manager')
    except User.DoesNotExist:
        return error_response('Manager not found.', {}, 404)

    tenant = _get_owner_tenant(request.user)
    if not tenant:
        return error_response('Tenant not found.', {}, 404)
    if not _manager_in_tenant(manager, tenant):
        return error_response('Manager not found.', {}, 404)

    if request.method == 'DELETE':
        from apps.sites.models import SiteManager
        from django.utils import timezone as tz

        SiteManager.objects.filter(
            manager=manager, site__tenant=tenant, is_active=True,
        ).update(is_active=False, removed_at=tz.now())
        return success_response('Manager removed from all sites.')

    return success_response(
        'Manager retrieved.',
        ManagerDetailSerializer(manager, context={'tenant': tenant}).data,
    )


@api_view(['GET'])
@permission_classes([IsOwner])
def lookup_manager(request):
    """
    GET /api/managers/lookup/?ref_code=MGR-1234  — lookup by reference code
    GET /api/managers/lookup/?email=x@y.com      — lookup by email
    Unified endpoint matching what the frontend services call.
    """
    ref_code = request.query_params.get('ref_code', '').strip().upper()
    email    = request.query_params.get('email', '').strip().lower()

    if ref_code:
        try:
            manager = User.objects.get(reference_code=ref_code, user_type='manager')
        except User.DoesNotExist:
            return error_response('No manager found with that reference code.', {}, 404)
        return success_response('Manager found.', ManagerListSerializer(manager).data)

    if email:
        managers = User.objects.filter(email__icontains=email, user_type='manager')
        return success_response('Search results.', ManagerListSerializer(managers, many=True).data)

    return error_response('Provide ref_code or email query parameter.', {}, 400)


@api_view(['POST'])
@permission_classes([IsOwner])
def add_manager(request):
    """
    POST /api/managers/add/
    Adds an existing manager to the owner's tenant by assigning them to one or more sites.
    Body: { manager_id: uuid, site_ids: [uuid, ...] }
    """
    from apps.tenants.models import Tenant
    from apps.sites.models import Site, SiteManager

    tenant = Tenant.objects.filter(owner=request.user).first()
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    manager_id = request.data.get('manager_id')
    site_ids   = request.data.get('site_ids', [])

    if not manager_id:
        return error_response('manager_id is required.', {}, 400)

    try:
        manager = User.objects.get(id=manager_id, user_type='manager')
    except User.DoesNotExist:
        return error_response('Manager not found.', {}, 404)

    assigned = []
    for sid in site_ids:
        try:
            site = Site.objects.get(id=sid, tenant=tenant)
            assignment, _ = SiteManager.objects.get_or_create(
                site=site, manager=manager, defaults={'is_active': True}
            )
            assignment.is_active = True
            assignment.removed_at = None
            assignment.save()
            assigned.append(str(site.id))
        except Site.DoesNotExist:
            pass

    return success_response('Manager added.', {
        'manager_id': str(manager.id),
        'assigned_sites': assigned,
    }, 201)


@api_view(['POST'])
@permission_classes([IsOwner])
def unassign_manager(request, manager_id):
    """
    POST /api/managers/:id/unassign/
    Body: { site_id: uuid }
    Removes a manager assignment from one site.
    """
    from apps.tenants.models import Tenant
    from apps.sites.models import SiteManager
    from django.utils import timezone as tz

    tenant = Tenant.objects.filter(owner=request.user).first()
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    site_id = request.data.get('site_id')
    if not site_id:
        return error_response('site_id is required.', {}, 400)

    updated = SiteManager.objects.filter(
        manager_id=manager_id,
        site_id=site_id,
        site__tenant=tenant,
        is_active=True,
    ).update(is_active=False, removed_at=tz.now())

    if not updated:
        return error_response('Assignment not found.', {}, 404)

    return success_response('Manager removed from site.')


@api_view(['DELETE'])
@permission_classes([IsOwner])
def remove_manager(request, manager_id):
    """
    DELETE /api/managers/:id/
    Removes the manager from ALL sites under this tenant (soft-delete assignments).
    Does not delete the manager user account.
    """
    from apps.tenants.models import Tenant
    from apps.sites.models import SiteManager
    from django.utils import timezone as tz

    tenant = Tenant.objects.filter(owner=request.user).first()
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    SiteManager.objects.filter(
        manager_id=manager_id,
        site__tenant=tenant,
        is_active=True,
    ).update(is_active=False, removed_at=tz.now())

    return success_response('Manager removed from all sites.')


@api_view(['GET'])
@permission_classes([IsOwner])
def manager_activity(request, manager_id):
    """GET /api/managers/:id/activity/ — unified recent activity for a manager."""
    from apps.sites.models import SiteManager
    from apps.progress.models import ProgressLog
    from apps.bills.models import Bill
    from apps.attendance.models import AttendanceSummary

    try:
        manager = User.objects.get(id=manager_id, user_type='manager')
    except User.DoesNotExist:
        return error_response('Manager not found.', {}, 404)

    tenant = _get_owner_tenant(request.user)
    if not tenant or not _manager_in_tenant(manager, tenant):
        return error_response('Manager not found.', {}, 404)

    assigned_site_ids = list(
        SiteManager.objects.filter(
            manager=manager, site__tenant=tenant, is_active=True,
        ).values_list('site_id', flat=True)
    )

    activities = []

    for log in ProgressLog.objects.filter(
        site_id__in=assigned_site_ids, logged_by=manager,
    ).select_related('site').order_by('-created_at')[:20]:
        summary = (log.work_done_today or 'Progress update')[:120]
        activities.append({
            'id': f'log-{log.id}',
            'type': 'progress_log',
            'site_id': str(log.site_id),
            'site_name': log.site.name,
            'description': f'Submitted daily log — {summary}',
            'timestamp': log.created_at.isoformat(),
        })

    for bill in Bill.objects.filter(
        site_id__in=assigned_site_ids, logged_by=manager,
    ).select_related('site').order_by('-created_at')[:20]:
        activities.append({
            'id': f'bill-{bill.id}',
            'type': 'bill',
            'site_id': str(bill.site_id),
            'site_name': bill.site.name,
            'description': f'Logged {bill.material_type} bill from {bill.supplier_name}',
            'timestamp': bill.created_at.isoformat(),
        })

    for att in AttendanceSummary.objects.filter(
        site_id__in=assigned_site_ids, submitted_by=manager,
    ).select_related('site').order_by('-submitted_at')[:20]:
        activities.append({
            'id': f'att-{att.id}',
            'type': 'attendance',
            'site_id': str(att.site_id),
            'site_name': att.site.name,
            'description': f'Submitted attendance — {att.total_present} workers present',
            'timestamp': att.submitted_at.isoformat(),
        })

    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    limit = int(request.query_params.get('limit', 30))
    return success_response('Activity retrieved.', activities[:limit])


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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    POST /api/auth/change-password/
    Body: { current_password, new_password }
    """
    current  = request.data.get('current_password', '')
    new_pwd  = request.data.get('new_password', '')

    if not current or not new_pwd:
        return error_response('current_password and new_password are required.', {}, 400)

    if len(new_pwd) < 8:
        return error_response('New password must be at least 8 characters.', {}, 400)

    if not request.user.check_password(current):
        return error_response('Current password is incorrect.', {}, 400)

    request.user.set_password(new_pwd)
    request.user.save(update_fields=['password'])
    return success_response('Password changed successfully.')
