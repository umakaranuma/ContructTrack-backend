"""
Auth URL routes — all prefixed /api/auth/ from root urls.py.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('register/', views.register_owner, name='auth-register'),
    path('register-mobile/', views.register_manager, name='auth-register-mobile'),
    path('login/', views.login_view, name='auth-login'),
    path('logout/', views.logout_view, name='auth-logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='auth-token-refresh'),
    path('me/', views.me_view, name='auth-me'),
]
