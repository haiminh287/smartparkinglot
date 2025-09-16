from django.urls import path, include
from rest_framework.routers import DefaultRouter
from parkinglot import views

router = DefaultRouter()
router.register(r'', views.ParkingLotViewSet)
router.register(r'floors', views.FloorViewSet)
router.register(r'zones', views.ZoneViewSet)
router.register(r'carslots', views.CarSlotViewSet)
router.register(r'cameras', views.CameraViewSet)
router.register(r'mapnodes', views.MapNodeViewSet)
urlpatterns = [
    path('', include(router.urls)),
]
