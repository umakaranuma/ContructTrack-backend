from django.urls import path
from . import views

urlpatterns = [
    path('summary/', views.finance_summary, name='finance-summary'),
    path('bills/', views.finance_bills, name='finance-bills'),
    path('bills/<uuid:bill_id>/', views.finance_bill_detail, name='finance-bill-detail'),
    path('wages/', views.finance_wages, name='finance-wages'),
    path('wages/<uuid:summary_id>/', views.finance_wage_detail, name='finance-wage-detail'),
    path('by-site/', views.finance_by_site, name='finance-by-site'),
]
