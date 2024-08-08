import os
import platform

from offspot_demo import logger
from offspot_demo.constants import DEBUG


def fail(message: str = "An error occured", code: int = 1) -> int:
    """shortcut to log an error message and return an error code"""
    logger.error(message)
    return code


def get_environ() -> dict[str, str]:
    """current environment variable with langs set to C to control cli output"""
    environ = os.environ.copy()
    environ.update({"LANG": "C", "LC_ALL": "C"})
    return environ


def is_root() -> bool:
    """whether running as root"""
    return os.getuid() == 0 or (DEBUG and platform.system() == "Darwin")
