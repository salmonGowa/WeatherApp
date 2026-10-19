from rest_framework.response import Response

from ..serializers import GeocodeQuerySerializer
from ..services import geocoding
from .base import BaseController, upstream_errors


class GeocodeController(BaseController):
    @upstream_errors
    def list(self, request):
        params = GeocodeQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        return Response(
            {"results": geocoding.search(params.validated_data["q"])}
        )
