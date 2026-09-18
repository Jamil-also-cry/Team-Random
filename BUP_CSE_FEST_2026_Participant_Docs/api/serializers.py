"""
DRF serializers wrapping the existing pydantic schemas.

We mirror the pydantic models verbatim so the HTTP request/response contract
is unchanged from the previous FastAPI app. The pydantic models still drive
validation in the service layer; DRF handles JSON parsing/rendering only.
"""
from rest_framework import serializers


class HourDataSerializer(serializers.Serializer):
    hour = serializers.IntegerField(min_value=0, max_value=23)
    demand_kwh = serializers.FloatField(min_value=0.0)
    solar_kwh = serializers.FloatField(min_value=0.0)
    tariff_bdt_per_kwh = serializers.FloatField(min_value=0.0)


class BatteryDataSerializer(serializers.Serializer):
    capacity_kwh = serializers.FloatField(min_value=0.0)
    initial_energy_kwh = serializers.FloatField(min_value=0.0)
    minimum_energy_kwh = serializers.FloatField(min_value=0.0)
    max_charge_kwh_per_hour = serializers.FloatField(min_value=0.0)
    max_discharge_kwh_per_hour = serializers.FloatField(min_value=0.0)


class OptimizeRequestSerializer(serializers.Serializer):
    scenario_id = serializers.CharField(min_length=1)
    operator_notes = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        min_length=1,
        max_length=3,
    )
    hours = serializers.ListField(
        child=HourDataSerializer(),
        min_length=24,
        max_length=24,
    )
    battery = BatteryDataSerializer()

    def validate_hours(self, hours):
        extracted = [h["hour"] for h in hours]
        if extracted != list(range(24)):
            raise serializers.ValidationError(
                "hours array must contain exactly 24 entries with hours ordered 0 through 23"
            )
        return hours
