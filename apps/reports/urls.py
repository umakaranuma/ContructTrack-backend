from django.urls import path
from . import views

urlpatterns = [
    path('', views.list_reports, name='report-list'),
    path('generate/', views.generate_report, name='report-generate'),
    path('<uuid:report_id>/download/', views.download_report, name='report-download'),
]
