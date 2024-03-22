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
)
from offspot_demo.utils.process import run_command


def render_maint_docker_compose():
    """Render the maintenance docker-compose to customize local stuff"""
    print("Rendering maintenance docker-compose")
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
    print("Installing docker-compose symlink")
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
        print("systemd unit not loaded properly:")
        print(status.stdout)
        sys.exit(2)
    if check_running:
        if "Active: active (running)" not in status.stdout:
            print("systemd unit is not running:")
            print(status.stdout)
            sys.exit(3)
        else:
            print("\tsystemd unit is running")
    if check_waiting:
        if "Active: active (waiting)" not in status.stdout:
            print("systemd unit is not waiting:")
            print(status.stdout)
            sys.exit(4)
        else:
            print("\tsystemd unit is waiting")
    if check_enabled:
        if "; enabled; " not in status.stdout:
            print("systemd unit is not enabled:")
            print(status.stdout)
            sys.exit(5)
        else:
            print("\tsystemd unit is enabled")
    return status


def install_systemd_file(unit_fullname: str):
    shutil.copyfile(
        SRC_PATH / f"systemd-unit/{unit_fullname}",
        SYSTEMD_UNITS_PATH / f"{unit_fullname}",
    )


def setup_systemd():
    """Setup systemd : install, start, enable (with checks)"""

    print("Installing systemd files")
    install_systemd_file(unit_fullname=f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service")
    install_systemd_file(unit_fullname=f"{SYSTEMD_WATCHER_UNIT_NAME}.timer")
    install_systemd_file(unit_fullname=f"{SYSTEMD_WATCHER_UNIT_NAME}.service")

    print("Checking systemd units")
    check_systemd_service(
        unit_fullname=f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service", ok_return_codes=[0, 3]
    )
    check_systemd_service(
        unit_fullname=f"{SYSTEMD_WATCHER_UNIT_NAME}.timer", ok_return_codes=[0, 3]
    )
    check_systemd_service(
        unit_fullname=f"{SYSTEMD_WATCHER_UNIT_NAME}.service", ok_return_codes=[0, 3]
    )

    print("Stopping systemd units (if already started)")
    run_command(
        ["systemctl", "stop", "--no-pager", f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service"],
        ok_return_codes=[0, 5],
    )

    print("Reload systemctl daemon")
    run_command(["systemctl", "daemon-reload"])

    print("Enabling systemd units")
    run_command(
        ["systemctl", "enable", "--no-pager", f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service"]
    )
    run_command(
        ["systemctl", "enable", "--no-pager", f"{SYSTEMD_WATCHER_UNIT_NAME}.timer"]
    )

    print("Checking systemd units")
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

    print("Starting systemd units")
    run_command(
        ["systemctl", "start", "--no-pager", f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service"]
    )
    run_command(
        ["systemctl", "start", "--no-pager", f"{SYSTEMD_WATCHER_UNIT_NAME}.timer"]
    )

    print(
        f"Sleeping {STARTUP_DURATION} seconds to check system status still ok after a"
        " while"
    )
    sleep(STARTUP_DURATION)

    print("Checking systemd unit is still running")
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


def entrypoint():
    """Setup the machine for proper operation"""
    render_maint_docker_compose()
    install_symlink()
    setup_systemd()
