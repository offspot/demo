import os


def get_environ() -> dict[str, str]:
    """current environment variable with langs set to C to control cli output"""
    environ = os.environ.copy()
    environ.update({"LANG": "C", "LC_ALL": "C"})
    return environ
