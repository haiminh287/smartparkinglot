from rest_framework import serializers
from booking_app.models import Booking, PackagePricing
from datetime import timedelta, datetime
from django.shortcuts import get_object_or_404
from parkinglot.models import CarSlot
from parkinglot.serializers import FloorSerializer, ZoneSerializer, CarSlotSerializer
from users.serializers import UserSerializer, VehicleSerializer


class PackagePricingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackagePricing
        fields = ["id", "package_type", "vehicle_type", "price"]


class BookingDetailSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    vehicle = VehicleSerializer(read_only=True)
    floor = FloorSerializer(read_only=True)
    zone = ZoneSerializer(read_only=True)
    car_slot = CarSlotSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = "__all__"
        read_only_fields = ['user', 'is_checked_in',
                            'is_checked_out', 'created_at', 'updated_at']


class BookingSerializer(serializers.ModelSerializer):
    bookings = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False
    )

    class Meta:
        model = Booking
        fields = "__all__"
        read_only_fields = ['user', 'created_at', 'updated_at']

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['user'] = request.user

        bookings_data = validated_data.pop('bookings', [])
        created_bookings = []

        vehicle = validated_data['vehicle']
        is_bike = vehicle.vehicle_type.lower() == "motorbike"

        if bookings_data:
            for day_slot in bookings_data:
                day = day_slot.get('date')
                slot = day_slot.get('slot')

                booking_data = validated_data.copy()

                if validated_data['package_type'] == 'custom':
                    try:
                        day_datetime = datetime.strptime(day, "%Y-%m-%d")
                    except ValueError:
                        raise serializers.ValidationError(
                            f"Invalid date format: {day}. Expected YYYY-MM-DD."
                        )

                    booking_data['start_time'] = day_datetime
                    booking_data['end_time'] = day_datetime + timedelta(days=1)

                    daily_price = PackagePricing.objects.get(
                        package_type="custom", vehicle_type=vehicle.vehicle_type).price
                    booking_data['price'] = daily_price

                elif validated_data['package_type'] in ['monthly', 'weekly']:
                    pricing = PackagePricing.objects.get(
                        package_type=validated_data['package_type'], vehicle_type=vehicle.vehicle_type).price
                    booking_data['price'] = pricing
                if is_bike:
                    booking_data.pop("car_slot", None)
                    print(">>> Booking data (bike):", booking_data)
                    booking = Booking.objects.create(**booking_data)
                else:
                    car_slot_instance = get_object_or_404(CarSlot, id=slot)
                    booking_data['car_slot'] = car_slot_instance
                    print(">>> Booking data (car):", booking_data)
                    booking = Booking.objects.create(**booking_data)

                created_bookings.append(booking)

            return created_bookings[-1]
