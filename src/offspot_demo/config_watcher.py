#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path

import requests

from offspot_demo import logger
from offspot_demo.constants import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    MULTI_CONFIG_URL,
    OFFSPOT_CONFIGURATION,
)
from offspot_demo.utils import fail, is_root
from offspot_demo.utils.yaml import yaml_load

RE_ENVIRON = re.compile(
    r"^(?P<name>[A-Za-z0-9\_]+)=([\"\']?)(?P<value>[^\"\']+)([\"\']?)$"
)


def load_environ(fpath: Path) -> dict[str, str]:
    """dict repr of all values in envrionment file"""
    environ: dict[str, str] = {}
    lines = fpath.read_text().splitlines()

    for line in lines:
        if m := RE_ENVIRON.match(line):
            environ.update({m.groupdict()["name"]: m.groupdict()["value"]})
    return environ


def save_environ(environ: dict[str, str], fpath: Path):
    """save environ into file, keeping extra lines, updating existing, appending new"""

    def line_for(name: str, value: str) -> str:
        return f'{name}="{value}"'

    orig_lines = fpath.read_text().splitlines()
    new_lines: list[str] = []

    for line in orig_lines:
        # updating existing keys in place
        if m := RE_ENVIRON.match(line):
            name, value = m.groupdict()["name"], m.groupdict()["value"]
            if name in environ:
                new_lines.append(line_for(name, environ[name]))
                del environ[name]
        # keeping comments
        else:
            new_lines.append(line)

    for name, value in environ.items():
        new_lines.append(line_for(name, value))

    new_lines.append("")

    fpath.write_text("\n".join(new_lines))


def check_and_record():
    """Check if a new image has to be deployed, and deploy it"""
    if not is_root():
        return fail("must be root", 1)

    logger.info("Checking for updates to demos YAML conf online")

    resp = requests.get(MULTI_CONFIG_URL, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()
    payload = yaml_load(resp.text)
    demos_conf = ",".join(
        f'{demo["ident"]}:{demo.get("alias", demo["ident"])}:'
        f'{demo.get("name", demo["ident"])}:'
        for demo in payload["demos"]
    )

    environ = load_environ(OFFSPOT_CONFIGURATION)
    if environ["OFFSPOT_DEMOS_LIST"] == demos_conf:
        logger.info("> No change, exiting.")
        return 0

    logger.info(f"> Online config updated. Recording new conf: {demos_conf}")
    environ["OFFSPOT_DEMOS_LIST"] = demos_conf
    save_environ(environ, fpath=OFFSPOT_CONFIGURATION)
    logger.info("> done. exiting.")


def entrypoint():
    parser = argparse.ArgumentParser(
        prog="demo-config-watcher",
        description="Watch multi-demo config URL for changes",
    )
    parser.parse_args()
    try:
        check_and_record()
        sys.exit()
    except Exception as exc:
        logger.exception(exc)
        logger.critical(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(entrypoint())
