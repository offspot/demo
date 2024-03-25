import json
import logging
import os
import pathlib
import subprocess

from offspot_demo.constants import get_logger
from offspot_demo.utils import get_environ

logger = get_logger("deploy")  # reusing deploy logger to get its level


def only_on_debug() -> bool:
    return logger.level <= logging.DEBUG


def flush_writes():
    """call sync to ensure all writes are commited to disks"""

    os.sync()
    subprocess.run(
        ["/usr/bin/env", "sync", "-f"],
        check=True,
        capture_output=only_on_debug(),
        text=True,
        env=get_environ(),
    )


def get_loopdev() -> str:
    """free loop-device path ready to ease"""
    return subprocess.run(
        ["/usr/bin/env", "losetup", "-f"],
        check=True,
        capture_output=True,
        text=True,
        env=get_environ(),
    ).stdout.strip()


def get_losetup() -> list[dict[str, str | int]]:
    """list of devices returned by losetup from, JSON output"""
    return json.loads(
        subprocess.run(
            ["/usr/bin/env", "losetup", "--json"],
            check=True,
            capture_output=True,
            text=True,
            env=get_environ(),
        ).stdout.strip()
    )["loopdevices"]


def is_loopdev_free(loop_dev: str):
    """whether a loop-device (/dev/loopX) is not already attached"""
    return loop_dev not in [device["name"] for device in get_losetup()]


def get_loopdev_used_by(image_path: pathlib.Path) -> str:
    """which loop_device an image file is currently attached to (if attached)"""
    for device in get_losetup():
        if device["back-file"] == str(image_path.resolve()):
            return str(device["name"])

    return ""


def get_loop_name(loop_dev: str) -> str:
    """name of loop from loop_dev (/dev/loopX -> loopX)"""
    return str(pathlib.Path(loop_dev).relative_to(pathlib.Path("/dev")))


def create_block_special_device(dev_path: str, major: int, minor: int):
    """create a special block device (for partitions, inside docker)"""
    logger.debug(f"Create mknod for {dev_path} with {major=} {minor=}")
    subprocess.run(
        ["/usr/bin/env", "mknod", dev_path, "b", str(major), str(minor)],
        check=True,
        capture_output=only_on_debug(),
        text=True,
        env=get_environ(),
    )


def attach_to_device(img_fpath: pathlib.Path, loop_dev: str):
    """attach a device image to a loop-device"""
    subprocess.run(
        ["/usr/bin/env", "losetup", "--partscan", loop_dev, str(img_fpath)],
        check=True,
        capture_output=only_on_debug(),
        text=True,
        env=get_environ(),
    )

    # create nodes for partitions if not present (typically when run in docker)
    if not pathlib.Path(f"{loop_dev}p1").exists():
        logger.debug(f"Missing {loop_dev}p1 on fs")
        loop_name = get_loop_name(loop_dev)
        loop_block_dir = pathlib.Path("/sys/block/") / loop_name

        if not loop_block_dir.exists():
            raise OSError(f"{loop_block_dir} does not exists")
        for part_dev_file in loop_block_dir.rglob(f"{loop_name}p*/dev"):
            part_path = pathlib.Path(loop_dev).with_name(part_dev_file.parent.name)
            major, minor = part_dev_file.read_text().strip().split(":", 1)
            create_block_special_device(
                dev_path=str(part_path), major=int(major), minor=int(minor)
            )
    else:
        logger.debug(f"Found {loop_dev}p1 on fs")


def detach_device(loop_dev: str, *, failsafe: bool = False) -> bool:
    """whether detaching this loop-device succeeded"""
    ps = subprocess.run(
        ["/usr/bin/env", "losetup", "--detach", loop_dev],
        check=not failsafe,
        capture_output=only_on_debug(),
        text=True,
        env=get_environ(),
    )

    # remove special block devices if still present (when in docker)
    loop_path = pathlib.Path(loop_dev)
    if loop_path.with_name(f"{loop_path.name}p1").exists():
        logger.debug(f"{loop_dev}p1 not removed from fs")
        for part_path in loop_path.parent.glob(f"{loop_path.name}p*"):
            logger.debug(f"Unlinking {part_path}")
            part_path.unlink(missing_ok=True)
    else:
        logger.debug(f"{loop_dev} properly removed from fs")

    return ps.returncode == 0


def mount_on(dev_path: str, mount_point: pathlib.Path, filesystem: str | None) -> bool:
    """whether mounting device onto mount point succeeded"""
    commands = ["/usr/bin/env", "mount"]
    if filesystem:
        commands += ["-t", filesystem]
    commands += [dev_path, str(mount_point)]
    return (
        subprocess.run(
            commands,
            capture_output=only_on_debug(),
            text=True,
            check=False,
            env=get_environ(),
        ).returncode
        == 0
    )


def unmount(mount_point: pathlib.Path) -> bool:
    """whether unmounting mount-point succeeded"""
    flush_writes()
    return (
        subprocess.run(
            ["/usr/bin/env", "umount", str(mount_point)],
            capture_output=only_on_debug(),
            text=True,
            check=False,
            env=get_environ(),
        ).returncode
        == 0
    )


def is_mounted(mount_point: pathlib.Path) -> bool:
    return (
        subprocess.run(
            ["/usr/bin/env", "mountpoint", "-q", str(mount_point)], check=False
        ).returncode
        == 0
    )
