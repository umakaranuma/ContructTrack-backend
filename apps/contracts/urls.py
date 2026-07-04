from django.urls import path
from . import views

urlpatterns = [
    # Cross-site summary for Finance page
    path('summary/', views.contracts_summary, name='contracts-summary'),

    # Site contract (get/create/update)
    path('sites/<uuid:site_id>/', views.site_contract, name='site-contract'),

    # Payment certificates
    path('sites/<uuid:site_id>/certs/', views.add_payment_cert, name='add-payment-cert'),
    path('sites/<uuid:site_id>/certs/<uuid:cert_id>/', views.update_payment_cert, name='update-payment-cert'),

    # Subcontracts
    path('sites/<uuid:site_id>/subcontracts/', views.subcontract_list, name='subcontract-list'),
    path('sites/<uuid:site_id>/subcontracts/<uuid:sub_id>/', views.subcontract_detail, name='subcontract-detail'),
    path('sites/<uuid:site_id>/subcontracts/<uuid:sub_id>/payments/', views.add_subcontract_payment, name='add-sub-payment'),
    path('sites/<uuid:site_id>/subcontracts/<uuid:sub_id>/payments/<uuid:payment_id>/', views.delete_subcontract_payment, name='delete-sub-payment'),
]
