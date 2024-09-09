import enum
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# general, machine-specific
OFFSPOT_CONFIGURATION = Path(
    os.getenv("OFFSPOT_CONFIGURATION") or "/etc/demo/environment"
)
OFFSPOT_DEMO_MAIN_FQDN = os.getenv("OFFSPOT_DEMO_FQDN", "")
OFFSPOT_DEMOS_LIST = [
    entry
    for entry in (os.getenv("OFFSPOT_DEMOS_LIST") or "").split(",")
    if entry.strip()
]
OFFSPOT_DEMO_IMAGES_ROOT_DIR = Path(
    os.getenv("OFFSPOT_DEMO_IMAGES_ROOT_DIR") or "/data/demo/images"
)
OFFSPOT_DEMO_TARGET_ROOT_DIR = Path(
    os.getenv("OFFSPOT_DEMO_TARGET_ROOT_DIR") or "/data/demo/data"
)
OFFSPOT_DEMO_COMPOSE_ROOT_DIR = Path(
    os.getenv("OFFSPOT_DEMO_COMPOSE_ROOT_DIR") or "/data/demo/compose"
)
OFFSPOT_DEMO_TLS_EMAIL = os.getenv("OFFSPOT_DEMO_TLS_EMAIL", "dev@kiwix.org")

IMAGER_SERVICE_API_USERNAME = os.getenv("IMAGER_SERVICE_API_USERNAME") or ""
IMAGER_SERVICE_API_PASSWORD = os.getenv("IMAGER_SERVICE_API_PASSWORD") or ""

# Default timeout of HTTP requests made by the scripts
DEFAULT_HTTP_TIMEOUT_SECONDS = 30
# maintenance container and images must be labeled with this
# in order not to be purged by deploy
DOCKER_LABEL_MAINT = "maintenance"
OCI_PLATFORM = os.getenv("OFFSPOT_DEMO_OCI_PLATFORM", "linux/amd64")
# Expected duration for the service startup ; scripts use this to pause and check that
# service is still up after this duration
STARTUP_DURATION = int(os.getenv("STARTUP_DURATION") or "10")
SRC_PATH = Path(__file__).parent

SYSTEMD_UNITS_PATH = Path("/etc/systemd/system/")
SYSTEMD_OFFSPOT_UNIT_NAME = "demo-offspot"
SYSTEMD_WATCHER_UNIT_NAME = "demo-watcher"

MULTI_CONFIG_URL = (
    os.getenv("MULTI_CONFIG_URL")
    or "https://raw.githubusercontent.com/offspot/demo/main/demos.yaml"
)

JINJA_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent), autoescape=select_autoescape()
)
DEBUG: bool = bool(os.getenv("DEBUG") or "")


class Mode(enum.Enum):
    IMAGE = 1
    MAINT = 2
