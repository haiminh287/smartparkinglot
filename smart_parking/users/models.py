from django.db import models
from django.contrib.auth.models import AbstractUser
from cloudinary.models import CloudinaryField
import re
from core.models import BaseModel


class User(AbstractUser):
    avatar = CloudinaryField(null=True)

    def __str__(self):
        return f"User: {self.username}"

    class Meta:
        db_table = 'User'
        verbose_name = "User"
        verbose_name_plural = "User"


class Connection(BaseModel):
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_connections')
    receiver = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='received_connections')
    accepted = models.BooleanField(default=False)

    class Meta:
        unique_together = ['sender', 'receiver']

    def __str__(self):
        return f'{self.sender.username} -> {self.receiver.username}'


class Message(BaseModel):
    connection = models.ForeignKey(
        Connection, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='my_messages')
    content = models.TextField()

    def __str__(self):
        return f'{self.user.username} -> {self.content}'


class VehicleType(models.TextChoices):
    CAR = 'Car', 'Xe Oto'
    MOTORBIKE = 'Motorbike', 'Xe Máy'


class Vehicle(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="vehicles")
    license_plate = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=10, choices=VehicleType.choices)
    name = models.CharField(max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        self.license_plate = re.sub(
            r'[^A-Za-z0-9]', '', self.license_plate).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.license_plate} ({self.vehicle_type})"
