#!/usr/bin/env python3

""" Deploy an image from an image URL

Limitations:
- URL must be hosted on S3 (or at least webserver must serve an md5 digest in ETag)
- Image must be Imager-service-created: have its data in a 3rd ext4 partition
"""

import argparse
import logging
import shutil
import sys
from http import HTTPStatus

import requests.exceptions

from offspot_demo import logger
from offspot_demo.deploy import unmount_detach_release
from offspot_demo.utils import fail, is_root
from offspot_demo.utils.deployment import DEPLOYMENTS, Deployment
from offspot_demo.utils.docker import stop_demo


def undeploy_for(deployment: Deployment, *, keep_image: bool):
    try:
        deployment.download_url  # noqa: B018
    except requests.exceptions.HTTPError as exc:
        if exc.response.status_code == HTTPStatus.NOT_FOUND:
            deployment._download_url = f"Gone image ({deployment.ident})"  # pyright: ignore [reportPrivateUsage]

        else:
            raise exc
    logger.info(f"undeploying for {deployment.download_url}")

    if not is_root():
        return fail("must be root", 1)

    logger.info("> stopping compose")
    stop_demo(deployment)

    rc = unmount_detach_release(deployment)
    if rc:
        return fail("Unable to release image", rc)

    if not keep_image:
        logger.info("> removing image file")
        deployment.image_path.unlink(missing_ok=True)
        logger.info("> removing temp image file")
        deployment.tmp_image_path.unlink(missing_ok=True)

    logger.info("> removing data dir")
    shutil.rmtree(deployment.target_dir, ignore_errors=True)


def entrypoint():
    parser = argparse.ArgumentParser(
        prog="demo-deploy", description="Deploy an offspot demo from a deployment ident"
    )
    parser.add_argument(dest="ident", help="Deployment/image identifier")

    parser.add_argument(
        "--keep",
        dest="keep",
        action="store_true",
        default=False,
        help="Keep the image file (otherwise removes it)",
    )

    args = parser.parse_args()
    logger.setLevel(logging.DEBUG)

    try:
        sys.exit(undeploy_for(deployment=DEPLOYMENTS[args.ident], keep_image=args.keep))
    except Exception as exc:
        logger.exception(exc)
        logger.critical(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(entrypoint())
