import cv2
import requests
import numpy as np
from app import detect_person

class ESP32Camera:
    def __init__(self, esp_base):
        """
        esp_base: Base URL of the ESP32-CAM, e.g. "http://192.168.1.10"
        """
        self.esp_base = esp_base.rstrip('/')  # ensure no trailing slash

    def get_frame(self):
        """
        Fetch a single frame from ESP32-CAM and return it as a cv2 image (BGR).
        """
        try:
            resp = requests.get(f"{self.esp_base}/capture", timeout=1)
            if resp.status_code != 200:
                return None
            img_array = np.frombuffer(resp.content, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            return frame
        except Exception as e:
            print(f"Error fetching frame: {e}")
            return None

    def get_stream(self):
        """
        Generator function that yields MJPEG frames with optional person detection applied.
        """
        while True:
            frame = self.get_frame()
            if frame is None:
                continue

            # Apply person detection if available
            frame = detect_person(frame)

            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
