import cv2
from ultralytics import YOLO
import easyocr
import re
import matplotlib.pyplot as plt


class LicensePlateRecognizer:
    def __init__(self, model_path, use_gpu=False):
        """
        Khởi tạo class với model YOLO và EasyOCR reader.
        :param model_path: Đường dẫn đến file model YOLO.
        :param use_gpu: Sử dụng GPU hay không (mặc định là False).
        """
        self.model = YOLO(model_path)
        self.reader = easyocr.Reader(['en'], gpu=use_gpu)

    def recognize_plate_from_image(self, image, conf_threshold=0.5):
        """
        Nhận dạng biển số từ hình ảnh.
        :param image: Ảnh đầu vào (numpy array).
        :param conf_threshold: Ngưỡng độ tin cậy cho YOLO (mặc định là 0.5).
        :return: Danh sách các biển số nhận dạng được.
        """
        # Dự đoán vị trí biển số bằng YOLO
        results = self.model.predict(source=image, conf=conf_threshold)
        plates = []

        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()  # Lấy tọa độ bounding box
            scores = result.boxes.conf.cpu().numpy()  # Lấy độ tin cậy

            for bbox, score in zip(boxes, scores):
                x_min, y_min, x_max, y_max = bbox.astype(int)

                # Cắt vùng ảnh chứa biển số
                plate_img = image[y_min:y_max, x_min:x_max]

                # Nhận dạng text từ vùng ảnh biển số
                ocr_result = self.reader.readtext(plate_img)
                plate_text = ''
                for (bbox, text, conf) in ocr_result:
                    # Ghép các ký tự nhận dạng được
                    plate_text += text

                # Làm sạch text (chỉ giữ lại chữ và số)
                plate_text = re.sub(r'[^A-Za-z0-9]', '', plate_text).upper()

                # Thêm biển số vào danh sách
                plates.append(plate_text)

        return plates
