from django.db import models
from users.models import VehicleType


class ParkingLot(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()

    def __str__(self):
        return self.name


class Floor(models.Model):
    parking_lot = models.ForeignKey(
        ParkingLot, on_delete=models.CASCADE, related_name="floors")
    level = models.IntegerField()

    def __str__(self):
        return f"{self.parking_lot.name} - Tầng {self.level}"


class Zone(models.Model):
    floor = models.ForeignKey(
        Floor, on_delete=models.CASCADE, related_name="zones")
    name = models.CharField(max_length=50)
    vehicle_type = models.CharField(max_length=10, choices=VehicleType.choices)
    capacity = models.IntegerField(default=50)


class Camera(models.Model):
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField(default=80)
    zone = models.ForeignKey(
        Zone, on_delete=models.CASCADE, related_name="cameras", null=True, blank=True)

    def __str__(self):
        return self.name


class CarSlot(models.Model):
    zone = models.ForeignKey(
        Zone, on_delete=models.CASCADE, related_name="slots")
    code = models.CharField(max_length=20)
    is_available = models.BooleanField(default=True)
    camera = models.ForeignKey(
        Camera, on_delete=models.SET_NULL, null=True, blank=True, related_name="slots")
    map_x = models.FloatField(null=True, blank=True)
    map_y = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.zone} - Slot {self.code}"

    def save(self, *args, **kwargs):
        """Tự động cập nhật available_count của Zone khi CarSlot thay đổi"""
        super().save(*args, **kwargs)
        self.zone.update_available_count()
