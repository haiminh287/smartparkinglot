from django.urls import path, re_path, include
from django.contrib import admin
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.authentication import JWTAuthentication


schema_view = get_schema_view(
    openapi.Info(
        title="Smart Parking API",
        default_version='v1',
        description="APIs for Smart Parking app",
        contact=openapi.Contact(email="minhht2k4@gmail.com"),
        license=openapi.License(name="Beta@2025"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),

)
urlpatterns = [
    path('api/users/', include('users.urls')),
    path("api/parkinglots/", include("parkinglot.urls")),
    path("api/bookings/", include("booking_app.urls")),
    path("api/cameras/", include("camera.urls")),
    path("api/chatbot/", include("chatbot.urls")),

    path('admin/', admin.site.urls),
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0),
            name='schema-json'),
    re_path(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0),
            name='schema-swagger-ui'),
    re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0),
            name='schema-redoc'),
]
