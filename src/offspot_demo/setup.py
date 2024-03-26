import argparse
import logging
import shutil
import subprocess
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


def check_systemd_service(
    unit_fullname: str,
    ok_return_codes: list[int] | None = None,
    *,
    check_running: bool = False,
    check_waiting: bool = False,
    check_enabled: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Check status of the systemd unit

    By default, check at least that the unit is loaded properly (i.e. parsing is ok)
    If check_running is True, it also checks that the unit is running
    If check_enabled is True, it also checks that the unit is enabled
    """
    status = run_command(
        [
            "systemctl",
            "status",
            "--no-pager",
            unit_fullname,
        ],
        ok_return_codes=ok_return_codes,
    )
    if "Loaded: loaded" not in status.stdout:
        logger.error(f"systemd unit not loaded properly:\n{status.stdout}")
        logger.error(status.stdout)
        sys.exit(2)
    if check_running:
        if "Active: active (running)" not in status.stdout:
            logger.error(f"systemd unit is not running:\n{status.stdout}")
            sys.exit(3)
        else:
            logger.info("\tsystemd unit is running")
    if check_waiting:
        if "Active: active (waiting)" not in status.stdout:
            logger.error(f"systemd unit is not waiting:\n{status.stdout}")
            sys.exit(4)
        else:
            logger.info("\tsystemd unit is waiting")
    if check_enabled:
        if "; enabled; " not in status.stdout:
            logger.error(f"systemd unit is not enabled:\n{status.stdout}")
            sys.exit(5)
        else:
            logger.info("\tsystemd unit is enabled")
    return status


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

    logger.info("Checking systemd units")
    check_systemd_service(
        unit_fullname=f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service", ok_return_codes=[0, 3]
    )
    check_systemd_service(
        unit_fullname=f"{SYSTEMD_WATCHER_UNIT_NAME}.timer", ok_return_codes=[0, 3]
    )
    check_systemd_service(
        unit_fullname=f"{SYSTEMD_WATCHER_UNIT_NAME}.service", ok_return_codes=[0, 3]
    )

    logger.info("Stopping systemd units (if already started)")
    run_command(
        ["systemctl", "stop", "--no-pager", f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service"],
        ok_return_codes=[0, 5],
    )

    logger.info("Reload systemctl daemon")
    run_command(["systemctl", "daemon-reload"])

    logger.info("Enabling systemd units")
    run_command(
        ["systemctl", "enable", "--no-pager", f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service"]
    )
    run_command(
        ["systemctl", "enable", "--no-pager", f"{SYSTEMD_WATCHER_UNIT_NAME}.timer"]
    )

    logger.info("Checking systemd units")
    check_systemd_service(
        unit_fullname=f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service",
        check_enabled=True,
        ok_return_codes=[0, 3],
    )
    check_systemd_service(
        unit_fullname=f"{SYSTEMD_WATCHER_UNIT_NAME}.timer",
        check_enabled=True,
        ok_return_codes=[0, 3],
    )

    logger.info("Starting systemd units")
    run_command(
        ["systemctl", "start", "--no-pager", f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service"]
    )
    run_command(
        ["systemctl", "start", "--no-pager", f"{SYSTEMD_WATCHER_UNIT_NAME}.timer"]
    )

    logger.info(
        f"Sleeping {STARTUP_DURATION} seconds to check system status still ok after a"
        " while"
    )
    sleep(STARTUP_DURATION)

    logger.info("Checking systemd unit is still running")
    check_systemd_service(
        unit_fullname=f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service",
        check_enabled=True,
        check_running=True,
    )
    check_systemd_service(
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
