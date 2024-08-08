import json

from offspot_demo.utils.deployment import Deployment
from offspot_demo.utils.process import run_command


def start_demo(deployment: Deployment):
    stop_demo(deployment=deployment)
    run_command(
        ["docker", "compose", "-f", str(deployment.compose_path), "up", "--build", "-d"]
    )


def stop_demo(deployment: Deployment):
    run_command(
        [
            "docker",
            "compose",
            "-f",
            str(deployment.compose_path),
            "down",
            "--remove-orphans",
            "--volumes",
        ],
        failsafe=True,
    )


def is_demo_healthy(deployment: Deployment) -> bool:
    ps = run_command(
        [
            "docker",
            "compose",
            "-f",
            str(deployment.compose_path),
            "ps",
            "--all",
            "--format",
            "json",
        ],
        failsafe=True,
    )
    if ps.returncode != 0:
        return False
    if not ps.stdout.strip():
        return False
    try:
        for line in ps.stdout.splitlines():
            payload = json.loads(line.strip())
            if payload.get("State") in ("restarting", "removing", "dead", "exited"):
                return False
    except Exception:
        return False
    return True
