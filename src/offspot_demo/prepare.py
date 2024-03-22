from pathlib import Path


def entrypoint():
    print("Hello from prepare")


def prepare_image(target_dir: Path) -> int:
    print(f"prepare-image {target_dir=}")
    return 1
