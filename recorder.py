import cv2
import time

class Recorder:
    def __init__(self, filename, fps=10, frame_size=(640,480)):
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.writer = cv2.VideoWriter(filename, fourcc, fps, frame_size)
        self.start_time = time.time()

    def write(self, frame):
        self.writer.write(frame)

    def release(self):
        self.writer.release()
