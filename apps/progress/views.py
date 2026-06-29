# Progress views — main logic in mobile views
from rest_framework.decorators import api_view, permission_classes
from apps.core.utils import success_response
from apps.core.permissions import IsOwnerOrManager


@api_view(['GET'])
@permission_classes([IsOwnerOrManager])
def placeholder(request):
    return success_response('Use /api/mobile/sites/:id/progress/ or /api/sites/:id/logs/')
