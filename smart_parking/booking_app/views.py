from rest_framework import viewsets, permissions
from booking_app import models, serializers, services
from rest_framework import generics, parsers
from rest_framework.response import Response
from rest_framework.decorators import action


class PackagePricingListView(generics.ListAPIView):
    queryset = models.PackagePricing.objects.all()
    serializer_class = serializers.PackagePricingSerializer
    permission_classes = [permissions.AllowAny]


class BookingViewSet(viewsets.ModelViewSet):
    queryset = models.Booking.objects.all()
    serializer_class = serializers.BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return serializers.BookingDetailSerializer
        return self.serializer_class

    def get_queryset(self):
        user = self.request.user
        queryset = self.queryset
        vehicle_type = self.request.query_params.get("vehicle_type")
        if vehicle_type:
            queryset = queryset.filter(vehicle__vehicle_type=vehicle_type)
        queryset = queryset.filter(user=user)
        return queryset

    @action(detail=True, methods=["get"], url_path="pay")
    def pay_booking(self, request, pk=None):
        booking = self.get_object()
        if booking.payment_status == models.PaymentStatus.COMPLETED:
            return Response({"detail": "Booking already paid."}, status=400)
        momo_response = services.get_qr_momo(
            booking.id, booking.price, '/booking-history', '/booking-history')
        if momo_response.status_code == 200:
            pay_url = momo_response.json().get('payUrl')
            if pay_url:
                return Response({"pay_url": pay_url}, status=200)

        return Response({"detail": "Payment init failed."}, status=400)

    @action(detail=True, methods=["post"], url_path="confirm-payment")
    def confirm_payment(self, request, pk=None):
        booking = self.get_object()
        result_code = request.data.get("resultCode")

        if str(result_code) == "0":
            booking.payment_status = models.PaymentStatus.COMPLETED
            booking.save()
            return Response({"detail": "Payment confirmed"}, status=200)

        booking.payment_status = models.PaymentStatus.FAILED
        booking.save()
        return Response({"detail": "Payment failed"}, status=400)

    @action(detail=True, methods=["post"], url_path="update-status")
    def update_status(self, request, pk=None):
        booking = self.get_object()
        payment_status = request.data.get("payment_status")
        booking.payment_status = payment_status
        booking.save()
        return Response({"detail": "Update status successfully"}, status=200)
