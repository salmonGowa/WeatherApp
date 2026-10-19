from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("health", views.HealthViewSet, basename="health")
router.register("geocode", views.GeocodeViewSet, basename="geocode")
router.register("plan", views.PlanViewSet, basename="plan")
router.register("heatmap", views.HeatmapViewSet, basename="heatmap")

urlpatterns = router.urls
