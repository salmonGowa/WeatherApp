from rest_framework.response import Response

from ..serializers import HeatmapRequestSerializer
from ..services import heatmap
from .base import BaseController, upstream_errors


class HeatmapController(BaseController):
    @upstream_errors
    def create(self, request):
        body = HeatmapRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        return Response(
            heatmap.build_heatmap(
                routes=data["routes"],
                start=data["start"],
                load_lb=data["load_lb"],
                hours=data["hours"],
                corridor_miles=data["corridor_miles"],
            )
        )
