

from booking_app.models import Booking, CheckInStatus,PackageType, PaymentType, PaymentStatus,PackagePricing, BookingRFID, RFIDTag
from users.models import User, Vehicle, VehicleType
from parkinglot.models import CarSlot, Floor, Zone
from datetime import datetime, timedelta
from booking_app import services
import os
import time
import easyocr
from ultralytics import YOLO
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
import re
import cv2
from pyzbar.pyzbar import decode
import serial
import serial.tools.list_ports
import time
from camera.ai.slot_detector import detect_slot_occupancy
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema



def send_command(arduino_port,baud_rate,command):
    try:
        ports = serial.tools.list_ports.comports()
        available_ports = [port.device for port in ports]
        if arduino_port not in available_ports:
            print(f"❌ Cổng {arduino_port} không khả dụng. Các cổng hiện có: {available_ports}")
            return

        with serial.Serial(arduino_port, baud_rate, timeout=2) as ser:
            time.sleep(2)  
            ser.write((command + '\n').encode())
            print(f"📤 Đã gửi lệnh: {command}")
            while ser.in_waiting:
                response = ser.readline().decode().strip()
                if response:
                    print(f"📥 Arduino: {response}")

    except serial.SerialException as e:
        print(f"❌ Không kết nối được với Arduino: {e}")


def scan_qr_from_camera(camera_url, timeout=30):
    cap = cv2.VideoCapture(camera_url)
    if not cap.isOpened():
        print("❌ Không mở được camera QR.")
        return None

    start_time = time.time()
    qr_data = None

    print("📷 Bắt đầu quét QR...")

    while time.time() - start_time < timeout:
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        codes = decode(gray)

        if codes:
            qr_data = codes[0].data.decode("utf-8")
            print(f"✅ QR code phát hiện: {qr_data}")
            break

        # Tạm dừng một chút để giảm tải CPU
        time.sleep(0.5)

    cap.release()

    if not qr_data:
        print("⚠️ Hết thời gian chờ mà không quét được QR.")
    return qr_data



class LicensePlateRecognizer:
    def __init__(self, model_path="camera/ml_models/license-plate-finetune-v1m.pt", use_gpu=True):
        self.model = YOLO(model_path)
        self.reader = easyocr.Reader(['en'], gpu=use_gpu)

    def recognize_plate_from_image(self, image, conf_threshold=0.5):
        results = self.model.predict(source=image, conf=conf_threshold)
        plates = []

        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()
            for x_min, y_min, x_max, y_max in boxes:
                x_min, y_min, x_max, y_max = map(
                    int, [x_min, y_min, x_max, y_max])
                plate_img = image[y_min:y_max, x_min:x_max]

                ocr_result = self.reader.readtext(plate_img)
                plate_text = ''.join([text for (_, text, _) in ocr_result])
                plate_text = re.sub(r'[^A-Za-z0-9]', '', plate_text).upper()

                if plate_text:
                    plates.append(plate_text)

        return plates


def is_frame_sharp(frame, threshold=100.0):
    """
    Kiểm tra độ nét frame.
    Trả về True nếu frame đủ nét.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    variance = lap.var()
    return variance >= threshold


def scan_plate_from_camera(cam_url: str, recognizer: LicensePlateRecognizer, max_wait=30, sharpness_threshold=100.0):
    cap = cv2.VideoCapture(cam_url)
    if not cap.isOpened():
        return None, None, None

    detected_plate, frame_plate, plate_img = None, None, None
    start_time = time.time()

    while time.time() - start_time < max_wait:
        ret, frame = cap.read()
        if not ret:
            continue

        if not is_frame_sharp(frame, sharpness_threshold):
            print("Camera chưa nét, đang chờ...")
            time.sleep(0.5)
            continue

        plates = recognizer.recognize_plate_from_image(frame)
        if plates:
            detected_plate = plates[0]
            frame_plate = frame
            result = recognizer.model.predict(source=frame, conf=0.5)[0]
            boxes = result.boxes.xyxy.cpu().numpy()
            if len(boxes) > 0:
                x_min, y_min, x_max, y_max = map(int, boxes[0])
                plate_img = frame[y_min:y_max, x_min:x_max]

                os.makedirs("plates", exist_ok=True)
                cv2.imwrite(f"plates/{detected_plate}.jpg", plate_img)

            print(f"Biển số nhận diện: {detected_plate}")
            break

        print("Đang theo dõi biển số...")

    cap.release()
    # cv2.destroyAllWindows()
    return detected_plate, frame_plate, plate_img


def scan_plate_from_image(image, recognizer: LicensePlateRecognizer, save_image=True):
    """
    Nhận diện biển số từ 1 ảnh đầu vào.
    Trả về: (biển số, ảnh gốc, ảnh crop biển số)
    """
    if image is None:
        print("❌ Ảnh đầu vào không hợp lệ.")
        return None, None, None

    plates = recognizer.recognize_plate_from_image(image)
    if not plates:
        print("❌ Không nhận diện được biển số.")
        return None, image, None

    detected_plate = plates[0]
    result = recognizer.model.predict(source=image, conf=0.5)[0]
    boxes = result.boxes.xyxy.cpu().numpy()

    plate_img = None
    if len(boxes) > 0:
        x_min, y_min, x_max, y_max = map(int, boxes[0])
        plate_img = image[y_min:y_max, x_min:x_max]

        if save_image:
            os.makedirs("plates", exist_ok=True)
            cv2.imwrite(f"plates/{detected_plate}.jpg", plate_img)

    print(f"✅ Biển số nhận diện từ ảnh: {detected_plate}")
    return detected_plate, image, plate_img



class QRAndPlateScanAPIView(APIView):

    def get(self, request):
        qr_cam_url = "http://192.168.1.23:4747/video"
        plate_cam_url = "http://192.168.1.23:4747/video"
        recognizer = LicensePlateRecognizer()

        # --- B1: Quét QR ---
        qr_data = scan_qr_from_camera(qr_cam_url)
        if not qr_data:
            return Response(
                {"error": "Không quét được QR"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- B2: Tìm Booking ---
        try:
            booking = Booking.objects.select_related("vehicle").get(id=qr_data)
        except Booking.DoesNotExist:
            return Response(
                {"error": f"Booking {qr_data} không tồn tại"},
                status=status.HTTP_404_NOT_FOUND
            )
        plate_number_expected = booking.vehicle.license_plate
        print(f"Booking {booking.id} - Biển số: {plate_number_expected}")

        # detected_plate, frame_plate, plate_img = scan_plate_from_camera(
        #     plate_cam_url, recognizer
        # )
        image = cv2.imread("bienso.jpg")
        detected_plate, frame_plate, plate_img = scan_plate_from_image(
            image, recognizer
        )
        print(detected_plate, plate_number_expected)
        if not detected_plate:
            return Response(
                {"error": "Không đọc được biển số"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        if detected_plate != plate_number_expected:
            return Response(
                {
                    "error": "Biển số không khớp với booking",
                    "expected": plate_number_expected,
                    "detected": detected_plate,
                },
                status=status.HTTP_400_BAD_REQUEST
            )        
        booking.check_in_status = CheckInStatus.CHECKED_IN
        booking.save()

        send_command("COM10",9600,"OPEN")
        # _, buffer_frame = cv2.imencode(".jpg", frame_plate)
        # frame_b64 = base64.b64encode(buffer_frame).decode()

        # _, buffer_plate = cv2.imencode(".jpg", plate_img)
        # plate_b64 = base64.b64encode(buffer_plate).decode()

        # location = {
        #     "floor": booking.floor.level if booking.floor else None,
        #     "zone": booking.zone.name if booking.zone else None,
        #     "slot": booking.car_slot.code if booking.car_slot else None,
        #     "map_x": booking.car_slot.map_x if booking.car_slot else None,
        #     "map_y": booking.car_slot.map_y if booking.car_slot else None,
        # }
        return Response({
            "message": "Check-in thành công",
            "booking_id": booking.id,
            "license_plate": detected_plate,
            
        }, status=status.HTTP_200_OK)
    


class QRCheckParkedAPIView(APIView):
    def get(self, request):
        qr_cam_url = "http://192.168.1.23:4747/video"  
        
        qr_data = scan_qr_from_camera(qr_cam_url)
        if not qr_data:
            return Response(
                {"error": "Không quét được mã QR"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            booking = Booking.objects.get(id=qr_data)
        except Booking.DoesNotExist:
            return Response(
                {"error": f"Booking {qr_data} không tồn tại"},
                status=status.HTTP_404_NOT_FOUND
            )

        if booking.check_in_status != CheckInStatus.CHECKED_IN:
            return Response(
                {"error": "Xe chưa được check-in ở cổng"},
                status=status.HTTP_400_BAD_REQUEST
            )
        booking.check_in_status = CheckInStatus.PARKED
        booking.save()

        send_command("COM10",9600,"OPEN")
        return Response({
            "message": "Xe đã vào chỗ đậu. Mở cửa thành công.",
            "booking_id": booking.id,
            "license_plate": booking.vehicle.license_plate,
            "slot": booking.car_slot.code if booking.car_slot else None,
        }, status=status.HTTP_200_OK)
    

class QRCheckOutAPIView(APIView):
    def get(self, request):
        qr_cam_url = "http://192.168.1.23:4747/video" 

        qr_data = scan_qr_from_camera(qr_cam_url)
        if not qr_data:
            return Response(
                {"error": "Không quét được mã QR"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            booking = Booking.objects.get(id=qr_data)
        except Booking.DoesNotExist:
            return Response(
                {"error": f"Booking {qr_data} không tồn tại"},
                status=status.HTTP_404_NOT_FOUND
            )

        if booking.check_in_status != CheckInStatus.PARKED:
            return Response(
                {"error": "Xe chưa được đậu vào chỗ hoặc đã check-out."},
                status=status.HTTP_400_BAD_REQUEST
            )

        booking.check_in_status = CheckInStatus.CHECKED_OUT
        booking.save()
  
        send_command("COM10", 9600, "OPEN")
        return Response({
            "message": "Xe đã rời khỏi chỗ đậu. Mở cửa thành công.",
            "booking_id": booking.id,
            "license_plate": booking.vehicle.license_plate,
            "slot": booking.car_slot.code if booking.car_slot else None,
        }, status=status.HTTP_200_OK)
    


class SlotDetectionAPIView(APIView):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'camera_url',
                openapi.IN_QUERY,
                description="Camera stream URL (ví dụ: http://192.168.1.100:4747/video)",
                type=openapi.TYPE_STRING,
                required=True
            )
        ]
    )
    def get(self, request):
        camera_url = request.query_params.get("camera_url")
        if not camera_url:
            return Response({"error": "Thiếu camera_url"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = detect_slot_occupancy(camera_url)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class CreateBookingFromPlateAPIView(APIView):
    def get(self, request):
        # camera_url = "http://192.168.1.23:4747/video"
        recognizer = LicensePlateRecognizer()

        # B1: Nhận diện biển số
        # plate = scan_plate_from_camera(camera_url, recognizer)
        image = cv2.imread("bienso.jpg")
        detected_plate, frame_plate, plate_img = scan_plate_from_image(
            image, recognizer
        )
        if not detected_plate:
            return Response({"error": "Không nhận diện được biển số"}, status=status.HTTP_400_BAD_REQUEST)

        print("✅ Biển số:", detected_plate)

        try:
            user = User.objects.get(id=3)
        except User.DoesNotExist:
            return Response({"error": "User không tồn tại"}, status=status.HTTP_404_NOT_FOUND)

        vehicle, created = Vehicle.objects.get_or_create(
            license_plate=detected_plate,
            defaults={
                "user": user,
                "vehicle_type": VehicleType.CAR
            }
        )

        today = datetime.now()
        start_time = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)
        available_slot = CarSlot.objects.filter(is_available=True).exclude(
            bookings__start_time__lt=end_time,
            bookings__end_time__gt=start_time
        ).first()

        if not available_slot:
            return Response({"error": "Không còn chỗ đậu xe trống"}, status=status.HTTP_400_BAD_REQUEST)
        price = PackagePricing.objects.get(
            package_type=PackageType.CUSTOM,
            vehicle_type=vehicle.vehicle_type
        ).price

        booking = Booking.objects.create(
            user=user,
            vehicle=vehicle,
            package_type=PackageType.CUSTOM,
            start_time=start_time,
            end_time=end_time,
            floor=available_slot.zone.floor,
            zone=available_slot.zone,
            car_slot=available_slot,
            payment_type=PaymentType.ON_EXIT,
            payment_status=PaymentStatus.PENDING,
            check_in_status=CheckInStatus.CHECKED_IN,
            price=price
        )

        rfid = RFIDTag.objects.filter(is_used=False).first()
        BookingRFID.objects.create(
            booking=booking,
            rfid_tag=rfid
        )
        # B6: Mở cửa
        send_command("COM10", 9600, "OPEN")

        return Response({
            "message": "Tạo booking thành công & mở cửa",
            "booking_id": booking.id,
            "license_plate": detected_plate,
            "car_slot": available_slot.code
        }, status=status.HTTP_201_CREATED)
    



class MoMoIPNView(APIView):
    def post(self, request):
        data = request.data
        print("📥 Nhận IPN từ MoMo:", data)

        result_code = int(data.get("resultCode", -1))
        extra_data = data.get("extraData") 
        amount = data.get("amount")

        if result_code == 0:
            try:
                booking_id = int(extra_data)
                booking = Booking.objects.get(id=booking_id)

                if booking.payment_status != PaymentStatus.COMPLETED:
                    booking.payment_status = PaymentStatus.COMPLETED
                    booking.save()

                    
                    if booking.check_in_status == CheckInStatus.PARKED:
                        send_command("COM10", 9600, "OPEN")

                    return Response({
                        "message": "Thanh toán thành công và đã cập nhật booking.",
                        "booking_id": booking.id,
                        "amount": amount,
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({"message": "Booking đã được thanh toán trước đó."})

            except Booking.DoesNotExist:
                return Response({"error": "Không tìm thấy booking."}, status=404)
            except Exception as e:
                return Response({"error": str(e)}, status=500)

        return Response({"message": "Thanh toán thất bại hoặc bị huỷ."}, status=400)

class RFIDCheckParkedAPIView(APIView):
    def post(self, request):
        uid = request.data.get("uid")
        slot = request.data.get("slot")
        if not uid:
            return Response(
                {"error": "Thiếu UID thẻ RFID"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rfid_tag = RFIDTag.objects.filter(rfid_code=uid).first()
        if not rfid_tag:
            return Response(
                {"error": f"Không tìm thấy thẻ RFID với UID {uid}"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            bookingRFID = BookingRFID.objects.get(rfid_tag=rfid_tag)
        except BookingRFID.DoesNotExist:
            return Response(
                {"error": f"Không tìm thấy booking với UID {uid}"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        booking = bookingRFID.booking
        if booking.car_slot.code != slot:
            return Response(
                {"error": "Chỗ đậu không đúng với booking"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if booking.check_in_status == CheckInStatus.CHECKED_IN:
            booking.check_in_status = CheckInStatus.PARKED
            booking.save()
            send_command("COM10", 9600, "OPEN")
            return Response({
                "message": "Xe đã vào chỗ đậu. Mở cửa thành công.",
                "booking_id": booking.id,
                "license_plate": booking.vehicle.license_plate,
                "slot": booking.car_slot.code if booking.car_slot else None,
            }, status=status.HTTP_200_OK)

        elif booking.check_in_status == CheckInStatus.PARKED and booking.payment_status == PaymentStatus.COMPLETED:
            booking.check_in_status = CheckInStatus.CHECKED_OUT
            booking.save()
            send_command("COM10", 9600, "OPEN")
            return Response({
                "message": "Xe đã rời khỏi chỗ đậu. Đóng cửa thành công.",
                "booking_id": booking.id,
                "license_plate": booking.vehicle.license_plate,
            }, status=status.HTTP_200_OK)
        
        elif booking.check_in_status == CheckInStatus.PARKED and booking.payment_status == PaymentStatus.PENDING:
            momo_response = services.get_qr_momo(
            booking.id, booking.price, '/booking-history', 'rfid-payment')
            if momo_response.status_code == 200:
                qrCodeUrl = momo_response.json().get('qrCodeUrl')
                if qrCodeUrl:
                    return Response({"pay_url": qrCodeUrl}, status=200)
        
        return Response(
            {"error": "Trạng thái không hợp lệ để thực hiện hành động này."},
            status=status.HTTP_400_BAD_REQUEST
        )
    




