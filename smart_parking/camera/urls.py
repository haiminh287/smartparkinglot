from django.urls import path
from camera import views

urlpatterns = [
    path("scan-qr/", views.QRAndPlateScanAPIView.as_view(), name="scan-qr"),
    path("scan-parked/", views.QRCheckParkedAPIView.as_view(), name="scan-parked"),
    path("scan-checkout/", views.QRCheckOutAPIView.as_view(), name="scan-checkout"),
    path("slot-detection/", views.SlotDetectionAPIView.as_view(), name="slot-detection"),
    path("create-booking/", views.CreateBookingFromPlateAPIView.as_view(), name="create-booking"),
    path("rfid-parked/", views.RFIDCheckParkedAPIView.as_view(), name="rfid-parked"),
    path("rfid-payment/", views.MoMoIPNView.as_view(), name="rfid-payment"),
]
