from rest_framework import viewsets, permissions, generics
from parkinglot.models import ParkingLot, Floor, Zone, CarSlot, Camera,MapNode
from django.db.models import Q, Exists, OuterRef, F, Count

from booking_app.models import PackageType, Booking
from django.utils.dateparse import parse_date
from datetime import timedelta, datetime, time
from parkinglot.serializers import ParkingLotSerializer, FloorSerializer, ZoneSerializer, CarSlotSerializer, CameraSerializer, MapNodeSerializer


class ParkingLotViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = ParkingLot.objects.all()
    serializer_class = ParkingLotSerializer
    # permission_classes = [permissions.IsAuthenticated]


class FloorViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = Floor.objects.all()
    serializer_class = FloorSerializer
    # permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        parkinglot_id = self.request.query_params.get("parkinglot")
        queryset = self.queryset
        if parkinglot_id:
            queryset = queryset.filter(parkinglot_id=parkinglot_id)
        return queryset


class ZoneViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer

    def get_queryset(self):
        queryset = self.queryset
        params = self.request.query_params

        floor_id = params.get("floor")
        vehicle_type = params.get("vehicle_type")
        package_type = params.get("package_type")
        date_str = params.get("date")

        if floor_id:
            queryset = queryset.filter(floor_id=floor_id)
        if vehicle_type:
            queryset = queryset.filter(vehicle_type=vehicle_type)

        if package_type and date_str:
            start_date = parse_date(date_str)
            if start_date:
                
                if package_type == PackageType.WEEKLY:
                    end_date = start_date + timedelta(days=6)
                elif package_type == PackageType.MONTHLY:
                    end_date = start_date + timedelta(days=30)
                elif package_type == PackageType.CUSTOM:
                    end_date = start_date
                else:
                    end_date = start_date

                start_datetime = datetime.combine(start_date, time.min)
                end_datetime = datetime.combine(end_date, time.max)

                filter_q = Q(
                    bookings__start_time__lte=end_datetime,
                    bookings__end_time__gte=start_datetime
                )

                queryset = queryset.annotate(
                    active_bookings=Count(
                        "bookings", filter=filter_q, distinct=True),
                    unavailable_slots=Count("slots", filter=Q(
                        slots__is_available=False), distinct=True),
                ).annotate(
                    available_count=F(
                        "capacity") - F("active_bookings") - F("unavailable_slots")
                )
        else:
            queryset = queryset.annotate(
                unavailable_slots=Count("slots", filter=Q(
                    slots__is_available=False), distinct=True),
            ).annotate(
                available_count=F("capacity") - F("unavailable_slots")
            )

        return queryset


class CarSlotViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = CarSlot.objects.all()
    serializer_class = CarSlotSerializer
    # permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset
        params = self.request.query_params

        floor_id = params.get("floor_id")
        if floor_id:
            queryset = queryset.filter(zone__floor_id=floor_id)

        zone_id = params.get("zone")
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)

        package_type = params.get("package_type")
        date_str = params.get("date")
        filter_q = Q()

        if package_type and date_str:
            start_date = parse_date(date_str)
            if start_date:
                if package_type == PackageType.WEEKLY:
                    end_date = start_date + timedelta(days=6)
                elif package_type == PackageType.MONTHLY:
                    end_date = start_date + timedelta(days=30)
                elif package_type == PackageType.CUSTOM:
                    end_date = start_date
                else:
                    end_date = start_date

                
                start_datetime = datetime.combine(start_date, time.min)
                end_datetime = datetime.combine(end_date, time.max)

                filter_q = Q(start_time__lte=end_datetime,
                             end_time__gte=start_datetime)

        queryset = queryset.annotate(
            is_booked=Exists(
                Booking.objects.filter(
                    car_slot=OuterRef("pk")
                ).filter(filter_q)
            )
        )

        return queryset.distinct()


class CameraViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = Camera.objects.all()
    serializer_class = CameraSerializer
    permission_classes = [permissions.IsAuthenticated]


class MapNodeViewSet(viewsets.ViewSet, generics.ListAPIView):
    queryset = MapNode.objects.all()
    serializer_class = MapNodeSerializer
    # permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset
        floor_id = self.request.query_params.get("floor_id")
        if floor_id:
            queryset = queryset.filter(floor=floor_id)
        type = self.request.query_params.get("type")
        if type:
            queryset = queryset.filter(node_type=type)
        return queryset
    



