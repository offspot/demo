""" Deploy an image from an image URL

Limitations:
- URL must be hosted on S3 (or at least webserver must serve an md5 digest in ETag)
- Image must be Imager-service-created: have its data in a 3rd ext4 partition
"""

import argparse
import hashlib
import http
import logging
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import NamedTuple

import requests

from offspot_demo.__about__ import __version__
from offspot_demo.constants import (
    DOCKER_LABEL_MAINT,
    IMAGE_PATH,
    TARGET_DIR,
    get_logger,
)
from offspot_demo.prepare import prepare_image
from offspot_demo.toggle import toggle_demo
from offspot_demo.utils.image import (
    attach_to_device,
    detach_device,
    get_loopdev,
    get_loopdev_used_by,
    is_mounted,
    mount_on,
    unmount,
)

ONE_MIB = 2**20

logger = get_logger("deploy")


def fail(message: str = "An error occured", code: int = 1) -> int:
    logger.error(message)
    return code


def is_url_correct(url: str) -> bool:
    """whether URL is reachable"""
    with requests.get(url, timeout=5, stream=True) as resp:
        return resp.status_code == http.HTTPStatus.OK


def prune_docker():
    """Remove all containers and images not associated with maintenance mode"""
    # purge all containers except maint-labeled ones
    if subprocess.run(
        [
            "/usr/bin/docker",
            "container",
            "prune",
            "--force",
            "--filter",
            f"label!={DOCKER_LABEL_MAINT}",
        ],
        check=False,
    ).returncode:
        logger.warning("Failed to prune containers")

    # purge all containers except maint-labeled ones
    if subprocess.run(
        [
            "/usr/bin/docker",
            "image",
            "prune",
            "--force",
            "--filter",
            f"label!={DOCKER_LABEL_MAINT}",
        ],
        check=False,
    ).returncode:
        logger.warning("Failed to prune images")


class S3CompatibleETag(NamedTuple):
    """Checksum informations from ETag HTTP header on an S3 host

    S3 always sends an ETag which is either the MD5 checksum for single-part files
    or a checksum of all the parts individual checksums for multi-part files.

    Single or multiple part is based on how it was uploaded and the part size is not
    standard but is generally rounded to a MiB.

    Storing all required information in this object to be able to re-compute the final
    checksum and ETag using the downloaded file"""

    checksum: str
    nb_parts: int
    parts_size: int
    filesize: int

    @property
    def etag(self):
        return f"{self.checksum}-{self.nb_parts}"

    @property
    def found(self):
        return self.nb_parts >= 1

    @property
    def is_multipart(self) -> bool:
        return self.found and self.nb_parts > 1

    @property
    def is_singlepart(self):
        return self.nb_parts == 1


def get_checksum_from(url: str) -> S3CompatibleETag:
    """S3CompatibleETag from a URL

    Should the URL not return an ETag or Content-Length, it is assumed to not
    have a checksum."""

    with requests.get(url, timeout=5, stream=True) as resp:
        size = resp.headers.get("Content-Length")
        etag = resp.headers.get("ETag", "").replace('"', "").replace("'", "")
    if not size or not etag:
        return S3CompatibleETag("", 0, 0, 0)

    size = int(size)

    # single part etag
    if "-" not in etag:
        return S3CompatibleETag(etag, 1, size, size)

    digest, nb_parts = etag.split("-", 1)
    nb_parts = int(nb_parts)

    size_in_mib = size // ONE_MIB
    if size_in_mib % nb_parts != 0:
        parts_size = size // (nb_parts - 1)
    else:
        parts_size = size // nb_parts
    # round to MiB
    parts_size = parts_size // ONE_MIB * ONE_MIB

    return S3CompatibleETag(digest, nb_parts, parts_size, size)


def compute_s3etag_for(fpath: Path, digest: S3CompatibleETag):
    """Compute-back an S3 multipart ETag using local file and info from orig ETag"""
    concat_sum = b""
    with open(fpath, "rb") as fh:
        for _ in range(digest.nb_parts):
            sum_ = hashlib.md5(fh.read(digest.parts_size), usedforsecurity=False)
            concat_sum += sum_.digest()
    concat_hex = hashlib.md5(concat_sum, usedforsecurity=False).hexdigest()
    return f"{concat_hex}-{digest.nb_parts}"


def download_file_into(url: str, dest: Path, digest: S3CompatibleETag) -> int:
    """Download url into dest using aria2c, validating checksum"""

    dest.parent.mkdir(parents=True, exist_ok=True)

    # download into a temp folder next to target
    with TemporaryDirectory(
        suffix=".aria2", dir=dest.parent, ignore_cleanup_errors=True, delete=True
    ) as tmpdir:
        tmp_dest = Path(tmpdir).joinpath("image.img")

        args = ["aria2c", "--dir", str(tmp_dest.parent), "--out", "image.img"]
        # single part checksum, let aria2 handle checksum validation
        if digest.is_singlepart:
            args += ["--checksum", digest.checksum]
        args += [url]
        aria2 = subprocess.run(args, check=False)

        if aria2.returncode != 0:
            logger.error("Failed to download with aria2c: {aria2.returncode}")
            return aria2.returncode

        if digest.is_multipart:
            logger.info(">> verify checksum…")

            computed = compute_s3etag_for(fpath=tmp_dest, digest=digest)
            if computed != digest.etag:
                logger.error(
                    f"MD5 checksum validation failed: {computed=} != {digest.etag}"
                )
                return 32
        # move to destination (should be safe as we're in sub of parent)
        tmp_dest.rename(dest)

    logger.info("Download completed")
    return 0


def deploy_url(url: str, *, reuse_image: bool):
    """Deploy from an URL

    Parameters:
        reuse_image: whether to not remove existing image file and skip download (dev)
    """
    logger.info(f"deploying for {url}")

    if not is_url_correct(url):
        return fail(f"URL is incorrect: {url}")
    logger.info("> URL is OK")

    rc = toggle_demo(mode="maintenance")
    if rc:
        return fail("Failed to switch to maintenance mode")

    if is_mounted(TARGET_DIR):
        logger.info(f"> unmounting {TARGET_DIR}")
        if not unmount(TARGET_DIR):
            return fail(f"Failed to unmout {TARGET_DIR}")

    loop_dev = get_loopdev_used_by(IMAGE_PATH)
    if loop_dev:
        logger.info(f"> detaching {loop_dev}")
        if not detach_device(loop_dev=loop_dev, failsafe=True):
            return fail(f"Failed to detach {loop_dev}")

    if IMAGE_PATH.exists() and not reuse_image:
        logger.info(f"> removing {IMAGE_PATH}")
        try:
            IMAGE_PATH.unlink(missing_ok=True)  # should not be missing
        except Exception as exc:
            logger.exception(exc)
            return fail(f"Failed to remove {IMAGE_PATH}: {exc}")

    logger.info("> purging docker")
    prune_docker()

    logger.info("Download image file using aria2")
    if not reuse_image:
        rc = download_file_into(url=url, dest=IMAGE_PATH, digest=get_checksum_from(url))
        if rc:
            return fail("Failed to download image", rc)

    logger.info("Requesting loop device")
    try:
        loop_dev = get_loopdev()
    except Exception as exc:
        logger.exception(exc)
        return fail("Failed to get loop-devices (all slots taken?)")
    logger.info(f"> {loop_dev}")

    logger.info(f"Attaching image to {loop_dev}")
    try:
        attach_to_device(img_fpath=IMAGE_PATH, loop_dev=loop_dev)
    except Exception as exc:
        logger.debug(exc)
        return fail(f"Failed to attach image to {loop_dev}: {exc}")

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Mounting 3rd partition to {TARGET_DIR}")
    if not mount_on(
        dev_path=f"{loop_dev}p3", mount_point=TARGET_DIR, filesystem="ext4"
    ):
        return fail(f"Failed to mount {loop_dev}p3 to TARGET_DIR")

    rc = prepare_image(target_dir=TARGET_DIR)
    if rc:
        return fail("Failed to prepare image", rc)

    logger.info("Switching to image mode")
    rc = toggle_demo(mode="image")
    if rc:
        return fail("Failed to switch to image mode", rc)

    logger.info("> demo ready")
    return 0


def entrypoint():
    parser = argparse.ArgumentParser(
        prog="demo-deploy", description="Deploy an offspot demo from an Image URL"
    )

    parser.add_argument("-D", "--debug", action="store_true", dest="debug")
    parser.add_argument("-V", "--version", action="version", version=__version__)

    parser.add_argument(
        "--reuse-image",
        action="store_true",
        dest="reuse_image",
        default=False,
        help="[dev] reuse already downloaded image instead of downloading",
    )

    parser.add_argument(
        dest="url",
        help="Imager Service-created Image URL",
    )

    # kwargs = dict(parser.parse_args()._get_kwargs())
    args = parser.parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    try:
        sys.exit(deploy_url(url=args.url, reuse_image=args.reuse_image))
    except Exception as exc:
        if args.debug:
            logger.exception(exc)
        logger.critical(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(entrypoint())
