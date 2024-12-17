import os
import smtplib
from collections import deque
from datetime import datetime
import time
from email.message import EmailMessage

import cv2
import gi
import hailo
from config import config

gi.require_version("Gst", "1.0")
from gi.repository import Gst

from detection_pipeline import GStreamerDetectionApp
from hailo_rpi_common import (BaseAppCallbackClass, get_caps_from_pad,
                              get_numpy_from_buffer)
from utils import create_today_folder, is_daylight


# -----------------------------------------------------------------------------------------------
# User-defined class to be used in the callback function
# -----------------------------------------------------------------------------------------------
# Inheritance from the app_callback_class
class UserAppCallback(BaseAppCallbackClass):
    def __init__(self) -> None:
        super().__init__()
        # create clean cache folder
        self.current_cache_dir = create_today_folder(config.CACHE_DIR)
        self.detection_interval = config.DETECTION_INTERVAL
        self.cooldown = config.COOLDOWN
        self.threshold = config.THRESHOLD

        self.last_detection_times = []
        self.last_email_sent = 0
        self.last_frame_path = ""
        # Keep track of last N frames (e.g., last 3 frames) instead of multiprocessing for now
        self.frame_history = deque(maxlen=3)

    def store_frame(self, frame_path: str) -> None:
        self.frame_history.append(frame_path)

    def record_detection(self) -> None:
        now = time.time()
        self.last_detection_times.append(now)
        # Clean up old detections
        self.last_detection_times = [t for t in self.last_detection_times if t > now - self.detection_interval]

    def should_send_email(self) -> bool:
        now = time.time()
        # Check if threshold met and cooldown passed
        if len(self.last_detection_times) >= self.threshold and (now - self.last_email_sent) > self.cooldown:
            return True
        return False

    def send_email_with_attachments(self, subject, body) -> None:
        # frames is a list of raw JPEG bytes
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = "from@example.com"
        msg['To'] = "to@example.com"
        msg.set_content(body)

        # Attach the frames
        for attachment_path in list(self.frame_history):
            if os.path.exists(attachment_path):
                with open(attachment_path, 'rb') as f:
                    file_data = f.read()
                    file_name = os.path.basename(attachment_path)
                msg.add_attachment(
                    file_data,
                    maintype='image',
                    subtype='jpeg',
                    filename=file_name
                )

        # lets see how consuming is sending emails directly
        with smtplib.SMTP('smtp.example.com') as server:
            server.login("user", "password")
            server.send_message(msg)

        self.last_email_sent = time.time()

# -----------------------------------------------------------------------------------------------
# User-defined callback function
# -----------------------------------------------------------------------------------------------


# This is the callback function that will be called when data is available from the pipeline
# create a class method and ABC class for better annotation
def app_callback(
    pad: Gst.Pad, info: Gst.PadProbeInfo, user_data: UserAppCallback
) -> Gst.PadProbeReturn:
    # Get the GstBuffer from the probe info
    buffer = info.get_buffer()
    # Check if the buffer is valid
    if buffer is None:
        return Gst.PadProbeReturn.OK

    # Using the user_data to count the number of frames
    user_data.increment()
    string_to_print = ""  # f"Frame count: {user_data.get_count()}\n"

    # Get the caps from the pad
    format, width, height = get_caps_from_pad(pad)

    # Get the detections from the buffer
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    is_detected = False

    # Parse the detections
    detection_count = 0
    for detection in detections:
        label = detection.get_label()
        bbox = detection.get_bbox()
        confidence = detection.get_confidence()
        if label in config.LABELS:  # sitting pigeons detected as person :D, let's catch them
            string_to_print += f"{label} {confidence:.2f}, Bx:{round(bbox.width(), 3)}x{round(bbox.height(),3)} "
            detection_count += 1
            is_detected = True
            print(string_to_print)

    # If the user_data.use_frame is set to True, we can get the video frame from the buffer
    if (
        is_detected
        and format is not None
        and width is not None
        and height is not None
    ):
        # Get video frame
        frame = get_numpy_from_buffer(buffer, format, width, height)

        # get unique time stamp, his will somehow control amount of pics per second (only one)
        current_datetime = datetime.now()
        formatted_datetime = current_datetime.strftime("%Y-%m-%d_%H:%M:%S")

        # Let's print the detection count to the frame
        cv2.putText(
            frame,
            f"{string_to_print}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )

        # Convert the frame to BGR
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # save frame anywhere
        frame_path = f"{user_data.current_cache_dir}/{formatted_datetime}.jpg"
        cv2.imwrite(frame_path, frame)
        if user_data.last_frame_path != frame_path:
            # 30 fps can over feed queue, frame_path have timestamp set to seconds
            user_data.store_frame(frame_path)
            user_data.last_frame_path = frame_path
            # user_data.set_frame(frame) # send frame to multi queue maybe better option

        # Record a detection
        user_data.record_detection()

        # Check if we should send an email
        if user_data.should_send_email():
            user_data.send_email_with_attachments(
                subject="Alert: Pigeon Detected!",
                body="Maybe your enemy is on the balcony. See attached frames.",
            )

    return Gst.PadProbeReturn.OK


if __name__ == "__main__":
    # add force
    if config.FORCE or is_daylight():
        user_data = UserAppCallback()
        app = GStreamerDetectionApp(app_callback, user_data)
        app.run()
