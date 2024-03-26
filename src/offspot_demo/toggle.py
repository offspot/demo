import argparse
import logging
import sys
from time import sleep

from offspot_demo.constants import (
    DOCKER_COMPOSE_IMAGE_PATH,
    DOCKER_COMPOSE_MAINT_PATH,
    DOCKER_COMPOSE_SYMLINK_PATH,
    STARTUP_DURATION,
    SYSTEMD_OFFSPOT_UNIT_NAME,
    Mode,
    logger,
)
from offspot_demo.utils import fail
from offspot_demo.utils.systemd import (
    SystemdNotEnabledError,
    SystemdNotLoadedError,
    SystemdNotRunningError,
    check_systemd_service,
    stop_systemd_unit,
)


def toggle_demo(mode: Mode) -> int:
    logger.info(f"toggle-demo {mode=}")

    systemd_unit_fullname = f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service"

    logger.info("Stopping systemd unit")
    stop_systemd_unit(systemd_unit_fullname)

    logger.info("Updating symlink")

    DOCKER_COMPOSE_SYMLINK_PATH.unlink(missing_ok=True)
    if mode == Mode.IMAGE:
        DOCKER_COMPOSE_SYMLINK_PATH.symlink_to(DOCKER_COMPOSE_IMAGE_PATH)
    else:
        DOCKER_COMPOSE_SYMLINK_PATH.symlink_to(DOCKER_COMPOSE_MAINT_PATH)

    logger.info("Starting systemd unit")

    logger.info(
        f"Sleeping {STARTUP_DURATION} seconds to check system status still ok after a"
        " while"
    )
    sleep(STARTUP_DURATION)

    logger.info("Checking systemd unit is still running")
    try:
        check_systemd_service(
            unit_fullname=f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service",
            check_enabled=True,
            check_running=True,
        )
    except SystemdNotLoadedError as exc:
        return fail(f"systemd unit not loaded properly:\n{exc.stdout}")
    except SystemdNotRunningError as exc:
        return fail(f"systemd unit not running:\n{exc.stdout}")
    except SystemdNotEnabledError as exc:
        return fail(f"systemd unit not enabled:\n{exc.stdout}")

    return 0


def get_mode() -> Mode:
    """modes currently active"""
    # WARN: symlink doesn't tell whether compose is running or not
    # and if it was launched with a different one
    return (
        Mode.IMAGE
        if DOCKER_COMPOSE_SYMLINK_PATH.resolve() == DOCKER_COMPOSE_IMAGE_PATH
        else Mode.MAINT
    )


def entrypoint():
    parser = argparse.ArgumentParser(
        prog="demo-toggle", description="Toggle between maint and image modes"
    )

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
        sys.exit(toggle_demo(mode=mode))
    except Exception as exc:
        logger.exception(exc)
        logger.critical(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(entrypoint())
