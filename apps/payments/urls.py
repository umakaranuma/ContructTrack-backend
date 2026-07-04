from django.urls import path
from . import views

urlpatterns = [
    path('history/', views.payment_history, name='payment-history'),
    path('initiate/', views.initiate_payment, name='payment-initiate'),
    path('webhook/payhere/', views.payhere_webhook, name='webhook-payhere'),
    path('webhook/webxpay/', views.webxpay_webhook, name='webhook-webxpay'),
]
