import argparse
import logging
import shutil
import sys
from time import sleep

from offspot_demo.constants import (
    DOCKER_COMPOSE_MAINT_PATH,
    DOCKER_COMPOSE_SYMLINK_PATH,
    JINJA_ENV,
    SRC_PATH,
    STARTUP_DURATION,
    SYSTEMD_OFFSPOT_UNIT_NAME,
    SYSTEMD_UNITS_PATH,
    SYSTEMD_WATCHER_UNIT_NAME,
    logger,
)
from offspot_demo.utils import fail, is_root
from offspot_demo.utils.process import run_command
from offspot_demo.utils.systemd import (
    SystemdNotEnabledError,
    SystemdNotLoadedError,
    SystemdNotRunningError,
    SystemdNotWaitingError,
    check_systemd_service,
    enable_systemd_unit,
    start_systemd_unit,
    stop_systemd_unit,
)


def render_maint_docker_compose():
    """Render the maintenance docker-compose to customize local stuff"""
    logger.info("Rendering maintenance docker-compose")
    with open(DOCKER_COMPOSE_MAINT_PATH, "w") as fh:
        fh.write(
            JINJA_ENV.from_string(
                """
services:
  webserver:
    build: {{ src_path }}/maint-compose/
    env_file:
      - /etc/demo/environment
    ports:
      - 80:80
      - 443:443
    volumes:
      - caddy_data:/data
      - caddy_config:/config
volumes:
  caddy_data:
  caddy_config:
"""
            ).render(src_path=SRC_PATH)
        )


def install_symlink():
    """Install docker-compose symlink

    Will be switched between maint and prod, but for now point to maint
    """
    logger.info("Installing docker-compose symlink")
    DOCKER_COMPOSE_SYMLINK_PATH.unlink(missing_ok=True)
    DOCKER_COMPOSE_SYMLINK_PATH.symlink_to(DOCKER_COMPOSE_MAINT_PATH)


def setup_check_systemd_service(
    unit_fullname: str,
    *,
    check_running: bool = False,
    check_waiting: bool = False,
    check_enabled: bool = False,
) -> None:
    """Check status of the systemd unit

    By default, check at least that the unit is loaded properly (i.e. parsing is ok)
    If check_running is True, it also checks that the unit is running
    If check_enabled is True, it also checks that the unit is enabled
    If check_waiting is True, it also checks that the unit is waiting
    """

    try:
        check_systemd_service(
            unit_fullname=unit_fullname,
            check_running=check_running,
            check_enabled=check_enabled,
            check_waiting=check_waiting,
        )
    except SystemdNotLoadedError as exc:
        logger.error(f"systemd unit not loaded properly:\n{exc.stdout}")
        sys.exit(2)
    except SystemdNotRunningError as exc:
        logger.error(f"systemd unit not running:\n{exc.stdout}")
        sys.exit(3)
    except SystemdNotWaitingError as exc:
        logger.error(f"systemd unit not waiting:\n{exc.stdout}")
        sys.exit(4)
    except SystemdNotEnabledError as exc:
        logger.error(f"systemd unit not enabled:\n{exc.stdout}")
        sys.exit(5)

    logger.info("\tsystemd unit is properly loaded")
    if check_enabled:
        logger.info("\tsystemd unit is enabled")
    if check_running:
        logger.info("\tsystemd unit is running")
    if check_waiting:
        logger.info("\tsystemd unit is waiting")


def install_systemd_file(unit_fullname: str):
    shutil.copyfile(
        SRC_PATH / f"systemd-unit/{unit_fullname}",
        SYSTEMD_UNITS_PATH / f"{unit_fullname}",
    )


def setup_systemd():
    """Setup systemd : install, start, enable (with checks)"""

    logger.info("Installing systemd files")
    install_systemd_file(unit_fullname=f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service")
    install_systemd_file(unit_fullname=f"{SYSTEMD_WATCHER_UNIT_NAME}.timer")
    install_systemd_file(unit_fullname=f"{SYSTEMD_WATCHER_UNIT_NAME}.service")

    logger.info("Checking systemd units are loaded properly")
    setup_check_systemd_service(unit_fullname=f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service")
    setup_check_systemd_service(unit_fullname=f"{SYSTEMD_WATCHER_UNIT_NAME}.timer")
    setup_check_systemd_service(unit_fullname=f"{SYSTEMD_WATCHER_UNIT_NAME}.service")

    logger.info("Stopping systemd units (if already started)")
    stop_systemd_unit(f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service")
    stop_systemd_unit(f"{SYSTEMD_WATCHER_UNIT_NAME}.timer")

    logger.info("Reload systemctl daemon")
    run_command(["systemctl", "daemon-reload"])

    logger.info("Enabling systemd units")
    enable_systemd_unit(f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service")
    enable_systemd_unit(f"{SYSTEMD_WATCHER_UNIT_NAME}.timer")

    logger.info("Checking systemd units")
    setup_check_systemd_service(
        unit_fullname=f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service",
        check_enabled=True,
    )
    setup_check_systemd_service(
        unit_fullname=f"{SYSTEMD_WATCHER_UNIT_NAME}.timer",
        check_enabled=True,
    )

    logger.info("Starting systemd units")
    start_systemd_unit(f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service")
    start_systemd_unit(f"{SYSTEMD_WATCHER_UNIT_NAME}.timer")

    logger.info(
        f"Sleeping {STARTUP_DURATION} seconds to check system status still ok after a"
        " while"
    )
    sleep(STARTUP_DURATION)

    logger.info("Checking systemd unit is still running")
    setup_check_systemd_service(
        unit_fullname=f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service",
        check_enabled=True,
        check_running=True,
    )
    setup_check_systemd_service(
        unit_fullname=f"{SYSTEMD_WATCHER_UNIT_NAME}.timer",
        check_enabled=True,
        check_waiting=True,
    )


def setup():
    """Setup the machine for proper operation"""
    if not is_root():
        return fail("must be root", 1)
    render_maint_docker_compose()
    install_symlink()
    setup_systemd()


def entrypoint():
    parser = argparse.ArgumentParser(
        prog="demo-setup",
        description="Setup the required stuff on the machine to run the offspot demo",
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
        sys.exit(setup())
    except Exception as exc:
        logger.exception(exc)
        logger.critical(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(entrypoint())
