import subprocess

from offspot_demo.utils.process import run_command


class SystemdError(Exception):

    def __init__(self, stdout: str, *args: object) -> None:
        self.stdout = stdout
        super().__init__(*args)


class SystemdNotRunningError(SystemdError):
    pass


class SystemdNotWaitingError(SystemdError):
    pass


class SystemdNotEnabledError(SystemdError):
    pass


class SystemdNotLoadedError(SystemdError):
    pass


def check_systemd_service(
    unit_fullname: str,
    *,
    check_running: bool = False,
    check_waiting: bool = False,
    check_enabled: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Check status of the systemd unit

    By default, check at least that the unit is loaded properly (i.e. parsing is ok),
    otherwise a SystemdNotLoadedError is raised.
    If check_running is True, it also checks that the unit is running, otherwise a
    SystemdNotRunningError is raiase
    If check_enabled is True, it also checks that the unit is enabled, otherwise a
    SystemdNotEnabledError is raiase
    If check_waiting is True, it also checks that the unit is waiting, otherwise a
    SystemdNotWaitingError is raiase
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
