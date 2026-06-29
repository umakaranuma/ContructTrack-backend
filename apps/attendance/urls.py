"""
Attendance URL patterns — accessed via the mobile API and owner dashboard.
These are included under /api/mobile/sites/:id/... in core/urls_mobile.py
and read-only under /api/sites/:id/attendance/ in sites/urls.py.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Worker roster management
    path('workers/', views.WorkerListCreateView.as_view(), name='worker-list-create'),
    path('workers/<uuid:pk>/', views.WorkerDetailView.as_view(), name='worker-detail'),

    # Daily attendance submission and retrieval
    path('attendance/', views.DailyAttendanceView.as_view(), name='attendance'),
    path('attendance/<str:log_date>/pay/', views.MarkWorkerPaidView.as_view(), name='attendance-pay'),

    # Summary per day
    path('attendance/summary/', views.AttendanceSummaryView.as_view(), name='attendance-summary'),
]
