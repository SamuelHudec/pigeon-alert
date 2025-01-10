import os
import pathlib

import dotenv
from pydantic_settings import BaseSettings

root = pathlib.Path(os.path.dirname(__file__)).parent

profile_env_name = "PROFILE"
profile = os.environ.get(profile_env_name, "").lower()
test_profile_enabled = os.environ.get(profile_env_name, None) == "TEST"


class Base(BaseSettings):
    class Config:
        env_file: str = f".env{'.' + profile.lower() if profile else ''}"


# read env vars from env file and override existing env vars from .env.${PROFILE} if PROFILE is set
dotenv.load_dotenv(pathlib.Path(root) / ".env")
dotenv.load_dotenv(pathlib.Path(root) / Base.Config.env_file, override=profile != "")


class Mail(BaseSettings):
    SENDER_EMAIL: str
    SENDER_PASSWORD: str
    MAX_FRAME: int = 3
    DETECTION_INTERVAL: int = 30
    COOLDOWN: int = 300
    THRESHOLD: int = 5


class Config(BaseSettings):
    mail: Mail = Mail()
    CACHE_DIR: str = ".cache/birds"
    LABELS: list[str] = ["bird", "person"]
    FORCE: bool = True


config: Config = Config()
