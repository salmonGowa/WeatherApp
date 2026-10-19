from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

MAX_DAYS_AHEAD = 10
MAX_HOURS_IN_PAST = 24
MAX_LOAD_LB = 200_000


class LocationSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)
    label = serializers.CharField(
        required=False, allow_blank=True, max_length=300
    )


def validate_departure(value):
    now = timezone.now()
    if value < now - timedelta(hours=MAX_HOURS_IN_PAST):
        raise serializers.ValidationError(
            f"Departure can be at most {MAX_HOURS_IN_PAST} hours in the past."
        )
    if value > now + timedelta(days=MAX_DAYS_AHEAD):
        raise serializers.ValidationError(
            "Forecasts are only available for departures within "
            f"{MAX_DAYS_AHEAD} days."
        )
    return value


class PlanRequestSerializer(serializers.Serializer):
    origin = LocationSerializer()
    destination = LocationSerializer()
    departure = serializers.DateTimeField(validators=[validate_departure])
    load_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)
    interval_miles = serializers.ChoiceField(choices=[10, 25, 50])
    apply_hos = serializers.BooleanField(default=True)

    def validate(self, attrs):
        o, d = attrs["origin"], attrs["destination"]
        if abs(o["lat"] - d["lat"]) < 1e-4 and abs(o["lon"] - d["lon"]) < 1e-4:
            raise serializers.ValidationError(
                "Origin and destination must be different."
            )
        return attrs


class CoordinateListField(serializers.ListField):
    child = serializers.ListField(
        child=serializers.FloatField(), min_length=2, max_length=2
    )

    def to_internal_value(self, data):
        coords = super().to_internal_value(data)
        for lat, lon in coords:
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise serializers.ValidationError("Coordinates out of range.")
        return [(lat, lon) for lat, lon in coords]


class HeatmapRequestSerializer(serializers.Serializer):
    routes = serializers.ListField(
        child=CoordinateListField(min_length=2, max_length=20_000),
        min_length=1,
        max_length=3,
    )
    start = serializers.DateTimeField(validators=[validate_departure])
    load_lb = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LB)
    hours = serializers.IntegerField(min_value=1, max_value=48, default=48)
    corridor_miles = serializers.FloatField(
        min_value=5, max_value=100, default=40
    )


class GeocodeQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=2, max_length=200)
