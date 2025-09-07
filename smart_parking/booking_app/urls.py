from django.urls import path, include
from rest_framework.routers import DefaultRouter
from booking_app import views

router = DefaultRouter()
router.register(r'', views.BookingViewSet, basename='booking')


urlpatterns = [
    path('package-pricing/', views.PackagePricingListView.as_view(),
         name='package-pricing'),
    path('', include(router.urls)),
]
