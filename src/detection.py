from datetime import datetime

import cv2
import gi
import hailo

gi.require_version("Gst", "1.0")
from gi.repository import Gst

from config import CACHE_DIR, LABELS
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
        self.current_cache_dir = create_today_folder(CACHE_DIR)


# -----------------------------------------------------------------------------------------------
# User-defined callback function
# -----------------------------------------------------------------------------------------------


# This is the callback function that will be called when data is available from the pipeline
# create a class method and ABC class for better annotation
def app_callback(
    pad: Gst.Pad, info: Gst.PadProbeInfo, user_data: BaseAppCallbackClass
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

    user_data.use_frame = False

    # Parse the detections
    detection_count = 0
    for detection in detections:
        label = detection.get_label()
        bbox = detection.get_bbox()
        confidence = detection.get_confidence()
        if label in LABELS:  # sitting pigeons detected as person :D, let's catch them
            string_to_print += f"{label} {confidence:.2f}, Bx:{round(bbox.width(), 3)}x{round(bbox.height(),3)} "
            detection_count += 1
            user_data.use_frame = True
            print(string_to_print)

    # If the user_data.use_frame is set to True, we can get the video frame from the buffer
    if (
        user_data.use_frame
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

        # save frame
        cv2.imwrite(f"{user_data.current_cache_dir}/{formatted_datetime}.jpg", frame)

        # user_data.set_frame(frame) # send frame to queue maybe better option
    return Gst.PadProbeReturn.OK


if __name__ == "__main__":
    # Create an instance of the user app callback class
    if is_daylight():
        user_data = UserAppCallback()
        app = GStreamerDetectionApp(app_callback, user_data)
        app.run()
