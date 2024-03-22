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
    SYSTEMD_OFFSPOT_UNIT_PATH,
)
from offspot_demo.utils import run_command


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
    ok_return_codes: list[int] | None = None,
    *,
    check_running: bool = False,
    check_enabled: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Check status of the systemd unit

    By default, check at least that the unit is loaded properly (i.e. parsing is ok)
    If check_running is True, it also checks that the unit is running
    If check_enabled is True, it also checks that the unit is enabled
    """
    status = run_command(
        ["systemctl", "status", "--no-pager", f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service"],
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
    if check_enabled:
        if "; enabled; " not in status.stdout:
            print("systemd unit is not enabled:")
            print(status.stdout)
            sys.exit(4)
        else:
            print("\tsystemd unit is enabled")
    return status


def setup_systemd_service():
    """Setup systemd service for offspot-demo: install, start, enable (with checks)"""

    print("Installing systemd unit")
    shutil.copyfile(
        SRC_PATH / f"systemd-unit/{SYSTEMD_OFFSPOT_UNIT_NAME}.service",
        SYSTEMD_OFFSPOT_UNIT_PATH,
    )
    print("Checking systemd unit")
    check_systemd_service(ok_return_codes=[0, 3])

    print("Starting systemd unit")
    run_command(
        ["systemctl", "start", "--no-pager", f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service"]
    )
    check_systemd_service(check_running=True)

    print(
        f"Sleeping {STARTUP_DURATION} seconds to check systemd unit is still ok after"
        " a while"
    )
    sleep(STARTUP_DURATION)

    print("Checking again systemd unit status")
    check_systemd_service(check_running=True)

    print("Enabling systemd unit")
    run_command(
        ["systemctl", "enable", "--no-pager", f"{SYSTEMD_OFFSPOT_UNIT_NAME}.service"]
    )
    check_systemd_service(check_running=True, check_enabled=True)


def entrypoint():
    """Setup the machine for proper operation"""
    render_maint_docker_compose()
    install_symlink()
    setup_systemd_service()
