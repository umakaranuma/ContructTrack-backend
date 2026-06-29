from django.urls import path
from .views import tenant_settings, upload_logo, notification_settings

urlpatterns = [
    path('', tenant_settings, name='settings-detail'),
    path('logo/', upload_logo, name='settings-logo'),
    path('notifications/', notification_settings, name='settings-notifications'),
]
