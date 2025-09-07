from django.urls import path, include
from rest_framework.routers import DefaultRouter
from chatbot import views

router = DefaultRouter()
router.register(r'', views.ChatHistoryViewSet, basename='chathistory')

urlpatterns = [
    path('', include(router.urls)),
]
