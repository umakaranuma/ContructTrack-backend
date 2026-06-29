"""
Dashboard URL routes — all prefixed /api/dashboard/ from root urls.py.
"""
from django.urls import path
from . import views_dashboard

urlpatterns = [
    path('overview/', views_dashboard.overview_stats,  name='dashboard-overview'),
    path('activity/', views_dashboard.activity_feed,   name='dashboard-activity'),
    path('alerts/',   views_dashboard.all_alerts,      name='dashboard-alerts'),
]
