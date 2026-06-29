"""
Mobile-first API routes — optimised for the React Native / Flutter app.
All endpoints require manager or owner authentication.
Sync endpoint allows batch offline-to-online data push.
"""
from django.urls import path
from . import views_mobile as v

urlpatterns = [
    # Site listing — trimmed payload for mobile bandwidth
    path('sites/', v.mobile_sites, name='mobile-sites'),
    path('sites/<uuid:site_id>/params/', v.mobile_site_params, name='mobile-site-params'),

    # Bills
    path('sites/<uuid:site_id>/bills/', v.mobile_bills, name='mobile-bills'),
    path('sites/<uuid:site_id>/bills/<uuid:bill_id>/photo/', v.mobile_bill_photo, name='mobile-bill-photo'),

    # Workers
    path('sites/<uuid:site_id>/workers/', v.mobile_workers, name='mobile-workers'),

    # Attendance
    path('sites/<uuid:site_id>/attendance/', v.mobile_attendance, name='mobile-attendance'),
    path('sites/<uuid:site_id>/attendance/<str:log_date>/pay/', v.mobile_attendance_pay, name='mobile-attendance-pay'),

    # Progress
    path('sites/<uuid:site_id>/progress/', v.mobile_progress, name='mobile-progress'),
    path('sites/<uuid:site_id>/progress/<uuid:log_id>/photos/', v.mobile_progress_photos, name='mobile-progress-photos'),

    # Bulk offline sync
    path('sync/', v.mobile_sync, name='mobile-sync'),
]
