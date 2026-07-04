"""
Internal admin panel views — for ConstructTrack staff only.
Role hierarchy: super_admin > support > finance
super_admin: all operations
support: read + limited write (no financial ops)
finance: payments module only
"""
import logging
from datetime import timedelta, date
from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.utils import success_response, error_response, paginate_queryset
from apps.core.permissions import IsAdminUser, IsSuperAdmin, IsFinanceAdmin
from apps.accounts.models import User
from apps.accounts.serializers import UserProfileSerializer, AdminLoginSerializer, ManagerListSerializer
from apps.tenants.models import Tenant, Package, TenantSubscriptionLog
from apps.tenants.serializers import TenantSerializer, PackageSerializer, SubscriptionLogSerializer
from apps.payments.models import Payment
from apps.payments.serializers import PaymentSerializer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Admin Auth
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([])  # no auth required — this is the login endpoint
def admin_login(request):
    """POST /api/admin/auth/login/ — admin-only login, rejects non-admin users."""
    serializer = AdminLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)

    user = authenticate(
        request,
        username=serializer.validated_data['email'],
        password=serializer.validated_data['password'],
    )
    if not user:
        return error_response('Invalid credentials.', {}, 401)

    if user.user_type != 'admin':
        # Security: never reveal that a non-admin account exists with this email
        return error_response('Invalid credentials.', {}, 401)

    if not user.is_active or user.is_suspended:
        return error_response('This admin account is disabled.', {}, 403)

    token = RefreshToken.for_user(user)
    return success_response('Admin login successful.', {
        'access_token': str(token.access_token),
        'refresh_token': str(token),
        'user': UserProfileSerializer(user).data,
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_me(request):
    return success_response('Profile.', UserProfileSerializer(request.user).data)


# ---------------------------------------------------------------------------
# Tenant Management
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_tenant_list(request):
    tenants = Tenant.objects.select_related('owner', 'package').all()
    status_filter = request.query_params.get('status')
    if status_filter:
        tenants = tenants.filter(status=status_filter)
    search = request.query_params.get('search', '')
    if search:
        tenants = tenants.filter(company_name__icontains=search)

    page = int(request.query_params.get('page', 1))
    limit = int(request.query_params.get('limit', 20))
    paged, total, pages = paginate_queryset(tenants, page, limit)
    return success_response('Tenants retrieved.', {
        'results': TenantSerializer(paged, many=True).data,
        'total': total, 'page': page, 'total_pages': pages,
    })


@api_view(['GET', 'PATCH'])
@permission_classes([IsAdminUser])
def admin_tenant_detail(request, tenant_id):
    try:
        tenant = Tenant.objects.select_related('owner', 'package').get(id=tenant_id)
    except Tenant.DoesNotExist:
        return error_response('Tenant not found.', {}, 404)

    if request.method == 'GET':
        return success_response('Tenant detail.', TenantSerializer(tenant).data)

    # Only super_admin can edit tenant details
    if request.user.admin_role != 'super_admin':
        return error_response('Super admin role required.', {}, 403)

    from apps.tenants.serializers import TenantSettingsUpdateSerializer
    serializer = TenantSettingsUpdateSerializer(tenant, data=request.data, partial=True)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)
    serializer.save()
    return success_response('Tenant updated.', TenantSerializer(tenant).data)


@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def admin_suspend_tenant(request, tenant_id):
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return error_response('Tenant not found.', {}, 404)

    reason = request.data.get('reason', '')
    tenant.status = 'suspended'
    tenant.save(update_fields=['status'])
    logger.info('Tenant %s suspended by admin %s. Reason: %s', tenant_id, request.user.email, reason)
    return success_response('Tenant suspended.')


@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def admin_reactivate_tenant(request, tenant_id):
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return error_response('Tenant not found.', {}, 404)

    tenant.status = 'active'
    tenant.save(update_fields=['status'])
    return success_response('Tenant reactivated.')


@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def admin_change_package(request, tenant_id):
    """POST /api/admin/tenants/:id/change-package/ — upgrade/downgrade a tenant's plan."""
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return error_response('Tenant not found.', {}, 404)

    package_id = request.data.get('package_id')
    reason = request.data.get('reason', '')
    try:
        new_package = Package.objects.get(id=package_id)
    except Package.DoesNotExist:
        return error_response('Package not found.', {}, 404)

    old_package = tenant.package
    with transaction.atomic():
        tenant.package = new_package
        tenant.save(update_fields=['package'])
        TenantSubscriptionLog.objects.create(
            tenant=tenant,
            old_package=old_package,
            new_package=new_package,
            changed_by=request.user,
            reason=reason,
        )
    return success_response('Package changed.', TenantSerializer(tenant).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_extend_trial(request, tenant_id):
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return error_response('Tenant not found.', {}, 404)

    days = int(request.data.get('days', 7))
    now = timezone.now()
    # Extend from current trial_end if still in trial, else from now
    base = tenant.trial_end if tenant.trial_end and tenant.trial_end > now else now
    tenant.trial_end = base + timedelta(days=days)
    tenant.subscription_end = tenant.trial_end
    tenant.status = 'trial'
    tenant.save(update_fields=['trial_end', 'subscription_end', 'status'])
    return success_response(f'Trial extended by {days} days.')


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_tenant_usage(request, tenant_id):
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return error_response('Tenant not found.', {}, 404)

    from apps.sites.models import Site
    from apps.bills.models import Bill
    from apps.attendance.models import DailyAttendance
    from django.db.models import Sum

    site_count = Site.objects.filter(tenant=tenant, is_active=True).count()
    manager_count = User.objects.filter(
        user_type='manager',
        managed_sites__site__tenant=tenant,
        managed_sites__is_active=True,
    ).distinct().count()

    site_ids = Site.objects.filter(tenant=tenant).values_list('id', flat=True)
    total_bills = Bill.objects.filter(site_id__in=site_ids).count()
    total_spend = Bill.objects.filter(site_id__in=site_ids).aggregate(t=Sum('total_amount_lkr'))['t'] or 0

    return success_response('Tenant usage.', {
        'active_sites': site_count,
        'managers': manager_count,
        'total_bills': total_bills,
        'total_material_spend_lkr': float(total_spend),
        'package_limits': {
            'max_sites': tenant.package.max_sites if tenant.package else None,
            'max_managers': tenant.package.max_managers if tenant.package else None,
        }
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_tenant_audit(request, tenant_id):
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return error_response('Tenant not found.', {}, 404)

    logs = TenantSubscriptionLog.objects.filter(tenant=tenant).order_by('-changed_at')
    return success_response('Audit log.', SubscriptionLogSerializer(logs, many=True).data)


# ---------------------------------------------------------------------------
# Package Management
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_package_list_create(request):
    if request.method == 'GET':
        packages = Package.objects.all()
        return success_response('Packages.', PackageSerializer(packages, many=True).data)

    if request.user.admin_role != 'super_admin':
        return error_response('Super admin role required.', {}, 403)

    serializer = PackageSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)
    package = serializer.save()
    return success_response('Package created.', PackageSerializer(package).data, 201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsSuperAdmin])
def admin_package_detail(request, package_id):
    try:
        package = Package.objects.get(id=package_id)
    except Package.DoesNotExist:
        return error_response('Package not found.', {}, 404)

    if request.method == 'PATCH':
        serializer = PackageSerializer(package, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response('Validation failed.', serializer.errors, 422)
        package = serializer.save()
        return success_response('Package updated.', PackageSerializer(package).data)

    if request.method == 'DELETE':
        if package.tenants.filter(status__in=['active', 'trial']).exists():
            return error_response('Cannot delete a package with active tenants.', {}, 409)
        package.is_active = False
        package.save(update_fields=['is_active'])
        return success_response('Package deactivated.')


# ---------------------------------------------------------------------------
# Payment Management
# ---------------------------------------------------------------------------

def _apply_admin_period(qs, request, date_field='payment_date'):
    """
    Filter a payment/tenant queryset by ?date_from / ?date_to (YYYY-MM-DD)
    or ?month=YYYY-MM. Returns (qs, error_or_None).
    """
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if date_from or date_to:
        if date_from:
            qs = qs.filter(**{f'{date_field}__gte': date_from})
        if date_to:
            qs = qs.filter(**{f'{date_field}__lte': date_to})
        return qs, None
    month_str = request.query_params.get('month')
    if month_str:
        try:
            year, month = month_str.split('-')
            qs = qs.filter(**{f'{date_field}__year': int(year), f'{date_field}__month': int(month)})
        except ValueError:
            return qs, error_response('month must be YYYY-MM.', {}, 400)
    return qs, None


@api_view(['GET'])
@permission_classes([IsFinanceAdmin])
def admin_payment_list(request):
    payments = Payment.objects.select_related('tenant', 'package').all()

    status_filter = request.query_params.get('status')
    if status_filter:
        payments = payments.filter(status=status_filter)

    method_filter = request.query_params.get('method')
    if method_filter:
        payments = payments.filter(method=method_filter)

    search = request.query_params.get('search', '').strip()
    if search:
        payments = payments.filter(
            Q(tenant__company_name__icontains=search) | Q(gateway_ref__icontains=search)
        )

    payments, err = _apply_admin_period(payments, request)
    if err:
        return err

    page = int(request.query_params.get('page', 1))
    limit = int(request.query_params.get('limit', 20))
    paged, total, pages = paginate_queryset(payments, page, limit)
    return success_response('Payments.', {
        'results': PaymentSerializer(paged, many=True).data,
        'total': total, 'page': page, 'total_pages': pages,
    })


@api_view(['POST'])
@permission_classes([IsFinanceAdmin])
def admin_manual_payment(request):
    """POST /api/admin/payments/manual/ — record a bank transfer or offline payment."""
    from apps.payments.views import _activate_subscription

    tenant_id = request.data.get('tenant_id')
    package_id = request.data.get('package_id')
    amount = request.data.get('amount_lkr')
    months = int(request.data.get('validity_months', 1))
    note = request.data.get('internal_note', '')

    try:
        tenant = Tenant.objects.get(id=tenant_id)
        package = Package.objects.get(id=package_id)
    except (Tenant.DoesNotExist, Package.DoesNotExist) as e:
        return error_response(str(e), {}, 404)

    with transaction.atomic():
        payment = Payment.objects.create(
            tenant=tenant,
            package=package,
            amount_lkr=amount,
            method='manual',
            status='success',
            payment_date=date.today(),
            validity_months=months,
            internal_note=note,
            recorded_by=request.user,
        )
        _activate_subscription(payment)

    return success_response('Manual payment recorded.', PaymentSerializer(payment).data, 201)


@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def admin_refund_payment(request, payment_id):
    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        return error_response('Payment not found.', {}, 404)

    if payment.status != 'success':
        return error_response('Only successful payments can be refunded.', {}, 409)

    payment.status = 'refunded'
    payment.internal_note = (payment.internal_note or '') + f'\nRefunded by {request.user.email}'
    payment.save(update_fields=['status', 'internal_note'])
    return success_response('Payment marked as refunded.')


@api_view(['GET'])
@permission_classes([IsFinanceAdmin])
def admin_revenue_summary(request):
    from django.db.models import Sum

    base = Payment.objects.filter(status='success')
    payments, err = _apply_admin_period(base, request)
    if err:
        return err

    total = payments.aggregate(t=Sum('amount_lkr'))['t'] or 0
    by_method = {
        m: float(payments.filter(method=m).aggregate(t=Sum('amount_lkr'))['t'] or 0)
        for m in ['payhere', 'webxpay', 'bank_transfer', 'manual']
    }

    # Revenue grouped by package tier for the selected period.
    tier_rows = (
        payments.values('package__name')
        .annotate(gross=Sum('amount_lkr'))
        .order_by('-gross')
    )
    by_tier = [
        {
            'tier': (r['package__name'] or 'Unknown'),
            'gross_lkr': float(r['gross'] or 0),
            'tenants': payments.filter(package__name=r['package__name'])
                               .values('tenant').distinct().count(),
        }
        for r in tier_rows
    ]

    # Last 6 months revenue-by-tier trend for the chart (ignores the period filter
    # so the trend line is always complete).
    from datetime import date as _date, timedelta as _td
    today = timezone.now().date()
    tiers = list(
        Payment.objects.filter(status='success')
        .exclude(package__name__isnull=True)
        .values_list('package__name', flat=True).distinct()
    )
    trend = []
    for i in range(5, -1, -1):
        y, m = today.year, today.month - i
        while m <= 0:
            m += 12
            y -= 1
        month_payments = Payment.objects.filter(
            status='success', payment_date__year=y, payment_date__month=m,
        )
        point = {'month': _date(y, m, 1).strftime('%b')}
        for tier in tiers:
            point[tier] = float(
                month_payments.filter(package__name=tier)
                .aggregate(t=Sum('amount_lkr'))['t'] or 0
            )
        trend.append(point)

    return success_response('Revenue summary.', {
        'total_revenue_lkr': float(total),
        'by_method': by_method,
        'by_tier': by_tier,
        'tiers': tiers,
        'trend': trend,
        'payment_count': payments.count(),
    })


@api_view(['GET'])
@permission_classes([IsFinanceAdmin])
def admin_upcoming_renewals(request):
    """GET /api/admin/payments/upcoming-renewals/?days=30"""
    days = int(request.query_params.get('days', 30))
    now = timezone.now()
    horizon = now + timedelta(days=days)
    tenants = (
        Tenant.objects.filter(
            subscription_end__gte=now, subscription_end__lte=horizon,
        )
        .select_related('package')
        .order_by('subscription_end')
    )
    results = [
        {
            'id': str(t.id),
            'company': t.company_name,
            'package': t.package.name if t.package else '—',
            'amount': float(t.package.price_lkr) if t.package else 0,
            'due': t.subscription_end.date().isoformat() if t.subscription_end else None,
        }
        for t in tenants
    ]
    return success_response('Upcoming renewals.', results)


# ---------------------------------------------------------------------------
# Mobile User (Manager) Management
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_mobile_users(request):
    users = User.objects.filter(user_type='manager')
    search = request.query_params.get('search', '')
    if search:
        users = users.filter(full_name__icontains=search) | users.filter(email__icontains=search)
    page = int(request.query_params.get('page', 1))
    limit = int(request.query_params.get('limit', 20))
    paged, total, pages = paginate_queryset(users, page, limit)
    return success_response('Mobile users.', {
        'results': ManagerListSerializer(paged, many=True).data,
        'total': total, 'page': page, 'total_pages': pages,
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_mobile_user_detail(request, user_id):
    try:
        user = User.objects.get(id=user_id, user_type='manager')
    except User.DoesNotExist:
        return error_response('Manager not found.', {}, 404)
    return success_response('Manager detail.', ManagerListSerializer(user).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_suspend_user(request, user_id):
    try:
        user = User.objects.get(id=user_id, user_type='manager')
    except User.DoesNotExist:
        return error_response('Manager not found.', {}, 404)
    user.is_suspended = True
    user.save(update_fields=['is_suspended'])
    return success_response('Manager suspended.')


@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def admin_reset_password(request, user_id):
    """POST /api/admin/mobile-users/:id/reset-password/ — force-set a new password."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return error_response('User not found.', {}, 404)

    new_password = request.data.get('new_password')
    if not new_password or len(new_password) < 8:
        return error_response('new_password must be at least 8 characters.', {}, 400)

    user.set_password(new_password)
    user.save()
    return success_response('Password reset.')


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_analytics_kpis(request):
    from apps.sites.models import Site
    from apps.bills.models import Bill
    from django.db.models import Sum

    total_tenants = Tenant.objects.count()
    active_tenants = Tenant.objects.filter(status='active').count()
    trial_tenants = Tenant.objects.filter(status='trial').count()
    total_sites = Site.objects.filter(is_active=True).count()
    total_managers = User.objects.filter(user_type='manager').count()
    total_revenue = Payment.objects.filter(status='success').aggregate(t=Sum('amount_lkr'))['t'] or 0

    return success_response('KPIs.', {
        'total_tenants': total_tenants,
        'active_tenants': active_tenants,
        'trial_tenants': trial_tenants,
        'total_active_sites': total_sites,
        'total_managers': total_managers,
        'total_revenue_lkr': float(total_revenue),
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_analytics_dau(request):
    """Daily active users — managers who logged data in the last 30 days."""
    from apps.progress.models import ProgressLog
    from django.db.models import Count, TruncDate

    dau = (
        ProgressLog.objects
        .filter(created_at__gte=timezone.now() - timedelta(days=30))
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('logged_by', distinct=True))
        .order_by('day')
    )
    return success_response('Daily active users.', list(dau))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_analytics_features(request):
    """Which features are most used across tenants."""
    active = Tenant.objects.filter(status__in=['active', 'trial']).select_related('package')
    feature_counts = {
        'whatsapp': sum(1 for t in active if t.package and t.package.feature_whatsapp),
        'excel_reports': sum(1 for t in active if t.package and t.package.feature_excel),
        'bank_report': sum(1 for t in active if t.package and t.package.feature_bank_report),
        'branded_pdf': sum(1 for t in active if t.package and t.package.feature_branded_pdf),
        'subcontractor': sum(1 for t in active if t.package and t.package.feature_subcontractor),
    }
    return success_response('Feature usage.', feature_counts)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_analytics_retention(request):
    """Monthly retention: how many trial tenants converted to paid."""
    converted = Tenant.objects.filter(
        status='active',
        trial_end__isnull=False,
        subscription_start__gt=timezone.now() - timedelta(days=90)
    ).count()
    trialed = Tenant.objects.filter(
        trial_start__gte=timezone.now() - timedelta(days=90)
    ).count()
    rate = round(converted / trialed * 100, 1) if trialed else 0
    return success_response('Retention.', {
        'trialed_last_90d': trialed,
        'converted_to_paid': converted,
        'conversion_rate_pct': rate,
    })


# ---------------------------------------------------------------------------
# Admin User Management
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsSuperAdmin])
def admin_admin_list_create(request):
    if request.method == 'GET':
        admins = User.objects.filter(user_type='admin')
        return success_response('Admin users.', UserProfileSerializer(admins, many=True).data)

    # Create a new admin user
    full_name = request.data.get('full_name')
    email = request.data.get('email')
    password = request.data.get('password')
    admin_role = request.data.get('admin_role', 'support')

    if not all([full_name, email, password]):
        return error_response('full_name, email, and password are required.', {}, 400)

    if User.objects.filter(email=email).exists():
        return error_response('Email already in use.', {}, 409)

    user = User.objects.create_user(
        email=email, full_name=full_name, password=password,
        user_type='admin', admin_role=admin_role,
    )
    return success_response('Admin user created.', UserProfileSerializer(user).data, 201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsSuperAdmin])
def admin_admin_detail(request, admin_id):
    try:
        admin = User.objects.get(id=admin_id, user_type='admin')
    except User.DoesNotExist:
        return error_response('Admin not found.', {}, 404)

    if request.method == 'PATCH':
        for field in ['full_name', 'admin_role', 'is_active']:
            if field in request.data:
                setattr(admin, field, request.data[field])
        admin.save()
        return success_response('Admin updated.', UserProfileSerializer(admin).data)

    # DELETE — deactivate rather than delete to preserve audit trail
    admin.is_active = False
    admin.save(update_fields=['is_active'])
    return success_response('Admin deactivated.')


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_audit_log(request):
    """GET /api/admin/audit/ — subscription change audit log."""
    logs = TenantSubscriptionLog.objects.select_related(
        'tenant', 'old_package', 'new_package', 'changed_by'
    ).order_by('-changed_at')
    page = int(request.query_params.get('page', 1))
    limit = int(request.query_params.get('limit', 50))
    paged, total, pages = paginate_queryset(logs, page, limit)
    return success_response('Audit log.', {
        'results': SubscriptionLogSerializer(paged, many=True).data,
        'total': total, 'page': page, 'total_pages': pages,
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_audit_export(request):
    """GET /api/admin/audit/export/ — returns CSV download URL of audit log."""
    # In production, this would generate and upload a CSV to Supabase
    # For now, return all audit records in JSON for client-side export
    logs = TenantSubscriptionLog.objects.select_related(
        'tenant', 'old_package', 'new_package', 'changed_by'
    ).order_by('-changed_at')
    return success_response('Audit export.', SubscriptionLogSerializer(logs, many=True).data)
