from django.urls import path
from . import views

urlpatterns = [
    path('', views.site_list_create, name='site-list'),
    path('<uuid:site_id>/', views.site_detail, name='site-detail'),
    path('<uuid:site_id>/logs/', views.site_logs, name='site-logs'),
    path('<uuid:site_id>/bills/', views.site_bills, name='site-bills'),
    path('<uuid:site_id>/attendance/', views.site_attendance, name='site-attendance'),
    path('<uuid:site_id>/progress-photos/', views.site_progress_photos, name='site-photos'),
    path('<uuid:site_id>/alerts/', views.site_alerts, name='site-alerts'),
]
