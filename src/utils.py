import logging
import os
import shutil
from datetime import date, datetime

import cv2
import pytz
from astral import LocationInfo
from astral.sun import sun

logger = logging.getLogger("Utils")

def create_and_clean_folder(folder_path: str, remove: bool = True) -> None:
    if os.path.exists(folder_path):
        if remove:
            shutil.rmtree(folder_path)
            os.makedirs(folder_path, exist_ok=True)
            print(f"Cleaned and recreated folder: {folder_path}")
        else:
            print(f"Folder exist: {folder_path}")
    else:
        os.makedirs(folder_path, exist_ok=True)
        print(f"Folder '{folder_path}' created.")


def create_today_folder(folder_path: str, remove: bool = False) -> str:
    current_datetime = datetime.now()
    formatted_date = current_datetime.strftime("%Y-%m-%d")
    current_cache_dir = os.path.join(folder_path, formatted_date)
    create_and_clean_folder(current_cache_dir, remove=remove)
    logger.debug(f"Folder directory: {current_cache_dir}")
    return current_cache_dir


def is_daylight() -> bool:
    city = LocationInfo("Prague", "Czech Republic", "Europe/Prague", 50.0755, 14.4378)
    tz = pytz.timezone(city.timezone)
    s = sun(city.observer, date=date.today(), tzinfo=tz)
    now = datetime.now(tz=tz)
    logger.debug(f"Location: {city}, timezone: {tz}, date: {now}")
    return s["sunrise"] <= now <= s["sunset"]


def encode_frame_to_jpeg(frame):
    ret, buffer = cv2.imencode(".jpg", frame)
    if not ret:
        return None
    return buffer.tobytes()
