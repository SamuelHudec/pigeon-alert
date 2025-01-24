import argparse
import logging
import multiprocessing
import os
import signal
import subprocess
import sys
import threading
from abc import ABC, abstractmethod
from typing import Any, Optional

import cv2
import gi
import numpy as np
import setproctitle

from config import config
from pipelines import get_source_type

gi.require_version("Gst", "1.0")
from gi.repository import GLib, GObject, Gst  # noqa: E402

try:
    from picamera2 import Picamera2
except ImportError:
    pass # Available only on Pi OS

logger = logging.getLogger("hailo rpi-common")

# -----------------------------------------------------------------------------------------------
# User-defined class to be used in the callback function
# -----------------------------------------------------------------------------------------------
# A sample class to be used in the callback function
# This example allows to:
# 1. Count the number of frames
# 2. Setup a multiprocessing queue to pass the frame to the main thread
# Additional variables and functions can be added to this class as needed


class BaseAppCallbackClass(ABC):
    def __init__(self) -> None:
        self.frame_count = 0
        self.current_cache_dir = ""
        self.use_frame = False
        self.frame_queue = multiprocessing.Queue(maxsize=config.mail.MAX_FRAME)
        self.running = True

    def increment(self) -> None:
        self.frame_count += 1

    def get_count(self) -> int:
        return self.frame_count

    def set_frame(self, frame: np.ndarray) -> None:
        if not self.frame_queue.full():
            self.frame_queue.put(frame)

    def get_frame(self) -> Optional[np.ndarray]:
        if not self.frame_queue.empty():
            return self.frame_queue.get()
        else:
            return None


def dummy_callback(
    pad: Gst.Pad, info: Gst.PadProbeInfo, user_data: object
) -> Gst.PadProbeReturn:
    """
    A minimal dummy callback function that returns immediately.

    Args:
        pad: The GStreamer pad.
        info: The probe info.
        user_data: User-defined data passed to the callback.

    Returns:
        Gst.PadProbeReturn.OK
    """
    return Gst.PadProbeReturn.OK


# -----------------------------------------------------------------------------------------------
# Common functions
# -----------------------------------------------------------------------------------------------
def detect_hailo_arch() -> Optional[str]:
    try:
        # Run the hailortcli command to get device information
        result = subprocess.run(
            ["hailortcli", "fw-control", "identify"], capture_output=True, text=True
        )

        # Check if the command was successful
        if result.returncode != 0:
            print(f"Error running hailortcli: {result.stderr}")
            return None

        # Search for the "Device Architecture" line in the output
        for line in result.stdout.split("\n"):
            if "Device Architecture" in line:
                if "HAILO8L" in line:
                    return "hailo8l"
                elif "HAILO8" in line:
                    return "hailo8"

        print("Could not determine Hailo architecture from device information.")
        return None
    except Exception as e:
        print(f"An error occurred while detecting Hailo architecture: {e}")
        return None


def get_caps_from_pad(
    pad: Gst.Pad,
) -> tuple[Optional[str], Optional[int], Optional[int]]:
    caps = pad.get_current_caps()
    if caps:
        # We can now extract information from the caps
        structure = caps.get_structure(0)
        if structure:
            # Extracting some common properties
            format = structure.get_value("format")
            width = structure.get_value("width")
            height = structure.get_value("height")
            return format, width, height
    else:
        return None, None, None


# This function is used to display the user data frame
def display_user_data_frame(user_data: BaseAppCallbackClass) -> None:
    while user_data.running:
        frame = user_data.get_frame()
        if frame is not None:
            cv2.imshow("User Frame", frame)
        cv2.waitKey(1)
    cv2.destroyAllWindows()


def get_default_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hailo App Help")
    current_path = os.path.dirname(os.path.abspath(__file__))
    default_video_source = os.path.join(current_path, "../resources/detection0.mp4")
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default=default_video_source,
        help="Input source. Can be a file, USB or RPi camera (CSI camera module). \
        For RPi camera use '-i rpi' (Still in Beta). \
        Defaults to example video resources/detection0.mp4",
    )
    parser.add_argument(
        "--use-frame",
        "-u",
        action="store_true",
        help="Use frame from the callback function",
    )
    parser.add_argument(
        "--show-fps", "-f", action="store_true", help="Print FPS on sink"
    )
    parser.add_argument(  # not used
        "--arch",
        default=None,
        choices=["hailo8", "hailo8l"],
        help="Specify the Hailo architecture (hailo8 or hailo8l). Default is None , app will run check.",
    )
    parser.add_argument(
        "--hef-path",
        default=None,
        help="Path to HEF file",
    )
    parser.add_argument(
        "--disable-sync",
        action="store_true",
        help="Disables display sink sync, will run as fast as possible. Relevant when using file source.",
    )
    parser.add_argument(
        "--dump-dot",
        action="store_true",
        help="Dump the pipeline graph to a dot file pipeline.dot",
    )
    parser.add_argument(
        "--set-time", "-t", type=int, default=None, help="Timer in seconds."
    )
    parser.add_argument(
        "--display-off",
        action="store_true",
        help="Turn off displaying.",
    )
    return parser


# -----------------------------------------------------------------------------------------------
# GStreamerApp class
# -----------------------------------------------------------------------------------------------
class GStreamerApp(ABC):
    # this is base class should be added as base properly before publishing
    def __init__(
        self, args: argparse.Namespace, user_data: BaseAppCallbackClass
    ) -> None:  # change user_data to something more intuitive
        # Set the process title
        setproctitle.setproctitle("Hailo Python App")

        # Create an empty options menu
        self.options_menu = args

        # Set up signal handler for SIGINT (Ctrl-C)
        signal.signal(signal.SIGINT, self.shutdown)

        # Initialize variables
        tappas_post_process_dir = os.environ.get("TAPPAS_POST_PROC_DIR", "")
        if tappas_post_process_dir == "":
            print(
                "TAPPAS_POST_PROC_DIR environment variable is not set. Please set it to by sourcing setup_env.sh"
            )
            exit(1)
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.postprocess_dir = tappas_post_process_dir
        self.video_source = self.options_menu.input
        self.source_type = get_source_type(self.video_source)
        self.user_data = user_data
        self.video_sink = "autovideosink" # "xvimagesink"
        self.pipeline = None
        self.loop = None
        self.threads = [] # for what is this?
        self.error_occurred = False
        self.pipeline_latency = 300  # milliseconds

        # Set Hailo parameters; these parameters should be set based on the model used
        self.batch_size = 1
        self.video_width = 1280
        self.video_height = 720
        self.video_format = "RGB"
        self.hef_path = None
        self.app_callback = None

        # Set user data parameters
        user_data.use_frame = self.options_menu.use_frame

        self.sync = (
            "false"
            if (self.options_menu.disable_sync or self.source_type != "file")
            else "true"
        )
        self.show_fps = "true" if self.options_menu.show_fps else "false"

        if self.options_menu.dump_dot:
            os.environ["GST_DEBUG_DUMP_DOT_DIR"] = self.current_path

    def on_fps_measurement(
        self, sink: Gst.Element, fps: float, droprate: float, avgfps: float
    ) -> bool:
        # sink doesnt used but necessary as placeholder
        print(f"FPS: {fps:.2f}, Droprate: {droprate:.2f}, Avg FPS: {avgfps:.2f}")
        return True

    def create_pipeline(self) -> None:
        # Initialize GStreamer
        Gst.init(None)

        pipeline_string = self.get_pipeline_string()
        try:
            self.pipeline = Gst.parse_launch(pipeline_string)
        except Exception as e:
            print(f"Error creating pipeline: {e}", file=sys.stderr)
            sys.exit(1)

        # Connect to hailo_display fps-measurements
        if self.options_menu.show_fps:
            print("Showing FPS")
            self.pipeline.get_by_name("hailo_display").connect(
                "fps-measurements", self.on_fps_measurement
            )

        # Create a GLib Main Loop
        self.loop = GLib.MainLoop()

    def bus_call(
        self, bus: Gst.Bus, message: Gst.MessageType, loop: GLib.MainLoop
    ) -> bool:
        # bus and loop doesnt used but necessary as placeholder
        t = message.type
        if t == Gst.MessageType.EOS:
            print("End-of-stream")
            self.on_eos()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}, {debug}", file=sys.stderr)
            self.error_occurred = True
            self.shutdown()
        # QOS
        elif t == Gst.MessageType.QOS:
            # Handle QoS message here
            qos_element = message.src.get_name()
            print(f"QoS message received from {qos_element}")
        return True

    def on_eos(self) -> None:
        if self.source_type == "file":
            # Seek to the start (position 0) in nanoseconds
            success = self.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
            if success:
                print("Video rewound successfully. Restarting playback...")
            else:
                print("Error rewinding the video.", file=sys.stderr)
        else:
            self.shutdown()

    def shutdown(
        self, signum: Optional[int] = None, frame: Optional[object] = None
    ) -> None:
        print("Shutting down... Hit Ctrl-C again to force quit.")
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        self.stop_loop()

    def stop_loop(self) -> None:
        """
        just copy paseted from shutdown method for purpose of outomatic quit
        :return:
        """
        self.pipeline.set_state(Gst.State.PAUSED)
        GLib.usleep(100000)  # 0.1 second delay

        self.pipeline.set_state(Gst.State.READY)
        GLib.usleep(100000)  # 0.1 second delay

        self.pipeline.set_state(Gst.State.NULL)
        GLib.idle_add(self.loop.quit)

    @abstractmethod
    def get_pipeline_string(self) -> str:
        pass

    def dump_dot_file(self) -> bool:
        print("Dumping dot file...")
        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, "pipeline")
        return False

    def run(self) -> None:
        # Add a watch for messages on the pipeline's bus
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.bus_call, self.loop)

        # Connect pad probe to the identity element
        identity = self.pipeline.get_by_name("identity_callback")
        if identity is None:
            print(
                "Warning: identity_callback element not found, add <identity name=identity_callback> in your pipeline where you want the callback to be called."
            )
        else:
            identity_pad = identity.get_static_pad("src")
            identity_pad.add_probe(
                Gst.PadProbeType.BUFFER, self.app_callback, self.user_data
            )

        hailo_display = self.pipeline.get_by_name("hailo_display")
        if hailo_display is None:  # if none, then raise error display pipe is needed
            print(
                "Warning: hailo_display element not found, add <fpsdisplaysink name=hailo_display> to your pipeline to support fps display."
            )

        # Disable QoS to prevent frame drops
        disable_qos(self.pipeline)

        # Start a subprocess to run the display_user_data_frame function
        display_process = None
        if self.options_menu.use_frame:
            display_process = multiprocessing.Process(
                target=display_user_data_frame, args=(self.user_data,)
            )
            display_process.start()

        if self.source_type == "rpi":
            picam_thread = threading.Thread(target=picamera_thread, args=(self.pipeline, self.video_width, self.video_height, self.video_format))
            self.threads.append(picam_thread)
            picam_thread.start()

        # Set the pipeline to PAUSED to ensure elements are initialized
        self.pipeline.set_state(Gst.State.PAUSED)

        # Set pipeline latency
        new_latency = self.pipeline_latency * Gst.MSECOND  # Convert milliseconds to nanoseconds
        self.pipeline.set_latency(new_latency)

        # Set pipeline to PLAYING state
        self.pipeline.set_state(Gst.State.PLAYING)

        # Dump dot file
        if self.options_menu.dump_dot:
            GLib.timeout_add_seconds(3, self.dump_dot_file)

        # time out
        if self.options_menu.set_time:
            GLib.timeout_add_seconds(self.options_menu.set_time, self.stop_loop)

        # Run the GLib event loop
        self.loop.run()

        # Clean up
        try:
            self.user_data.running = False
            self.pipeline.set_state(Gst.State.NULL)
            if self.options_menu.use_frame:
                display_process.terminate()
                display_process.join()
            for t in self.threads:
                t.join()
        except Exception as e:
            print(f"Error during cleanup: {e}", file=sys.stderr)
        finally:
            if self.error_occurred:
                print("Exiting with error...", file=sys.stderr)
                sys.exit(1)
            else:
                print("Exiting...")
                sys.exit(0)



def picamera_thread(pipeline: Gst.Pipeline, video_width: int, video_height: int, video_format: str, picamera_config: Any = None) -> None:
    appsrc = pipeline.get_by_name("app_source")
    appsrc.set_property("is-live", True)
    appsrc.set_property("format", Gst.Format.TIME)
    print("appsrc properties: ", appsrc)
    # Initialize Picamera2
    with Picamera2() as picam2:
        if picamera_config is None:
            # Default configuration
            main = {'size': (1280, 720), 'format': 'RGB888'}
            lores = {'size': (video_width, video_height), 'format': 'RGB888'}
            controls = {'FrameRate': 30}
            config = picam2.create_preview_configuration(main=main, lores=lores, controls=controls)
        else:
            config = picamera_config
        # Configure the camera with the created configuration
        picam2.configure(config)
        # Update GStreamer caps based on 'lores' stream
        lores_stream = config['lores']
        format_str = 'RGB' if lores_stream['format'] == 'RGB888' else video_format
        width, height = lores_stream['size']
        print(f"Picamera2 configuration: width={width}, height={height}, format={format_str}")
        appsrc.set_property(
            "caps",
            Gst.Caps.from_string(
                f"video/x-raw, format={format_str}, width={width}, height={height}, "
                f"framerate=30/1, pixel-aspect-ratio=1/1"
            )
        )
        picam2.start()
        frame_count = 0
        print("picamera_process started")
        while True:
            frame_data = picam2.capture_array('lores')
            # frame_data = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
            if frame_data is None:
                print("Failed to capture frame.")
                break
            # Convert framontigue data if necessary
            frame = cv2.cvtColor(frame_data, cv2.COLOR_BGR2RGB)
            frame = np.asarray(frame)
            # Create Gst.Buffer by wrapping the frame data
            buffer = Gst.Buffer.new_wrapped(frame.tobytes())
            # Set buffer PTS and duration
            buffer_duration = Gst.util_uint64_scale_int(1, Gst.SECOND, 30)
            buffer.pts = frame_count * buffer_duration
            buffer.duration = buffer_duration
            # Push the buffer to appsrc
            ret = appsrc.emit('push-buffer', buffer)
            if ret != Gst.FlowReturn.OK:
                print("Failed to push buffer:", ret)
                break
            frame_count += 1


# ---------------------------------------------------------
# Functions used to get numpy arrays from GStreamer buffers
# ---------------------------------------------------------


def handle_rgb(map_info: Any, width: int, height: int) -> np.ndarray:
    """
    The copy() method is used to create a copy of the numpy array. This is necessary because the original numpy array
    is created from buffer data, and it does not own the data it represents.
    Instead, it's just a view of the buffer's data.
    """
    return np.ndarray(
        shape=(height, width, 3), dtype=np.uint8, buffer=map_info.data
    ).copy()


def handle_nv12(
    map_info: Any, width: int, height: int
) -> tuple[np.ndarray, np.ndarray]:
    y_plane_size = width * height
    # uv_plane_size = width * height // 2
    y_plane = np.ndarray(
        shape=(height, width), dtype=np.uint8, buffer=map_info.data[:y_plane_size]
    ).copy()
    uv_plane = np.ndarray(
        shape=(height // 2, width // 2, 2),
        dtype=np.uint8,
        buffer=map_info.data[y_plane_size:],
    ).copy()
    return y_plane, uv_plane


def handle_yuyv(map_info: Any, width: int, height: int) -> np.ndarray:
    return np.ndarray(
        shape=(height, width, 2), dtype=np.uint8, buffer=map_info.data
    ).copy()


FORMAT_HANDLERS = {
    "RGB": handle_rgb,
    "NV12": handle_nv12,
    "YUYV": handle_yuyv,
}


def get_numpy_from_buffer(
    buffer: Gst.Buffer, format: str, width: int, height: int
) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    """
    Converts a GstBuffer to a numpy array based on provided format, width, and height.

    Args:
        buffer (GstBuffer): The GStreamer Buffer to convert.
        format (str): The video format ('RGB', 'NV12', 'YUYV', etc.).
        width (int): The width of the video frame.
        height (int): The height of the video frame.

    Returns:
        np.ndarray: A numpy array representing the buffer's data, or a tuple of arrays for certain formats.
    """
    # Map the buffer to access data
    success, map_info = buffer.map(Gst.MapFlags.READ)
    if not success:
        raise ValueError("Buffer mapping failed")

    try:
        # Handle different formats based on the provided format parameter
        handler = FORMAT_HANDLERS.get(format)
        if handler is None:
            raise ValueError(f"Unsupported format: {format}")
        return handler(map_info, width, height)
    finally:
        buffer.unmap(map_info)


# ---------------------------------------------------------
# Useful functions for working with GStreamer
# ---------------------------------------------------------


def disable_qos(pipeline: Gst.Pipeline) -> None:
    """
    Iterate through all elements in the given GStreamer pipeline and set the qos property to False
    where applicable.
    When the 'qos' property is set to True, the element will measure the time it takes to process each buffer and will drop frames if latency is too high.
    We are running on long pipelines, so we want to disable this feature to avoid dropping frames.
    :param pipeline: A GStreamer pipeline object
    """
    # Ensure the pipeline is a Gst.Pipeline instance
    if not isinstance(pipeline, Gst.Pipeline):
        print("The provided object is not a GStreamer Pipeline")
        return

    # Iterate through all elements in the pipeline
    it = pipeline.iterate_elements()
    while True:
        result, element = it.next()
        if result != Gst.IteratorResult.OK:
            break

        # Check if the element has the 'qos' property
        if "qos" in GObject.list_properties(element):
            # Set the 'qos' property to False
            element.set_property("qos", False)
            print(f"Set qos to False for {element.get_name()}")
