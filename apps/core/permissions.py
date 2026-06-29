"""
Custom DRF permission classes for ConstructTrack's RBAC.
We don't use Django's built-in permission framework — it requires auth_permission
tables we've disabled. Instead, we check user_type and admin_role directly.
"""
from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    """
    Grants access only to internal ConstructTrack staff (user_type == 'admin').
    Used to protect /api/admin/* endpoints.
    """
    message = 'Only ConstructTrack admin accounts can access this endpoint.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'admin'
        )


class IsSuperAdmin(BasePermission):
    """
    Full admin access — can create/delete packages, suspend tenants, etc.
    """
    message = 'Super admin role required.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'admin' and
            request.user.admin_role == 'super_admin'
        )


class IsFinanceAdmin(BasePermission):
    """
    Finance admin can view/manage payments and revenue; read-only elsewhere.
    """
    message = 'Finance admin role required.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'admin' and
            request.user.admin_role in ('super_admin', 'finance')
        )


class IsOwner(BasePermission):
    """
    Tenant owner — created a company account, manages sites and managers.
    """
    message = 'Only tenant owners can access this endpoint.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'owner'
        )


class IsManager(BasePermission):
    """
    Site manager — mobile app user who logs attendance, bills, progress.
    """
    message = 'Only site managers can access this endpoint.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'manager'
        )


class IsOwnerOrManager(BasePermission):
    """
    Shared access — both owners (web) and managers (mobile) can read site data.
    """
    message = 'Owner or manager access required.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.user_type in ('owner', 'manager')
        )


class IsAdminOrOwner(BasePermission):
    """Used by settings endpoints that admins can also override."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.user_type in ('admin', 'owner')
        )
