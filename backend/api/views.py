"""Thin ViewSets that delegate every action to api/controllers."""

from rest_framework import viewsets

from .controllers import (
    GeocodeController,
    HealthController,
    HeatmapController,
    PlanController,
)


class HealthViewSet(viewsets.ViewSet):
    controller = HealthController()

    def list(self, request):
        return self.controller.list(request)


class GeocodeViewSet(viewsets.ViewSet):
    controller = GeocodeController()

    def list(self, request):
        return self.controller.list(request)


class PlanViewSet(viewsets.ViewSet):
    controller = PlanController()

    def create(self, request):
        return self.controller.create(request)


class HeatmapViewSet(viewsets.ViewSet):
    controller = HeatmapController()

    def create(self, request):
        return self.controller.create(request)
