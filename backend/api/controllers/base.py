import logging
from functools import wraps

from rest_framework import status
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.response import Response

from ..services.http import ExternalServiceError

logger = logging.getLogger(__name__)


def upstream_errors(method):
    """Turn a third-party API failure into a readable 502 response."""

    @wraps(method)
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except ExternalServiceError as exc:
            logger.warning("External service failure: %s", exc)
            detail = f"The {exc.service} service is unavailable: {exc.message}"
            return Response(
                {"detail": detail, "service": exc.service},
                status=status.HTTP_502_BAD_GATEWAY,
            )

    return wrapper


class BaseController:
    """Request handling for one resource. ViewSets delegate each action
    here; actions a controller doesn't implement answer 405.
    """

    def list(self, request):
        raise MethodNotAllowed(request.method)

    def create(self, request):
        raise MethodNotAllowed(request.method)

    def retrieve(self, request, pk=None):
        raise MethodNotAllowed(request.method)

    def update(self, request, pk=None):
        raise MethodNotAllowed(request.method)

    def partial_update(self, request, pk=None):
        raise MethodNotAllowed(request.method)

    def destroy(self, request, pk=None):
        raise MethodNotAllowed(request.method)
