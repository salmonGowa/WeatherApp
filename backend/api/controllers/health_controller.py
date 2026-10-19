from rest_framework.response import Response

from .base import BaseController


class HealthController(BaseController):
    def list(self, request):
        return Response({"status": "ok"})
