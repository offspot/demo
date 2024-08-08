import subprocess
import sys

from offspot_demo import logger


def run_command(
    command: list[str],
    ok_return_codes: list[int] | None = None,
    *,
    quiet: bool = True,
    failsafe: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command and check return code

    A list of return codes which have to be considered as ok can be passed, by default
    only the 0 return code is considered as ok.
    """
    if not ok_return_codes:
        ok_return_codes = [0]

    process = subprocess.run(
        ["/usr/bin/env", *command],
        check=False,
        text=True,
        stderr=subprocess.STDOUT if quiet else None,
        stdout=subprocess.PIPE if quiet else None,
    )
    if process.returncode not in ok_return_codes:
        logger.error(
            f"Running command failed with code {process.returncode}\n"
            f"Command was: {command}\n"
            f"Stdout/Stderr is:\n{process.stdout}"
        )
        if not failsafe:
            sys.exit(1)
    return process
