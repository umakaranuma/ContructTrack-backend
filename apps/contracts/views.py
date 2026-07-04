"""
Contract management views.
All endpoints are owner-only — managers don't see contract financials.
"""
from rest_framework.decorators import api_view, permission_classes

from apps.core.utils import success_response, error_response
from apps.core.permissions import IsOwner
from apps.tenants.models import Tenant
from apps.sites.models import Site
from .models import SiteContract, PaymentCertificate, Subcontract, SubcontractPayment
from .serializers import (
    SiteContractSerializer, SiteContractWriteSerializer,
    PaymentCertificateSerializer,
    SubcontractSerializer, SubcontractWriteSerializer,
    SubcontractPaymentSerializer,
    ContractSummarySerializer,
)


def _get_tenant(user):
    return Tenant.objects.filter(owner=user).first()


def _get_site(tenant, site_id):
    try:
        return Site.objects.get(id=site_id, tenant=tenant)
    except Site.DoesNotExist:
        return None


# ─── Site Contract ────────────────────────────────────────────────────────────

@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([IsOwner])
def site_contract(request, site_id):
    """
    GET   /api/contracts/sites/<site_id>/  → full contract + certs + subcontracts
    POST  /api/contracts/sites/<site_id>/  → create a contract for this site
    PATCH /api/contracts/sites/<site_id>/  → update existing contract
    """
    tenant = _get_tenant(request.user)
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    site = _get_site(tenant, site_id)
    if not site:
        return error_response('Site not found.', {}, 404)

    if request.method == 'GET':
        contract = SiteContract.objects.filter(site=site).prefetch_related(
            'payment_certs'
        ).first()
        subcontracts = Subcontract.objects.filter(site=site).prefetch_related('payments')
        return success_response('Contract data retrieved.', {
            'contract':     SiteContractSerializer(contract).data if contract else None,
            'subcontracts': SubcontractSerializer(subcontracts, many=True).data,
        })

    if request.method == 'POST':
        if SiteContract.objects.filter(site=site, status='active').exists():
            return error_response(
                'This site already has an active contract. Update it via PATCH or close it first.',
                {}, 400,
            )
        serializer = SiteContractWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('Validation failed.', serializer.errors, 422)
        contract = serializer.save(site=site)
        return success_response('Contract created.', SiteContractSerializer(contract).data, 201)

    # PATCH
    contract = SiteContract.objects.filter(site=site).first()
    if not contract:
        return error_response('No contract found for this site.', {}, 404)
    serializer = SiteContractWriteSerializer(contract, data=request.data, partial=True)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)
    contract = serializer.save()
    return success_response('Contract updated.', SiteContractSerializer(contract).data)


# ─── Payment Certificates ─────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsOwner])
def add_payment_cert(request, site_id):
    """POST /api/contracts/sites/<site_id>/certs/"""
    tenant = _get_tenant(request.user)
    if not tenant:
        return error_response('Tenant not found.', {}, 404)
    site = _get_site(tenant, site_id)
    if not site:
        return error_response('Site not found.', {}, 404)
    contract = SiteContract.objects.filter(site=site).first()
    if not contract:
        return error_response('No contract exists for this site. Create one first.', {}, 400)

    serializer = PaymentCertificateSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)

    # Auto-assign next cert number if not provided
    data = serializer.validated_data
    if 'cert_number' not in data or not data.get('cert_number'):
        last = contract.payment_certs.order_by('-cert_number').first()
        data['cert_number'] = (last.cert_number + 1) if last else 1

    cert = serializer.save(contract=contract)
    return success_response('Payment certificate added.', PaymentCertificateSerializer(cert).data, 201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsOwner])
def update_payment_cert(request, site_id, cert_id):
    """PATCH/DELETE /api/contracts/sites/<site_id>/certs/<cert_id>/"""
    tenant = _get_tenant(request.user)
    if not tenant:
        return error_response('Tenant not found.', {}, 404)
    site = _get_site(tenant, site_id)
    if not site:
        return error_response('Site not found.', {}, 404)
    try:
        cert = PaymentCertificate.objects.get(id=cert_id, contract__site=site)
    except PaymentCertificate.DoesNotExist:
        return error_response('Certificate not found.', {}, 404)

    if request.method == 'DELETE':
        cert.delete()
        return success_response('Certificate deleted.')

    serializer = PaymentCertificateSerializer(cert, data=request.data, partial=True)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)
    cert = serializer.save()
    return success_response('Certificate updated.', PaymentCertificateSerializer(cert).data)


# ─── Subcontracts ─────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsOwner])
def subcontract_list(request, site_id):
    """
    GET  /api/contracts/sites/<site_id>/subcontracts/
    POST /api/contracts/sites/<site_id>/subcontracts/
    """
    tenant = _get_tenant(request.user)
    if not tenant:
        return error_response('Tenant not found.', {}, 404)
    site = _get_site(tenant, site_id)
    if not site:
        return error_response('Site not found.', {}, 404)

    if request.method == 'GET':
        subs = Subcontract.objects.filter(site=site).prefetch_related('payments')
        return success_response('Subcontracts retrieved.', SubcontractSerializer(subs, many=True).data)

    serializer = SubcontractWriteSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)
    sub = serializer.save(site=site)
    return success_response('Subcontract created.', SubcontractSerializer(sub).data, 201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsOwner])
def subcontract_detail(request, site_id, sub_id):
    """PATCH/DELETE /api/contracts/sites/<site_id>/subcontracts/<sub_id>/"""
    tenant = _get_tenant(request.user)
    if not tenant:
        return error_response('Tenant not found.', {}, 404)
    site = _get_site(tenant, site_id)
    if not site:
        return error_response('Site not found.', {}, 404)
    try:
        sub = Subcontract.objects.get(id=sub_id, site=site)
    except Subcontract.DoesNotExist:
        return error_response('Subcontract not found.', {}, 404)

    if request.method == 'DELETE':
        sub.delete()
        return success_response('Subcontract deleted.')

    serializer = SubcontractWriteSerializer(sub, data=request.data, partial=True)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)
    sub = serializer.save()
    return success_response('Subcontract updated.', SubcontractSerializer(sub).data)


@api_view(['POST'])
@permission_classes([IsOwner])
def add_subcontract_payment(request, site_id, sub_id):
    """POST /api/contracts/sites/<site_id>/subcontracts/<sub_id>/payments/"""
    tenant = _get_tenant(request.user)
    if not tenant:
        return error_response('Tenant not found.', {}, 404)
    site = _get_site(tenant, site_id)
    if not site:
        return error_response('Site not found.', {}, 404)
    try:
        sub = Subcontract.objects.get(id=sub_id, site=site)
    except Subcontract.DoesNotExist:
        return error_response('Subcontract not found.', {}, 404)

    serializer = SubcontractPaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)

    # Guard: don't allow overpayment
    new_total = sub.total_paid_lkr + float(serializer.validated_data['amount_lkr'])
    if new_total > float(sub.contract_value_lkr):
        return error_response(
            f'Payment would exceed subcontract value of LKR {sub.contract_value_lkr}. '
            f'Balance remaining: LKR {sub.balance_lkr}.',
            {}, 400,
        )

    payment = serializer.save(subcontract=sub)
    return success_response(
        'Payment recorded.',
        SubcontractPaymentSerializer(payment).data,
        201,
    )


@api_view(['DELETE'])
@permission_classes([IsOwner])
def delete_subcontract_payment(request, site_id, sub_id, payment_id):
    """DELETE /api/contracts/sites/<site_id>/subcontracts/<sub_id>/payments/<payment_id>/"""
    tenant = _get_tenant(request.user)
    if not tenant:
        return error_response('Tenant not found.', {}, 404)
    site = _get_site(tenant, site_id)
    if not site:
        return error_response('Site not found.', {}, 404)
    try:
        payment = SubcontractPayment.objects.get(
            id=payment_id, subcontract_id=sub_id, subcontract__site=site,
        )
    except SubcontractPayment.DoesNotExist:
        return error_response('Payment not found.', {}, 404)
    payment.delete()
    return success_response('Payment deleted.')


# ─── Finance summary (cross-site) ─────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsOwner])
def contracts_summary(request):
    """
    GET /api/contracts/summary/
    Returns all active site contracts for the owner with aggregated financials.
    Used by the Finance page Contracts tab.
    """
    tenant = _get_tenant(request.user)
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    site_id = request.query_params.get('site_id')
    site_ids = Site.objects.filter(tenant=tenant).values_list('id', flat=True)
    if site_id:
        site_ids = [s for s in site_ids if str(s) == site_id]

    contracts = SiteContract.objects.filter(
        site_id__in=site_ids,
    ).prefetch_related('payment_certs', 'site__subcontracts__payments').select_related('site')

    from django.db.models import Sum
    from .models import SubcontractPayment

    # Totals across all matched contracts
    total_contract_value  = sum(float(c.contract_value_lkr) for c in contracts)
    total_received        = sum(c.total_received_lkr for c in contracts)
    total_outstanding     = sum(c.outstanding_lkr for c in contracts)

    all_sub_ids = Subcontract.objects.filter(site_id__in=site_ids).values_list('id', flat=True)
    total_sub_committed   = float(
        Subcontract.objects.filter(site_id__in=site_ids)
        .aggregate(t=Sum('contract_value_lkr'))['t'] or 0
    )
    total_sub_paid        = float(
        SubcontractPayment.objects.filter(subcontract_id__in=all_sub_ids)
        .aggregate(t=Sum('amount_lkr'))['t'] or 0
    )

    return success_response('Contracts summary.', {
        'totals': {
            'contract_value_lkr':      total_contract_value,
            'total_received_lkr':      total_received,
            'total_outstanding_lkr':   total_outstanding,
            'subcontract_committed_lkr': total_sub_committed,
            'subcontract_paid_lkr':    total_sub_paid,
        },
        'contracts': ContractSummarySerializer(contracts, many=True).data,
    })
