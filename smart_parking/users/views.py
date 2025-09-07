from django.shortcuts import render
from rest_framework import viewsets, generics, permissions, parsers
from rest_framework.response import Response
from rest_framework.decorators import action, permission_classes
from users import models, serializers
from django.db.models import Q, Exists, OuterRef


class UserViewSet(viewsets.ViewSet, generics.ListCreateAPIView):
    queryset = models.User.objects.filter(is_active=True)
    serializer_class = serializers.UserSerializer
    parser_classes = [parsers.MultiPartParser]
    # pagination_class = paginators.UserPaginator

    @action(methods=['get', 'patch'], url_path="current-user", detail=False, permission_classes=[permissions.IsAuthenticated])
    def get_current_user(self, request):
        if request.method.__eq__("PATCH"):
            u = request.user

            for key in request.data:
                if key in ['first_name', 'last_name']:
                    setattr(u, key, request.data[key])
                elif key.__eq__('password'):
                    u.set_password(request.data[key])

            u.save()
            return Response(serializers.UserSerializer(u).data)
        else:
            return Response(serializers.UserSerializer(request.user).data)

    def get_queryset(self):
        query = self.queryset
        print('request.user', self.request.user)
        kw = self.request.query_params.get('kw')
        if kw:
            query = query.filter(
                Q(username__icontains=kw) |
                Q(first_name__icontains=kw) |
                Q(last_name__icontains=kw)
            )
        query = query.exclude(username=self.request.user.username).annotate(
            pending_them=Exists(models.Connection.objects.filter(
                sender=self.request.user, receiver=OuterRef('id'), accepted=False)),
            pending_me=Exists(models.Connection.objects.filter(
                sender=OuterRef('id'), receiver=self.request.user, accepted=False)),
            connected=Exists(models.Connection.objects.filter(
                Q(sender=self.request.user, receiver=OuterRef('id')) |
                Q(sender=OuterRef('id'), receiver=self.request.user),
                accepted=True
            ))
        )
        return query

    @permission_classes([permissions.IsAuthenticated])
    def list(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentication credentials were not provided.'}, status=401)
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = serializers.UserStatusSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = serializers.UserStatusSerializer(queryset, many=True)
        return Response(serializer.data)


class VehicleViewSet(viewsets.ViewSet, generics.ListCreateAPIView):
    queryset = models.Vehicle.objects.all()
    serializer_class = serializers.VehicleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_authenticated:
            user_vehicles = self.queryset.filter(user=self.request.user)
            return user_vehicles if user_vehicles.exists() else self.queryset.none()
        return self.queryset.none()

    def perform_create(self, serializer):
        license_plate = serializer.validated_data.get('license_plate')
        vehicle_type = serializer.validated_data.get('vehicle_type')
        name = serializer.validated_data.get('name')

        vehicle, created = models.Vehicle.objects.get_or_create(
            user=self.request.user,
            license_plate=license_plate,
            defaults={
                'vehicle_type': vehicle_type,
                'name': name
            }
        )

        if not created:
            raise serializers.ValidationError(
                {"detail": "Vehicle with this license plate already exists for the user."}
            )
