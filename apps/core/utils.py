"""
Shared utility functions and custom DRF exception handler.
Centralising these avoids duplicating error-formatting logic across views.
"""
import random
import string
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Wraps DRF's default exception handler to ensure every error response
    follows the same envelope format as success responses.
    """
    response = exception_handler(exc, context)

    if response is not None:
        # Normalise the error payload into our standard envelope
        return Response({
            'is_success': False,
            'message': _extract_message(response.data),
            'result': response.data,
            'system_code': response.status_code,
        }, status=response.status_code)

    # Unhandled exception — log it and return 500
    logger.exception('Unhandled exception: %s', exc)
    return Response({
        'is_success': False,
        'message': 'An unexpected server error occurred.',
        'result': {},
        'system_code': 500,
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _extract_message(data):
    """Pull a human-readable message out of DRF's error detail dict."""
    if isinstance(data, dict):
        for key in ('detail', 'non_field_errors', 'message'):
            if key in data:
                val = data[key]
                return str(val[0]) if isinstance(val, list) else str(val)
        # Return first field error if no top-level detail
        first_key = next(iter(data))
        val = data[first_key]
        return f"{first_key}: {val[0] if isinstance(val, list) else val}"
    if isinstance(data, list) and data:
        return str(data[0])
    return str(data)


def api_response(success: bool, message: str, result=None, http_status: int = 200):
    """
    Standard response envelope used by all views.
    Keeps the API contract consistent regardless of which view generates it.
    """
    return Response({
        'is_success': success,
        'message': message,
        'result': result if result is not None else {},
        'system_code': http_status,
    }, status=http_status)


def success_response(message: str, result=None, http_status: int = 200):
    return api_response(True, message, result, http_status)


def error_response(message: str, result=None, http_status: int = 400):
    return api_response(False, message, result, http_status)


def generate_manager_reference_code():
    """
    Generate a unique MGR-XXXX code for manager self-identification.
    The code is displayed on the manager's profile; owners use it to look
    up and assign managers without needing their email.
    """
    from apps.accounts.models import User  # lazy import to avoid circular deps
    while True:
        code = 'MGR-' + ''.join(random.choices(string.digits, k=4))
        if not User.objects.filter(reference_code=code).exists():
            return code


def paginate_queryset(queryset, page: int, limit: int):
    """
    Simple manual pagination — avoids DRF pagination class boilerplate for
    endpoints that need custom filtering logic before paginating.
    Returns (page_data, total_count, total_pages).
    """
    total = queryset.count()
    offset = (page - 1) * limit
    data = queryset[offset: offset + limit]
    total_pages = (total + limit - 1) // limit if limit else 1
    return data, total, total_pages
