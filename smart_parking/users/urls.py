from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from users import views

router = DefaultRouter()
router.register(r'', views.UserViewSet, basename='user')
router.register(r'vehicles', views.VehicleViewSet, basename='vehicle')
urlpatterns = [
    path('', include(router.urls)),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(),

         name='token_refresh'),  # refresh token
    # path('registry/', views.RegistryUserView.as_view(), name='user_registry')
]
