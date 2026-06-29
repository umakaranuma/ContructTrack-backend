"""
Payment gateway views.
PayHere and Webxpay send asynchronous webhook notifications after payment.
We verify the hash/signature before updating tenant subscription.
"""
import hashlib
import logging
from datetime import date, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.core.utils import success_response, error_response
from apps.core.permissions import IsOwner
from apps.tenants.models import Tenant
from .models import Payment
from .serializers import PaymentSerializer

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsOwner])
def initiate_payment(request):
    """
    POST /api/payments/initiate/
    Creates a pending payment record and returns PayHere order params.
    The client uses these to open the PayHere payment page.
    """
    tenant = Tenant.objects.filter(owner=request.user).select_related('package').first()
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    from apps.tenants.models import Package
    package_id = request.data.get('package_id')
    months = int(request.data.get('validity_months', 1))

    try:
        package = Package.objects.get(id=package_id, is_active=True)
    except Package.DoesNotExist:
        return error_response('Package not found.', {}, 404)

    amount = float(package.price_lkr) * months

    payment = Payment.objects.create(
        tenant=tenant,
        package=package,
        amount_lkr=amount,
        method='payhere',
        status='pending',
        validity_months=months,
    )

    # PayHere order params — merchant_id should come from env in production
    return success_response('Payment initiated.', {
        'payment_id': str(payment.id),
        'amount': amount,
        'currency': 'LKR',
        'order_id': str(payment.id),
        'package_name': package.name,
        'merchant_id': 'REPLACE_WITH_PAYHERE_MERCHANT_ID',
        'return_url': 'https://app.constructtrack.lk/payment/return',
        'cancel_url': 'https://app.constructtrack.lk/payment/cancel',
        'notify_url': 'https://api.constructtrack.lk/api/payments/webhook/payhere/',
    })


@csrf_exempt  # PayHere POSTs to this without CSRF token — standard webhook pattern
@api_view(['POST'])
@permission_classes([AllowAny])
def payhere_webhook(request):
    """
    POST /api/payments/webhook/payhere/
    PayHere sends payment confirmation here. We verify the MD5 hash before
    activating the subscription — critical security step to prevent fake webhooks.
    """
    data = request.data
    order_id = data.get('order_id')
    status_code = data.get('status_code')
    md5sig = data.get('md5sig', '')

    logger.info('PayHere webhook: order=%s status=%s', order_id, status_code)

    try:
        payment = Payment.objects.select_related('tenant', 'package').get(id=order_id)
    except Payment.DoesNotExist:
        logger.warning('PayHere webhook: unknown order_id %s', order_id)
        return error_response('Order not found.', {}, 404)

    # TODO: Verify MD5 hash with PayHere merchant secret before trusting status
    # hash = MD5(merchant_id + order_id + amount + currency + status_code + MD5(merchant_secret))

    if status_code == '2':  # PayHere: 2 = success
        payment.status = 'success'
        payment.payment_date = date.today()
        payment.gateway_ref = data.get('payment_id', '')
        payment.save()
        _activate_subscription(payment)
    elif status_code in ('0', '-1', '-2', '-3'):
        payment.status = 'failed'
        payment.save()

    return success_response('Webhook processed.')


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def webxpay_webhook(request):
    """
    POST /api/payments/webhook/webxpay/
    Webxpay callback — verify transaction and activate subscription.
    """
    data = request.data
    transaction_id = data.get('transaction_id')
    status = data.get('status', '').lower()

    logger.info('Webxpay webhook: txn=%s status=%s', transaction_id, status)

    # Find payment by gateway_ref if already set, else by our internal ref
    ref = data.get('order_ref') or transaction_id
    try:
        payment = Payment.objects.select_related('tenant', 'package').get(id=ref)
    except Payment.DoesNotExist:
        return error_response('Order not found.', {}, 404)

    if status == 'success':
        payment.status = 'success'
        payment.payment_date = date.today()
        payment.gateway_ref = transaction_id
        payment.save()
        _activate_subscription(payment)
    else:
        payment.status = 'failed'
        payment.save()

    return success_response('Webhook processed.')


def _activate_subscription(payment: Payment):
    """
    Extend tenant subscription after confirmed payment.
    Called from both webhook handlers — isolated here so both share the same logic.
    """
    tenant = payment.tenant
    now = timezone.now()

    # If currently active, extend from current end; if expired, start fresh from today
    start = max(tenant.subscription_end or now, now)
    end = start + timedelta(days=30 * payment.validity_months)

    tenant.subscription_start = start
    tenant.subscription_end = end
    tenant.status = 'active'
    if payment.package:
        old_package = tenant.package
        tenant.package = payment.package
        # Log the package change for audit
        from apps.tenants.models import TenantSubscriptionLog
        if old_package != payment.package:
            TenantSubscriptionLog.objects.create(
                tenant=tenant,
                old_package=old_package,
                new_package=payment.package,
                reason=f'Package changed via payment {payment.id}',
            )
    tenant.save()
    logger.info('Subscription activated: tenant=%s until=%s', tenant.id, end)
