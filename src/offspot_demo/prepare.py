#!/usr/bin/env python3

import argparse
import logging
import sys
from pathlib import Path

from offspot_demo import logger
from offspot_demo.constants import (
    OCI_PLATFORM,
    OFFSPOT_DEMO_TLS_EMAIL,
)
from offspot_demo.utils import fail, is_root
from offspot_demo.utils.deployment import DEPLOYMENTS, Deployment
from offspot_demo.utils.process import run_command
from offspot_demo.utils.yaml import yaml_dump, yaml_load


def docker_pull(ident: str) -> int:
    """pull a docker image via docker CLI"""

    # should we validate `ident` first? As it comes from an external file
    # and we pass it to subprocess…
    return (
        run_command(
            [
                "docker",
                "image",
                "pull",
                "--platform",
                OCI_PLATFORM,
                ident,
            ]
        ).returncode
        == 0
    )


def prepare_for(deployment: Deployment, *, force: bool) -> int:
    """Prepare a deployment from a mounted image path

    Parameters:
        target_dir: the path of a mounted 3rd partition or an offspot image
    """
    logger.info(f"prepare-image from {deployment.target_dir!s}")

    if not is_root():
        return fail("must be root", 1)

    if deployment.is_already_prepared and not force:
        return 0

    dashboard_path = deployment.target_dir / "contents" / "dashboard.yaml"
    image_yaml_path = deployment.target_dir / "image.yaml"

    for fpath in (image_yaml_path, dashboard_path):
        if not fpath.exists():
            return fail(
                f"Missing {fpath.relative_to(deployment.target_dir)} YAML. "  # noqa: ISC003
                + f"Not an Imager Service image? -- {fpath}",
                1,
            )

    # read and parse /data/contents/dashboard.yaml
    dashboard = yaml_load(dashboard_path.read_text())

    # record original FQDN as we'll need it for replaces
    orig_fqdn = str(dashboard["metadata"]["fqdn"])

    # update FQDN
    dashboard["metadata"]["fqdn"] = deployment.fqdn

    # update all entries' urls
    for entry in dashboard.get("packages", []):
        if entry.get("url"):
            entry["url"] = entry["url"].replace(orig_fqdn, deployment.fqdn)
        if entry.get("download", {}).get("url"):
            entry["download"]["url"] = entry["download"]["url"].replace(
                orig_fqdn, deployment.fqdn
            )

    for reader in dashboard.get("readers", []):
        if reader.get("download_url"):
            reader["download_url"] = reader["download_url"].replace(
                orig_fqdn, deployment.fqdn
            )

    for link in dashboard.get("links", []):
        if link.get("url"):
            link["url"] = link["url"].replace(orig_fqdn, deployment.fqdn)

    # overwrite file
    dashboard_path.write_text(yaml_dump(dashboard))

    image_yaml = yaml_load(image_yaml_path.read_text())
    compose = image_yaml.get("offspot", {}).get("containers")
    if not compose:
        return fail("Missing compose definition in image.yaml (offspot.containers)", 1)

    # update compose name so we can have several in parallel
    compose["name"] = f"offspot_{deployment.ident}"

    offspot_data_root = Path("/data")

    subdomains: list[str] = []

    for svcname, service in compose.get("services", {}).items():

        # delete container_name so we can have multiple compose in parallel
        if "container_name" in service.keys():
            del service["container_name"]

        orig_volumes = list(service.get("volumes", []))
        service["volumes"] = []
        for volume in orig_volumes:

            # we accept /data prefixed sources
            if Path(volume["source"]).is_relative_to(offspot_data_root):
                # rewrite so it works off any `target_dir`
                volume["source"] = str(
                    deployment.target_dir
                    / Path(volume["source"]).relative_to(offspot_data_root)
                )
                service["volumes"].append(volume)
                continue

            # reverse-proxy only is allowed to mount /var/log (for metrics)
            if (
                svcname == "reverse-proxy"
                and volume["source"] == "/var/log"
                and service["image"].startswith("ghcr.io/offspot/reverse-proxy:")
            ):
                volume["source"] = f"/var/log/offspot-demo_{deployment.ident}"
                service["volumes"].append(volume)
                Path(f"/var/log/offspot-demo_{deployment.ident}").mkdir(
                    parents=True, exist_ok=True
                )
                continue

            # metrics shares this with reverse-proxy
            if (
                svcname == "metrics"
                and volume["source"] == "/var/log"
                and service["image"].startswith("ghcr.io/offspot/metrics:")
            ):
                volume["source"] = f"/var/log/offspot-demo_{deployment.ident}"
                service["volumes"].append(volume)
                Path(f"/var/log/offspot-demo_{deployment.ident}").mkdir(
                    parents=True, exist_ok=True
                )
                continue

            # other volumes are not accepted and thus removed (not added-back)

        # remove cap_add for all ; will break captive portal but it's OK
        if "cap_add" in service:
            del service["cap_add"]

        # only allow reverse-proxy to define ports ; ensure its 80/443
        if not (
            svcname == "reverse-proxy"
            and service["image"].startswith("ghcr.io/offspot/reverse-proxy:")
        ):
            if "ports" in service:
                del service["ports"]
        else:
            service["ports"] = [
                f"{deployment.http_port}:80",
            ]

        # dont allow using network_mode (captive portal with be switched to ports)
        if "network_mode" in service:
            del service["network_mode"]

        # convert captive-portal's network_mode expose to new ports
        if svcname == "home-portal" and service["image"].startswith(
            "ghcr.io/offspot/captive-portal:"
        ):
            service["ports"] = [
                f"{deployment.captive_http_port}:80",
            ]

        # allow none to be privileged ; breaks hwclock but it's OK
        if "privileged" in service:
            del service["privileged"]

        # replace fqdn in all environment
        for key, value in list(service.get("environment", {}).items()):
            if key not in ("PROTECTED_SERVICES",):
                service["environment"][key] = value.replace(orig_fqdn, deployment.fqdn)

        if svcname == "reverse-proxy":
            service["environment"]["DEMO_TLS_EMAIL"] = OFFSPOT_DEMO_TLS_EMAIL
            service["environment"]["IS_ONLINE_DEMO"] = "false"
            service["environment"]["FQDN"] = deployment.fqdn
            subdomains += service["environment"]["SERVICES"].split(",")
            subdomains += [
                fm.split(":")[0]
                for fm in service["environment"].get("FILES_MAPPING", "").split(",")
            ]

    deployment.subdomains = subdomains

    # ATM we only support services
    for key in ("networks", "volumes", "configs", "secrets"):
        if compose.get(key):
            del compose[key]

    # pull all OCI images from oci_images
    for entry in image_yaml.get("oci_images", []):
        if entry["ident"] == "ghcr.io/offspot/reverse-proxy:1.7":
            entry["ident"] = "ghcr.io/offspot/reverse-proxy:1.8"
        logger.info(f"> Pulling OCI Image {entry['ident']}")
        docker_pull(entry["ident"])

    # write new compose to partition
    deployment.image_compose_path.write_text(yaml_dump(compose))

    logger.debug(deployment.image_compose_path.read_text())

    deployment.prepared_ok_path.touch()
    return 0


def entrypoint():
    parser = argparse.ArgumentParser(
        prog="demo-prepare", description="Prepare deployment from mounted image folder"
    )

    parser.add_argument(dest="ident", help="Deployment/image identifier")
    parser.add_argument(
        "--force",
        dest="force",
        action="store_true",
        default=False,
        help="Re-prepare even if already prepared",
    )

    args = parser.parse_args()
    logger.setLevel(logging.DEBUG)

    try:
        sys.exit(prepare_for(DEPLOYMENTS[args.ident], force=args.force))
    except Exception as exc:
        logger.exception(exc)
        logger.critical(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(entrypoint())
