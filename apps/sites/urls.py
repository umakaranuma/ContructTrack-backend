from django.urls import path
from . import views

urlpatterns = [
    path('', views.site_list_create, name='site-list'),
    path('<uuid:site_id>/', views.site_detail, name='site-detail'),

    # Sub-resources
    path('<uuid:site_id>/logs/', views.site_logs, name='site-logs'),
    path('<uuid:site_id>/daily-logs/', views.site_daily_logs, name='site-daily-logs'),  # frontend alias
    path('<uuid:site_id>/bills/', views.site_bills, name='site-bills'),
    path('<uuid:site_id>/workers/', views.site_workers, name='site-workers'),
    path('<uuid:site_id>/attendance/', views.site_attendance, name='site-attendance'),
    path('<uuid:site_id>/progress-photos/', views.site_progress_photos, name='site-photos-full'),
    path('<uuid:site_id>/photos/', views.site_photos, name='site-photos'),  # frontend alias

    # Alerts
    path('<uuid:site_id>/alerts/', views.site_alerts, name='site-alerts'),
    path('<uuid:site_id>/alerts/<uuid:alert_id>/acknowledge/', views.alert_acknowledge, name='alert-acknowledge'),
    path('<uuid:site_id>/alerts/<uuid:alert_id>/resolve/', views.alert_resolve, name='alert-resolve'),
]
