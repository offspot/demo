import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

OFFSPOT_IMAGE_ID = "offspot-demo"
OFFSPOT_IMAGE_URL = f"https://api.imager.kiwix.org/auto-images/{OFFSPOT_IMAGE_ID}/json"

TARGET_DIR = Path("/host/data")
IMAGE_PATH = Path("/host/demo/image.img")
PREPARED_FLAG_PATH = TARGET_DIR / "prepared.ok"

FQDN = os.getenv("OFFSPOT_DEMO_FQDN", "demo.hostpot.kiwix.org")

DOCKER_COMPOSE_PROD_PATH = TARGET_DIR / "compose.yaml"
DOCKER_COMPOSE_SYMLINK_PATH = Path("/etc/docker/compose.yaml")

SYSTEMD_UNIT_NAME = "offspot-demo"
SYSTEMD_UNIT_PATH = Path(f"/etc/systemd/system/{SYSTEMD_UNIT_NAME}.service")

SRC_PATH = Path(__file__).parent

JINJA_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent), autoescape=select_autoescape()
)

# Expected duration for the service startup ; scripts use this to pause and check that
# service is still up after this duration
STARTUP_DURATION = 10
