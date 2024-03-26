import subprocess

from offspot_demo.utils.process import run_command


class SystemdError(Exception):

    def __init__(self, stdout: str, *args: object) -> None:
        self.stdout = stdout
        super().__init__(*args)


class SystemdNotRunningError(SystemdError):
    return_code = 3


class SystemdNotWaitingError(SystemdError):
    return_code = 4


class SystemdNotEnabledError(SystemdError):
    return_code = 5


class SystemdNotLoadedError(SystemdError):
    return_code = 2


def check_systemd_service(
    unit_fullname: str,
    *,
    check_running: bool = False,
    check_waiting: bool = False,
    check_enabled: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Check status of the systemd unit

    The minimal check consists in ensuring that the systemd unit is properly loaded (no
    parsing issue, no unknown parameter, ...)

    Parameters:
        unit_fullname: full name of the systemd unit to check (e.g. my-timer.timer)
        check_running: also check that systemd unit is running
        check_waiting: also check that systemd unit is waiting (for timers typically)
        check_enabled: also check that systemd unit is enabled

    Raises:
        SystemdNotLoadedError: if unit is not properly loaded
        SystemdNotRunningError: if unit is not running ; when using check_running
        SystemdNotEnabledError: if unit is not enabled ; when using check_enabled
        SystemdNotWaitingError: if unit is not waiting ; when using check_waiting
    """
    process = run_command(
        [
            "systemctl",
            "status",
            "--no-pager",
            unit_fullname,
        ],
        ok_return_codes=[0, 3],
    )
    if "Loaded: loaded" not in process.stdout:
        raise SystemdNotLoadedError(stdout=process.stdout)
    if check_running and "Active: active (running)" not in process.stdout:
        raise SystemdNotRunningError(stdout=process.stdout)
    if check_waiting and "Active: active (waiting)" not in process.stdout:
        raise SystemdNotWaitingError(stdout=process.stdout)
    if check_enabled and "; enabled; " not in process.stdout:
        raise SystemdNotWaitingError(stdout=process.stdout)
    return process


def start_systemd_unit(unit_fullname: str):
    """Starts a systemd unit, based on its fullname e.g. my-timer.timer"""

    run_command(["systemctl", "start", "--no-pager", unit_fullname])


def stop_systemd_unit(unit_fullname: str):
    """Stops a systemd unit, based on its fullname e.g. my-timer.timer"""

    # return code 5 is allowed since the service might not be started yet
    run_command(
        ["systemctl", "stop", "--no-pager", unit_fullname], ok_return_codes=[0, 5]
    )


def enable_systemd_unit(unit_fullname: str):
    """Enables a systemd unit, based on its fullname e.g. my-timer.timer"""

    run_command(["systemctl", "stop", "--no-pager", unit_fullname])
