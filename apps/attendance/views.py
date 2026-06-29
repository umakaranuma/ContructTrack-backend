"""
Attendance views — worker roster and daily roll call.
Mobile endpoints (POST attendance, mark paid) are in apps/core/views_mobile.py.
These views serve the owner dashboard's read-only requests via /api/sites/:id/attendance/.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.utils import success_response, error_response
from apps.core.permissions import IsOwner, IsOwnerOrManager
from .models import Worker, DailyAttendance, AttendanceSummary
from .serializers import WorkerSerializer, DailyAttendanceSerializer, AttendanceSummarySerializer


class WorkerListCreateView(APIView):
    """
    GET  /api/mobile/sites/:siteId/workers/  — list roster for a site
    POST /api/mobile/sites/:siteId/workers/  — add a new worker to roster
    """
    permission_classes = [IsAuthenticated, IsOwnerOrManager]

    def get(self, request, site_pk):
        workers = Worker.objects.filter(site_id=site_pk, is_active=True).order_by('role', 'full_name')
        serializer = WorkerSerializer(workers, many=True)
        return success_response('Workers fetched.', serializer.data)

    def post(self, request, site_pk):
        serializer = WorkerSerializer(data={**request.data, 'site': str(site_pk)})
        if serializer.is_valid():
            serializer.save()
            return success_response('Worker added.', serializer.data, 201)
        return error_response('Validation failed.', serializer.errors, 422)


class WorkerDetailView(APIView):
    """
    GET / PATCH / DELETE a single worker from the roster.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrManager]

    def _get_worker(self, pk, site_pk):
        try:
            return Worker.objects.get(pk=pk, site_id=site_pk)
        except Worker.DoesNotExist:
            return None

    def get(self, request, site_pk, pk):
        w = self._get_worker(pk, site_pk)
        if not w:
            return error_response('Worker not found.', status=404)
        return success_response('OK', WorkerSerializer(w).data)

    def patch(self, request, site_pk, pk):
        w = self._get_worker(pk, site_pk)
        if not w:
            return error_response('Worker not found.', status=404)
        serializer = WorkerSerializer(w, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return success_response('Worker updated.', serializer.data)
        return error_response('Validation failed.', serializer.errors, 422)

    def delete(self, request, site_pk, pk):
        # Soft-delete — preserve history
        w = self._get_worker(pk, site_pk)
        if not w:
            return error_response('Worker not found.', status=404)
        w.is_active = False
        w.save(update_fields=['is_active'])
        return success_response('Worker removed from roster.')


class DailyAttendanceView(APIView):
    """
    GET  /api/mobile/sites/:siteId/attendance/?date=2025-06-17  — roll call for a date
    POST /api/mobile/sites/:siteId/attendance/                   — submit daily roll call
    """
    permission_classes = [IsAuthenticated, IsOwnerOrManager]

    def get(self, request, site_pk):
        date = request.query_params.get('date')
        qs = DailyAttendance.objects.filter(site_id=site_pk).select_related('worker')
        if date:
            qs = qs.filter(log_date=date)
        serializer = DailyAttendanceSerializer(qs.order_by('worker__full_name'), many=True)
        return success_response('Attendance fetched.', serializer.data)

    def post(self, request, site_pk):
        """
        Expects a list of attendance records: [{ worker, status, overtime_hours, ... }]
        All records for the day are saved together — idempotent on re-submit.
        """
        records = request.data.get('records', [])
        if not records:
            return error_response('No attendance records provided.', status=400)

        created = []
        for rec in records:
            rec['site'] = str(site_pk)
            rec['logged_by'] = str(request.user.id)
            # Compute total earned from daily rate
            worker = Worker.objects.filter(pk=rec.get('worker')).first()
            if worker:
                multiplier = 1.0 if rec.get('status') == 'present' else 0.5 if rec.get('status') == 'half' else 0.0
                overtime   = float(rec.get('overtime_hours', 0))
                hourly     = worker.daily_rate_lkr / 8
                rec['daily_rate_lkr']   = worker.daily_rate_lkr
                rec['total_earned_lkr'] = round(worker.daily_rate_lkr * multiplier + overtime * hourly, 2)

            att, _ = DailyAttendance.objects.update_or_create(
                site_id=site_pk,
                worker_id=rec.get('worker'),
                log_date=rec.get('log_date'),
                defaults={k: v for k, v in rec.items() if k not in ('worker', 'log_date', 'site')},
            )
            created.append(att)

        serializer = DailyAttendanceSerializer(created, many=True)
        return success_response('Attendance submitted.', serializer.data, 201)


class MarkWorkerPaidView(APIView):
    """
    PATCH /api/mobile/sites/:siteId/attendance/:log_date/pay/
    Marks a specific worker's attendance record as paid today.
    """
    permission_classes = [IsAuthenticated, IsOwnerOrManager]

    def patch(self, request, site_pk, log_date):
        worker_id = request.data.get('worker_id')
        if not worker_id:
            return error_response('worker_id is required.', status=400)

        try:
            att = DailyAttendance.objects.get(site_id=site_pk, worker_id=worker_id, log_date=log_date)
        except DailyAttendance.DoesNotExist:
            return error_response('Attendance record not found.', status=404)

        att.is_paid = True
        att.save(update_fields=['is_paid'])
        return success_response('Marked as paid.', DailyAttendanceSerializer(att).data)


class AttendanceSummaryView(APIView):
    """
    GET /api/mobile/sites/:siteId/attendance/summary/?month=2025-06
    Returns pre-aggregated summary rows for the owner dashboard calendar heatmap.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, site_pk):
        month = request.query_params.get('month')  # e.g. '2025-06'
        qs = AttendanceSummary.objects.filter(site_id=site_pk).order_by('log_date')
        if month:
            qs = qs.filter(log_date__startswith=month)
        serializer = AttendanceSummarySerializer(qs, many=True)
        return success_response('Summary fetched.', serializer.data)
