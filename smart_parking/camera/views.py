

# # === Các hàm camera ===
from booking_app.models import Booking, CheckInStatus
import os
import time
import easyocr
from ultralytics import YOLO
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
import re
import base64
import cv2
from pyzbar.pyzbar import decode


def scan_qr_from_camera(camera_url):
    cap = cv2.VideoCapture(camera_url)
    if not cap.isOpened():
        return None

    ret, frame = cap.read()
    cap.release()

    if not ret:
        return None

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    codes = decode(gray)

    if codes:
        # Extract the first QR code's data
        qr_data = codes[0].data.decode("utf-8")  # Decode bytes to string
        return qr_data
    return None


# camera/views.py


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


class QRAndPlateScanAPIView(APIView):
    """
    API quét QR => lấy idBooking => nhận diện biển số => đối chiếu => update check-in
    """

    def get(self, request):
        qr_cam_url = "http://192.168.100.130:4747/video"
        plate_cam_url = "http://192.168.100.130:4747/video"
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
        time.sleep(5)

        detected_plate, frame_plate, plate_img = scan_plate_from_camera(
            plate_cam_url, recognizer
        )
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

        # --- B5: Update check-in ---
        booking.check_in_status = CheckInStatus.CHECKED_IN
        booking.save()

        # Encode frame gốc và ảnh biển số để trả về
        _, buffer_frame = cv2.imencode(".jpg", frame_plate)
        frame_b64 = base64.b64encode(buffer_frame).decode()

        _, buffer_plate = cv2.imencode(".jpg", plate_img)
        plate_b64 = base64.b64encode(buffer_plate).decode()

        return Response({
            "message": "Check-in thành công",
            "booking_id": booking.id,
            "license_plate": detected_plate,
            "frame_image": frame_b64,
            "plate_image": plate_b64
        }, status=status.HTTP_200_OK)
