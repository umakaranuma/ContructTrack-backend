"""
Report generation views.
Generation is async — POST returns immediately with report_id;
client polls /api/reports/:id/download/ until status == 'ready'.
"""
import logging
from django.http import HttpResponseRedirect
from rest_framework.decorators import api_view, permission_classes

from apps.core.utils import success_response, error_response
from apps.core.permissions import IsOwner
from apps.tenants.models import Tenant
from .models import Report
from .serializers import ReportGenerateSerializer, ReportSerializer
from .tasks import generate_report_task

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsOwner])
def list_reports(request):
    """GET /api/reports/ — list previously generated reports for this tenant."""
    tenant = Tenant.objects.filter(owner=request.user).first()
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    from apps.core.utils import paginate_queryset
    reports = Report.objects.filter(tenant=tenant).select_related('site').order_by('-created_at')

    site_id = request.query_params.get('site_id')
    if site_id:
        reports = reports.filter(site_id=site_id)
    page  = int(request.query_params.get('page', 1))
    limit = int(request.query_params.get('limit', 20))
    paged, total, pages = paginate_queryset(reports, page, limit)
    return success_response('Reports retrieved.', {
        'results': ReportSerializer(paged, many=True).data,
        'total': total, 'page': page, 'total_pages': pages,
    })


@api_view(['POST'])
@permission_classes([IsOwner])
def generate_report(request):
    """
    POST /api/reports/generate/
    Creates a report record and queues a Celery task to build the file.
    """
    tenant = Tenant.objects.filter(owner=request.user).first()
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    # Check feature flags based on report type and package
    report_type = request.data.get('report_type', '')
    if report_type == 'bank_loan' and not tenant.has_feature('bank_report'):
        return error_response('Bank loan reports require a Pro or Enterprise plan.', {}, 403)
    if report_type == 'subcontractor' and not tenant.has_feature('subcontractor'):
        return error_response('Subcontractor reports require an Enterprise plan.', {}, 403)

    serializer = ReportGenerateSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response('Validation failed.', serializer.errors, 422)

    report = serializer.save(
        tenant=tenant,
        generated_by=request.user,
        status='pending',
    )

    # Queue async generation — task updates report.status and report.file_url when done
    generate_report_task.delay(str(report.id))

    return success_response('Report generation queued.', ReportSerializer(report).data, 202)


@api_view(['GET'])
@permission_classes([IsOwner])
def download_report(request, report_id):
    """
    GET /api/reports/:id/download/
    Returns the file_url when ready; 202 while still generating.
    """
    tenant = Tenant.objects.filter(owner=request.user).first()
    if not tenant:
        return error_response('Tenant not found.', {}, 404)

    try:
        report = Report.objects.get(id=report_id, tenant=tenant)
    except Report.DoesNotExist:
        return error_response('Report not found.', {}, 404)

    if report.status == 'ready' and report.file_url:
        return success_response('Report ready.', {
            'status': 'ready',
            'file_url': report.file_url,
        })
    elif report.status == 'failed':
        return error_response('Report generation failed. Please try again.', {'status': 'failed'}, 500)
    else:
        return success_response('Report is still generating.', {
            'status': report.status,
            'report_id': str(report.id),
        }, 202)
