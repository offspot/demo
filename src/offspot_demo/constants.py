import enum
import logging
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from offspot_demo.__about__ import NAME

OFFSPOT_IMAGE_ID = "offspot-demo"
OFFSPOT_IMAGE_URL = os.getenv(
    "OFFSPOT_DEMO_IMAGE_URL",
    f"https://api.imager.kiwix.org/auto-images/{OFFSPOT_IMAGE_ID}/json",
)
TARGET_DIR = Path(os.getenv("OFFSPOT_DEMO_TARGET_DIR", "/data"))
IMAGE_PATH = Path(os.getenv("OFFSPOT_DEMO_IMAGE_PATH", "/demo/image.img"))
LAST_IMAGE_DEPLOYED_PATH = Path("/demo/last_image")

FQDN = os.getenv("OFFSPOT_DEMO_FQDN", "demo.hostpot.kiwix.org")
OFFSPOT_DEMO_TLS_EMAIL = os.getenv("OFFSPOT_DEMO_TLS_EMAIL", "dev@kiwix.org")

SRC_PATH = Path(__file__).parent

DOCKER_COMPOSE_IMAGE_PATH = TARGET_DIR / "compose.yaml"
DOCKER_COMPOSE_MAINT_PATH = SRC_PATH / "maint-compose" / "docker-compose.yml"
DOCKER_COMPOSE_SYMLINK_PATH = Path("/etc/docker/compose.yaml")

SYSTEMD_UNITS_PATH = Path("/etc/systemd/system/")
SYSTEMD_OFFSPOT_UNIT_NAME = "demo-offspot"
SYSTEMD_WATCHER_UNIT_NAME = "demo-watcher"

JINJA_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent), autoescape=select_autoescape()
)

# Expected duration for the service startup ; scripts use this to pause and check that
# service is still up after this duration
STARTUP_DURATION = 10

# maintenance container and images must be labeled with this
# in order not to be purged by deploy
DOCKER_LABEL_MAINT = "maintenance"

OCI_PLATFORM = os.getenv("OFFSPOT_DEMO_OCI_PLATFORM", "linux/amd64")


class Mode(enum.Enum):
    IMAGE = 1
    MAINT = 2


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(NAME)

# Default timeout of HTTP requests made by the scripts
DEFAULT_HTTP_TIMEOUT_SECONDS = 30
