import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

try:
    from yaml import CDumper as Dumper
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    # we don't NEED cython ext but it's faster so use it if avail.
    from yaml import Dumper, SafeLoader

from offspot_demo.constants import FQDN, OCI_PLATFORM, TARGET_DIR, logger
from offspot_demo.utils import fail, is_root
from offspot_demo.utils.process import run_command


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


def yaml_dump(data: dict[str, Any]) -> str:
    """YAML textual representation of data"""
    return yaml.dump(data, Dumper=Dumper, explicit_start=True, sort_keys=False)


def yaml_load(data: str) -> dict[str, Any]:
    return yaml.load(data, Loader=SafeLoader)


def prepare_image(target_dir: Path) -> int:
    """Prepare a deployment from a mounted image path

    Parameters:
        target_dir: the path of a mounted 3rd partition or an offspot image
    """
    logger.info(f"prepare-image from {target_dir!s}")

    if not is_root():
        return fail("must be root", 1)

    preapred_ok_path = target_dir / "prepared.ok"
    if preapred_ok_path.exists():
        return 0

    dashboard_path = target_dir / "contents" / "dashboard.yaml"
    image_yaml_path = target_dir / "image.yaml"

    for fpath in (image_yaml_path, dashboard_path):
        if not fpath.exists():
            return fail(
                f"Missing {fpath.relative_to(target_dir)} YAML. "  # noqa: ISC003
                + f"Not an Imager Service image? -- {fpath}",
                1,
            )

    # read and parse /data/contents/dashboard.yaml
    dashboard = yaml_load(dashboard_path.read_text())

    # record original FQDN as we'll need it for replaces
    orig_fqdn = str(dashboard["metadata"]["fqdn"])

    # update FQDN
    dashboard["metadata"]["fqdn"] = FQDN

    # update all entries' urls
    for entry in dashboard.get("packages", []):
        if entry.get("url"):
            entry["url"] = entry["url"].replace(orig_fqdn, FQDN)
        if entry.get("download", {}).get("url"):
            entry["download"]["url"] = entry["download"]["url"].replace(orig_fqdn, FQDN)

    for reader in dashboard.get("readers", []):
        if reader.get("download_url"):
            reader["download_url"] = reader["download_url"].replace(orig_fqdn, FQDN)

    for link in dashboard.get("links", []):
        if link.get("url"):
            link["url"] = link["url"].replace(orig_fqdn, FQDN)

    # overwrite file
    dashboard_path.write_text(yaml_dump(dashboard))

    image_yaml = yaml_load(image_yaml_path.read_text())
    compose = image_yaml.get("offspot", {}).get("containers")
    if not compose:
        return fail("Missing compose definition in image.yaml (offspor.containers)", 1)

    offspot_root = Path("/data")

    for svcname, service in compose.get("services", {}).items():

        for volume in service.get("volumes", []):
            # we accept /data prefixed sources
            if Path(volume["source"]).is_relative_to(offspot_root):
                # rewrite so it works off any `target_dir` but shouldnt be necessary
                # on prod if we use `/data` as well
                volume["source"] = str(
                    target_dir / Path(volume["source"]).relative_to(offspot_root)
                )
                continue
            # reverse-proxy only is allowed to mount /var/log (for metrics)
            if (
                svcname == "reverse-proxy"
                and volume["source"] == "/var/log"
                and service["image"].startswith("ghcr.io/offspot/reverse-proxy:")
            ):
                continue
            # other volumes are not accepted and thus removed
            service["volumes"].remove(volume)

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
            service["ports"] = ["80:80", "443:443"]

        # only allow captive-portal to use set network_mode
        if (
            not (
                svcname == "home-portal"
                and service["image"].startswith("ghcr.io/offspot/captive-portal:")
            )
            and "network_mode" in service
        ):
            del service["network_mode"]

        # allow none to be privileged ; breaks hwclock but it's OK
        if "privileged" in service:
            del service["privileged"]

        # replace fqdn in all environment
        for key, value in list(service.get("environment", {}).items()):
            if key not in ("PROTECTED_SERVICES",):
                service["environment"][key] = value.replace(orig_fqdn, FQDN)

    # ATM we only support services
    for key in ("networks", "volumes", "configs", "secrets"):
        if compose.get(key):
            del compose[key]

    # pull all OCI images from oci_images
    for entry in image_yaml.get("oci_images", []):
        logger.info(f"> Pulling OCI Image {entry['ident']}")
        docker_pull(entry["ident"])

    # write new compose to partition
    target_dir.joinpath("compose.yaml").write_text(yaml_dump(compose))

    preapred_ok_path.touch()
    return 0


def entrypoint():
    parser = argparse.ArgumentParser(
        prog="demo-prepare", description="Prepare deployment from mounted image folder"
    )

    parser.add_argument(
        dest="target_dir",
        help="Path to the image's third partition, to prepare from",
        default=str(TARGET_DIR),
    )

    args = parser.parse_args()
    logger.setLevel(logging.DEBUG)

    try:
        sys.exit(prepare_image(target_dir=Path(args.target_dir).expanduser().resolve()))
    except Exception as exc:
        logger.exception(exc)
        logger.critical(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(entrypoint())
