# ai/yolo.py
import torch

_model = None

def get_yolo_model():
    global _model
    if _model is None:
        _model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)
        _model.eval()
    return _model
