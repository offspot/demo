import subprocess
import sys

from offspot_demo.constants import logger


def run_command(
    command: list[str],
    ok_return_codes: list[int] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command and check return code

    A list of return codes which have to be considered as ok can be passed, by default
    only the 0 return code is considered as ok.
    """
    if not ok_return_codes:
        ok_return_codes = [0]
    process = subprocess.run(
        [
            "/usr/bin/env",
            *command,
        ],
        text=True,
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        check=False,
    )
    if process.returncode not in ok_return_codes:
        logger.error(
            f"Running command failed with code {process.returncode}\n"
            f"Command was: {command}\n"
            f"Stdout/Stderr is:\n{process.stdout}"
        )
        sys.exit(1)
    return process
