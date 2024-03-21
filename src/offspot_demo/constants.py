from pathlib import Path

OFFSPOT_IMAGE_ID = "offspot-demo"
OFFSPOT_IMAGE_URL = "https://api.imager.kiwix.org/auto-images/{OFFSPOT_IMAGE_ID}/json"

TARGET_DIR = Path("/data")
IMAGE_PATH = Path("/demo/image.img")
PREPARED_FLAG_PATH = TARGET_DIR / "prepared.ok"

FQDN = "demo.hostpot.kiwix.org"
