from django.urls import path
from camera import views

urlpatterns = [
    path("scan-qr/", views.QRAndPlateScanAPIView.as_view(), name="scan-qr"),
]
