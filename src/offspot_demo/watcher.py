import argparse
import logging
import sys

import requests

from offspot_demo.constants import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    LAST_IMAGE_DEPLOYED_PATH,
    OFFSPOT_IMAGE_URL,
    logger,
)
from offspot_demo.deploy import deploy_url


def get_new_deploy_url() -> str | None:
    """Check if deploy image has changed

    Returns the current image URL if it has changed (or has never been successfully
    deployed).

    Returns None otherwise.
    """
    if not (LAST_IMAGE_DEPLOYED_PATH).exists():
        last_image_fetched = None
    else:
        last_image_fetched = LAST_IMAGE_DEPLOYED_PATH.read_text()

    response = requests.get(OFFSPOT_IMAGE_URL, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    response_json = response.json()
    if "http_url" not in response_json or not response_json["http_url"]:
        logger.warning(f"'http_url' not found in response from {OFFSPOT_IMAGE_URL}")
        logger.debug(response.content)
        raise Exception("Unexpected response from image provider")
    if last_image_fetched != response_json["http_url"]:
        return response_json["http_url"]
    else:
        return None


def check_and_deploy():
    """Check if a new image has to be deployed, and deploy it"""
    # create folder to store LAST_IMAGE_DEPLOYED file
    LAST_IMAGE_DEPLOYED_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Checking for new image")
    new_deploy_url = get_new_deploy_url()
    if not new_deploy_url:
        logger.info("Image has not been updated")
        return
    logger.info(f"Starting demo deployment with {new_deploy_url}")
    deploy_url(url=new_deploy_url, reuse_image=False)
    logger.info("Deploy OK, persisting last image url")
    LAST_IMAGE_DEPLOYED_PATH.write_text(new_deploy_url)


def entrypoint():
    parser = argparse.ArgumentParser(
        prog="demo-watcher",
        description="Watch an offspot demo Image URL updates and trigger deployment",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        dest="debug",
        default=False,
        help="Activate debug logs",
    )

    args = parser.parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    try:
        sys.exit(check_and_deploy())
    except Exception as exc:
        logger.exception(exc)
        logger.critical(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(entrypoint())
