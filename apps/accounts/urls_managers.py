"""
Manager management URLs — all prefixed /api/managers/ from root urls.py.
"""
from django.urls import path
from . import views

urlpatterns = [
    # List / add
    path('', views.list_managers, name='managers-list'),
    path('add/', views.add_manager, name='managers-add'),

    # Lookup (supports ?ref_code= and ?email=)
    path('lookup/', views.lookup_manager, name='managers-lookup'),

    # Legacy search / resolve kept for backwards compat
    path('resolve/', views.lookup_manager, name='managers-resolve'),
    path('search/', views.lookup_manager, name='managers-search'),

    # Invite new manager by email
    path('invite/', views.invite_manager, name='managers-invite'),

    # Per-manager actions
    path('<uuid:manager_id>/', views.get_manager, name='managers-detail'),
    path('<uuid:manager_id>/assign/', views.assign_manager, name='managers-assign'),
    path('<uuid:manager_id>/unassign/', views.unassign_manager, name='managers-unassign'),
    path('<uuid:manager_id>/assign/<uuid:site_id>/', views.remove_manager_from_site, name='managers-remove-from-site'),
    path('<uuid:manager_id>/deactivate/', views.deactivate_manager, name='managers-deactivate'),
    path('<uuid:manager_id>/remove/', views.remove_manager, name='managers-remove'),
    path('<uuid:manager_id>/activity/', views.manager_activity, name='managers-activity'),

    # DELETE /api/managers/:id/ — handled by remove_manager view
    # (also accessible as <uuid:manager_id>/remove/ for explicit naming)
]
