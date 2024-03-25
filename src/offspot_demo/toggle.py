from offspot_demo.constants import (
    DOCKER_COMPOSE_IMAGE_PATH,
    DOCKER_COMPOSE_SYMLINK_PATH,
    Mode,
)


def entrypoint():
    print("Hello from toggle")


def toggle_demo(mode: Mode) -> int:
    print(f"toggle-demo {mode=}")
    return 0


def get_mode() -> Mode:
    """modes currently active"""
    # WARN: symlink doesn't tell whether compose is running or not
    # and if it was launched with a different one
    return (
        Mode.IMAGE
        if DOCKER_COMPOSE_SYMLINK_PATH.resolve() == DOCKER_COMPOSE_IMAGE_PATH
        else Mode.MAINT
    )
