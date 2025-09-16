from django.db import models
from users.models import User, Vehicle, VehicleType
from parkinglot.models import Floor, Zone, CarSlot
from core.models import BaseModel


class PackageType(models.TextChoices):
    MONTHLY = "monthly", "Theo tháng"
    WEEKLY = "weekly", "Theo tuần"
    CUSTOM = "custom", "Chọn ngày"


class PaymentType(models.TextChoices):
    ONLINE = 'online', 'Online'
    ON_EXIT = 'on_exit', 'Thanh toán khi lấy xe'


class PackagePricing(BaseModel):
    package_type = models.CharField(max_length=10, choices=PackageType.choices)
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices, default=VehicleType.CAR
    )
    price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.get_package_type_display()} - {self.price}"


class CheckInStatus(models.TextChoices):
    CHECKED_IN = "checked_in", "Đã check-in"
    NOT_CHECKED_IN = "not_checked_in", "Chưa check-in"
    CHECKED_OUT = "checked_out", "Đã check-out"
    PARKED = "parked", "Đã đậu vào chỗ đậu xe"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Chưa thanh toán"
    COMPLETED = "completed", "Đã thanh toán"
    FAILED = "failed", "Thanh toán thất bại"


class Booking(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="bookings"
    )

    package_type = models.CharField(max_length=10, choices=PackageType.choices)

    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)

    floor = models.ForeignKey(
        Floor, on_delete=models.CASCADE)
    zone = models.ForeignKey(
        Zone, on_delete=models.CASCADE, related_name="bookings")
    car_slot = models.ForeignKey(
        CarSlot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bookings"
    )

    payment_type = models.CharField(
        max_length=10, choices=PaymentType.choices, default=PaymentType.ONLINE)
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )

    check_in_status = models.CharField(
        max_length=20, choices=CheckInStatus.choices, default=CheckInStatus.NOT_CHECKED_IN
    )
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.id} - {self.vehicle.license_plate} | {self.start_time.date()}"

class RFIDTag(models.Model):
    rfid_code = models.CharField(max_length=100, unique=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"RFID {self.rfid_code}"

class BookingRFID(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='rfid_info')
    rfid_tag = models.OneToOneField(RFIDTag, on_delete=models.CASCADE, related_name='booking_info')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"RFID {self.rfid_code} for booking {self.booking.id}"
    
