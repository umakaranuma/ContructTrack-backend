"""
Internal admin panel API routes.
All routes are protected by IsAdminUser or sub-role permission classes.
"""
from django.urls import path
from . import views_admin as v

urlpatterns = [
    # Admin auth
    path('auth/login/', v.admin_login, name='admin-login'),
    path('auth/me/', v.admin_me, name='admin-me'),

    # Tenant management
    path('tenants/', v.admin_tenant_list, name='admin-tenant-list'),
    path('tenants/<uuid:tenant_id>/', v.admin_tenant_detail, name='admin-tenant-detail'),
    path('tenants/<uuid:tenant_id>/suspend/', v.admin_suspend_tenant, name='admin-tenant-suspend'),
    path('tenants/<uuid:tenant_id>/reactivate/', v.admin_reactivate_tenant, name='admin-tenant-reactivate'),
    path('tenants/<uuid:tenant_id>/change-package/', v.admin_change_package, name='admin-change-package'),
    path('tenants/<uuid:tenant_id>/extend-trial/', v.admin_extend_trial, name='admin-extend-trial'),
    path('tenants/<uuid:tenant_id>/usage/', v.admin_tenant_usage, name='admin-tenant-usage'),
    path('tenants/<uuid:tenant_id>/audit/', v.admin_tenant_audit, name='admin-tenant-audit'),

    # Package management
    path('packages/', v.admin_package_list_create, name='admin-package-list'),
    path('packages/<uuid:package_id>/', v.admin_package_detail, name='admin-package-detail'),

    # Payment management
    path('payments/', v.admin_payment_list, name='admin-payment-list'),
    path('payments/manual/', v.admin_manual_payment, name='admin-payment-manual'),
    path('payments/<uuid:payment_id>/refund/', v.admin_refund_payment, name='admin-payment-refund'),
    path('payments/revenue-summary/', v.admin_revenue_summary, name='admin-revenue-summary'),
    path('payments/upcoming-renewals/', v.admin_upcoming_renewals, name='admin-upcoming-renewals'),

    # Mobile user management
    path('mobile-users/', v.admin_mobile_users, name='admin-mobile-users'),
    path('mobile-users/<uuid:user_id>/', v.admin_mobile_user_detail, name='admin-mobile-user-detail'),
    path('mobile-users/<uuid:user_id>/suspend/', v.admin_suspend_user, name='admin-suspend-user'),
    path('mobile-users/<uuid:user_id>/reset-password/', v.admin_reset_password, name='admin-reset-password'),

    # Analytics
    path('analytics/kpis/', v.admin_analytics_kpis, name='admin-analytics-kpis'),
    path('analytics/dau/', v.admin_analytics_dau, name='admin-analytics-dau'),
    path('analytics/features/', v.admin_analytics_features, name='admin-analytics-features'),
    path('analytics/retention/', v.admin_analytics_retention, name='admin-analytics-retention'),

    # Admin user management
    path('admins/', v.admin_admin_list_create, name='admin-admins-list'),
    path('admins/<uuid:admin_id>/', v.admin_admin_detail, name='admin-admins-detail'),

    # Audit log
    path('audit/', v.admin_audit_log, name='admin-audit-log'),
    path('audit/export/', v.admin_audit_export, name='admin-audit-export'),
]
