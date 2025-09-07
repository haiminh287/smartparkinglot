from django.db import models
from users.models import User
from core.models import BaseModel


class ChatHistory(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    response = models.TextField()

    def __str__(self):
        return f"ChatHistory {self.id} for User {self.user_id}"

    class Meta:
        ordering = ['-id']
