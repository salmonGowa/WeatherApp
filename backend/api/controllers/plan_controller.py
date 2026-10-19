from rest_framework.response import Response

from ..serializers import PlanRequestSerializer
from ..services import planner
from .base import BaseController, upstream_errors


class PlanController(BaseController):
    @upstream_errors
    def create(self, request):
        body = PlanRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        trip = planner.TripRequest(
            origin=(data["origin"]["lat"], data["origin"]["lon"]),
            destination=(
                data["destination"]["lat"],
                data["destination"]["lon"],
            ),
            departure=data["departure"],
            load_lb=data["load_lb"],
            interval_miles=data["interval_miles"],
            apply_hos=data["apply_hos"],
        )
        return Response(planner.plan_trip(trip))
