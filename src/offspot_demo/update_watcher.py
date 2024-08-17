#!/usr/bin/env python3

import argparse
import logging
import sys

from offspot_demo import logger
from offspot_demo.constants import OFFSPOT_DEMO_TARGET_ROOT_DIR
from offspot_demo.deploy import deploy_for, reconfigure_multiproxy
from offspot_demo.undeploy import undeploy_for
from offspot_demo.utils import fail, is_root
from offspot_demo.utils.deployment import DEPLOYMENTS, Deployment
from offspot_demo.utils.docker import is_demo_healthy


def check_and_deploy():
    """Check if a new image has to be deployed, and deploy it"""
    if not is_root():
        return fail("must be root", 1)

    reconfigure_multiproxy()

    # existing deployments (assumed to be running but we dont check that)
    # are tested for the prepared.ok file which is created near end of deployment
    # this allows maint-mode to be enabled without the script overwritting the depl
    existing_idents: list[str] = [
        fpath.parent.name for fpath in OFFSPOT_DEMO_TARGET_ROOT_DIR.rglob("prepared.ok")
    ]

    for ident in [
        ident for ident in existing_idents if ident not in DEPLOYMENTS.keys()
    ]:
        logger.info(f"Undeploying previous deployment {ident}")
        undeploy_for(Deployment.using(ident=ident, index=99), keep_image=False)

    if not DEPLOYMENTS:
        logger.info("No deployment in config")
        return 0

    for deployment in DEPLOYMENTS.values():
        logger.info(f"[{deployment}] Checking…")
        is_healthy = is_demo_healthy(deployment)
        has_new_image = deployment.has_new_image
        if is_healthy and not has_new_image:
            logger.info("> image has not been updated")
            continue

        if is_healthy:
            logger.info(f"[{deployment}] Image has been updated. re-deploying")
        else:
            logger.info(f"[{deployment}] Deployment is not running. deploying")

        if (
            deploy_for(
                deployment,
                reuse_image=deployment.image_path.exists() and not has_new_image,
                force_prepare=True,
            )
            == 0
        ):
            logger.info("> Deploy OK, persisting last image url")
            deployment.write_last_image_url()
        else:
            logger.error("Failed to deploy. Skipping")
        continue


def entrypoint():
    parser = argparse.ArgumentParser(
        prog="demo-watcher",
        description="Watch offspot demo Image URL updates and trigger deployments",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        dest="debug",
        default=False,
        help="Activate debug logs",
    )

    args = parser.parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    try:
        sys.exit(check_and_deploy())
    except Exception as exc:
        logger.exception(exc)
        logger.critical(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(entrypoint())
