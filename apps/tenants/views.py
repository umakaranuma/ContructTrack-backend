"""
Tenant and package views.
Owner-facing settings views are also here (thin layer — most logic is in serializers).
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.core.utils import success_response, error_response
from apps.core.permissions import IsOwner
from .models import Package, Tenant
from .serializers import PackageSerializer, TenantSerializer, TenantSettingsUpdateSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def list_packages(request):
    """GET /api/packages/ — public endpoint, no auth required (shown on landing page)."""
    packages = Package.objects.filter(is_active=True).order_by('display_order')
    return success_response('Packages retrieved.', PackageSerializer(packages, many=True).data)


@api_view(['GET', 'PATCH'])
@permission_classes([IsOwner])
def tenant_settings(request):
    """
    GET  /api/settings/ — retrieve current tenant settings
    PATCH /api/settings/ — update company info / notification preferences
    """
    tenant = Tenant.objects.filter(owner=request.user).select_related('package').first()
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    if request.method == 'GET':
        return success_response('Settings retrieved.', TenantSerializer(tenant).data)

    serializer = TenantSettingsUpdateSerializer(tenant, data=request.data, partial=True)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)
    serializer.save()
    return success_response('Settings updated.', TenantSerializer(tenant).data)


@api_view(['POST'])
@permission_classes([IsOwner])
def upload_logo(request):
    """
    POST /api/settings/logo/
    Accepts a logo URL (client uploads to Supabase directly and sends the URL).
    Direct-upload pattern avoids streaming binary through the Django process.
    """
    tenant = Tenant.objects.filter(owner=request.user).first()
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    logo_url = request.data.get('logo_url')
    if not logo_url:
        return error_response('logo_url is required.', {}, 400)

    tenant.logo_url = logo_url
    tenant.save(update_fields=['logo_url'])
    return success_response('Logo updated.', {'logo_url': logo_url})


@api_view(['GET', 'PATCH'])
@permission_classes([IsOwner])
def notification_settings(request):
    """
    GET  /api/settings/notifications/ — read alert prefs
    PATCH /api/settings/notifications/ — update WhatsApp + email digest settings
    """
    tenant = Tenant.objects.filter(owner=request.user).first()
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    if request.method == 'GET':
        return success_response('Notification settings.', {
            'whatsapp_alerts': tenant.whatsapp_alerts,
            'whatsapp_number': tenant.whatsapp_number,
            'email_digest': tenant.email_digest,
        })

    allowed_fields = ['whatsapp_alerts', 'whatsapp_number', 'email_digest']
    for field in allowed_fields:
        if field in request.data:
            setattr(tenant, field, request.data[field])
    tenant.save(update_fields=allowed_fields)
    return success_response('Notification settings updated.', {
        'whatsapp_alerts': tenant.whatsapp_alerts,
        'whatsapp_number': tenant.whatsapp_number,
        'email_digest': tenant.email_digest,
    })
