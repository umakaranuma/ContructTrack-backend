from django.urls import path
from . import views

urlpatterns = [
    path('generate/', views.generate_report, name='report-generate'),
    path('<uuid:report_id>/download/', views.download_report, name='report-download'),
]
