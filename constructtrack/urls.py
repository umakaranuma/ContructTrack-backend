"""
Root URL configuration for ConstructTrack.
All routes are namespaced under /api/ to keep the URL space clean and
versioning-friendly (prefix can become /api/v1/ without touching app urls).
"""
from django.urls import path, include

urlpatterns = [
    # Authentication — login, register, JWT refresh, profile
    path('api/auth/', include('apps.accounts.urls')),

    # Owner dashboard overview endpoints
    path('api/dashboard/', include('apps.core.urls_dashboard')),

    # Public package listing (no auth required)
    path('api/packages/', include('apps.tenants.urls_packages')),

    # Site management
    path('api/sites/', include('apps.sites.urls')),

    # Manager management (owner-facing)
    path('api/managers/', include('apps.accounts.urls_managers')),

    # Finance aggregations
    path('api/finances/', include('apps.bills.urls_finances')),

    # Report generation + download
    path('api/reports/', include('apps.reports.urls')),

    # Tenant settings
    path('api/settings/', include('apps.tenants.urls_settings')),

    # Mobile-first endpoints (offline-sync, GPS photo upload)
    path('api/mobile/', include('apps.core.urls_mobile')),

    # Payment gateway webhooks + initiation
    path('api/payments/', include('apps.payments.urls')),

    # Internal admin panel API (separate from Django admin)
    path('api/admin/', include('apps.core.urls_admin')),
]
