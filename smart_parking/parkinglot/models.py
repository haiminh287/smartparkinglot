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
    x1 = models.IntegerField(null=True, blank=True) 
    y1 = models.IntegerField(null=True, blank=True)
    x2 = models.IntegerField(null=True, blank=True)  
    y2 = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.zone} - Slot {self.code}"



class MapNodeType(models.TextChoices):
    GATE = "gate", "Cổng chính"
    ELEVATOR = "elevator", "Thang máy"
    ROAD = "road", "Đường đi"
    SLOT = "slot", "Chỗ đậu xe"


class MapNode(models.Model):
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name="map_nodes", null=True, blank=True)
    name = models.CharField(max_length=100)
    x = models.FloatField()
    y = models.FloatField()
    is_gate = models.BooleanField(default=False) 
    node_type = models.CharField(max_length=20,
        choices=MapNodeType.choices,
        default=MapNodeType.SLOT)
    slot = models.OneToOneField(CarSlot, on_delete=models.SET_NULL, null=True, blank=True, related_name="map_node")

    def __str__(self):
        return f"{self.name} ({self.floor})"


class DirectionType(models.TextChoices):
    STRAIGHT = "straight", "Đi thẳng"
    LEFT = "left", "Rẽ trái"
    RIGHT = "right", "Rẽ phải"
    ELEVATOR = "elevator", "Đi thang máy"
    RAMP = "ramp", "Đi theo dốc"
    DESTINATION = "destination", "Đến vị trí"


class MapEdge(models.Model):
    start = models.ForeignKey(MapNode, on_delete=models.CASCADE, related_name="edges_from")
    end = models.ForeignKey(MapNode, on_delete=models.CASCADE, related_name="edges_to")
    distance = models.FloatField(default=1.0)  # mét
    direction = models.CharField(
        max_length=20,
        choices=DirectionType.choices,
        default=DirectionType.STRAIGHT,
    )


    def __str__(self):
        return f"{self.start} -> {self.end} ({self.get_direction_display()})"
