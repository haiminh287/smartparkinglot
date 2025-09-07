from rest_framework import serializers
from parkinglot import models


class ParkingLotSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ParkingLot
        fields = "__all__"


class FloorSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Floor
        fields = "__all__"


class ZoneSerializer(serializers.ModelSerializer):
    active_bookings = serializers.IntegerField(read_only=True)
    available_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = models.Zone
        fields = "__all__"


class CarSlotSerializer(serializers.ModelSerializer):
    is_booked = serializers.BooleanField(read_only=True)

    class Meta:
        model = models.CarSlot
        fields = "__all__"

    def validate(self, attrs):
        zone = attrs.get("zone")
        if zone.vehicle_type != "Car":
            raise serializers.ValidationError(
                "❌ Chỉ được thêm CarSlot vào Zone ô tô!")
        return attrs


class CameraSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Camera
        fields = "__all__"
