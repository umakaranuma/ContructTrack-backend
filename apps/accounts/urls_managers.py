"""
Manager management URLs — all prefixed /api/managers/ from root urls.py.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.list_managers, name='managers-list'),
    path('resolve/', views.resolve_manager_by_code, name='managers-resolve'),
    path('search/', views.search_manager_by_email, name='managers-search'),
    path('invite/', views.invite_manager, name='managers-invite'),
    path('<uuid:manager_id>/assign/', views.assign_manager, name='managers-assign'),
    path('<uuid:manager_id>/assign/<uuid:site_id>/', views.remove_manager_from_site, name='managers-remove'),
    path('<uuid:manager_id>/deactivate/', views.deactivate_manager, name='managers-deactivate'),
]
