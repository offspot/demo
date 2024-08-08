#!/usr/bin/env python3

import argparse
import logging
import sys
from time import sleep

from offspot_demo import logger
from offspot_demo.constants import (
    JINJA_ENV,
    SRC_PATH,
    STARTUP_DURATION,
    Mode,
)
from offspot_demo.utils import fail
from offspot_demo.utils.deployment import DEPLOYMENTS, Deployment
from offspot_demo.utils.docker import is_demo_healthy, start_demo, stop_demo


def write_maint_compose(deployment: Deployment):
    """Render the maintenance docker-compose to customize local stuff"""
    logger.info("Rendering maintenance docker-compose")
    deployment.maint_compose_path.parent.mkdir(parents=True, exist_ok=True)
    deployment.maint_compose_path.write_text(
        JINJA_ENV.from_string(
            """
services:
  maint:
    build: {{ src_path }}/maint-compose/
    environment:
      - FQDN={{ fqdn }}
    ports:
      - {{ http_port }}:80

"""
        ).render(
            src_path=SRC_PATH, fqdn=deployment.fqdn, http_port=deployment.http_port
        )
    )


def toggle_demo(deployment: Deployment, mode: Mode) -> int:
    logger.info(f"toggle-demo {deployment!s} {mode=}")

    if not deployment.maint_compose_installed:
        write_maint_compose(deployment=deployment)

    logger.info("Stopping compose")
    stop_demo(deployment)

    logger.info("Updating symlink")

    deployment.compose_path.unlink(missing_ok=True)
    if mode == Mode.IMAGE:
        deployment.compose_path.symlink_to(deployment.image_compose_path)
    else:
        deployment.compose_path.symlink_to(deployment.maint_compose_path)

    logger.info("Starting compose")
    start_demo(deployment)

    logger.info(
        f"Sleeping {STARTUP_DURATION} seconds to check system status still ok after a"
        " while"
    )
    sleep(STARTUP_DURATION)

    logger.info("Checking compose is still running")
    if not is_demo_healthy(deployment):
        return fail("Compose is not properly running")

    return 0


def get_mode(deployment: Deployment) -> Mode:
    """modes currently active"""
    # WARN: symlink doesn't tell whether compose is running or not
    # and if it was launched with a different one
    return (
        Mode.IMAGE
        if deployment.compose_path.resolve() == deployment.image_compose_path
        else Mode.MAINT
    )


def entrypoint():
    parser = argparse.ArgumentParser(
        prog="demo-toggle", description="Toggle between maint and image modes"
    )

    parser.add_argument(dest="ident", help="Deployment/image identifier")

    parser.add_argument(
        dest="mode",
        help="New target mode, either maint or image",
        default="maint",
        choices=[m.lower() for m in Mode.__members__.keys()],
    )

    args = parser.parse_args()
    logger.setLevel(logging.DEBUG)

    try:
        mode = Mode[args.mode.upper()]
        sys.exit(toggle_demo(deployment=DEPLOYMENTS[args.ident], mode=mode))
    except Exception as exc:
        logger.exception(exc)
        logger.critical(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(entrypoint())
