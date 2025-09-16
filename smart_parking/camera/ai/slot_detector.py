# ai/slot_detector.py

import cv2
from camera.ai.yolo import get_yolo_model
from parkinglot.models import CarSlot, Camera

def is_overlap(boxA, boxB, threshold=0.3):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    if boxAArea == 0:
        return False
    iou = interArea / float(boxAArea)
    return iou > threshold

def detect_slot_occupancy(camera_url):
    cap = cv2.VideoCapture(camera_url)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise Exception("Không lấy được frame từ camera.")

    model = get_yolo_model()
    results = model(frame)
    detections = results.pandas().xyxy[0]

    car_boxes = []
    for _, row in detections.iterrows():
        if row['name'] in ['car', 'motorbike']:
            car_boxes.append((int(row['xmin']), int(row['ymin']), int(row['xmax']), int(row['ymax'])))

    ip = camera_url.split("//")[-1].split(":")[0]
    cam = Camera.objects.filter(ip_address=ip).first()
    if not cam:
        raise Exception("Không tìm thấy camera trong database")

    slots = CarSlot.objects.filter(camera=cam)

    result = []
    for slot in slots:
        slot_box = (slot.x1, slot.y1, slot.x2, slot.y2)
        occupied = any(is_overlap(slot_box, car_box) for car_box in car_boxes)

        slot.is_available = not occupied
        slot.save(update_fields=["is_available"])

        result.append({
            "slot_id": slot.id,
            "slot_code": slot.code,
            "is_available": not occupied
        })

    return result
