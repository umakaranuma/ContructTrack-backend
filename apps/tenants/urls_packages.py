from django.urls import path
from .views import list_packages

urlpatterns = [
    path('', list_packages, name='packages-list'),
]
