from django.urls import path
from users import consumers
websocket_urlpatterns = [
    path("chat/", consumers.ChatConsumer.as_asgi(), name="chat"),
]
