from django.urls import path
from . import views

urlpatterns = [
    path('summary/', views.finance_summary, name='finance-summary'),
    path('bills/', views.finance_bills, name='finance-bills'),
    path('wages/', views.finance_wages, name='finance-wages'),
    path('by-site/', views.finance_by_site, name='finance-by-site'),
]
