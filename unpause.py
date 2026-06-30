"""Resume paused deployments for this project.

Usage: python unpause.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from anthropic import Anthropic

from load_env import load_env


def load_ids() -> dict[str, str]:
    env_file = Path(__file__).parent / ".env.ids"
    if not env_file.exists():
        sys.exit("Missing .env.ids — run setup.py first.")
    return dict(
        line.split("=", 1)
        for line in env_file.read_text().splitlines()
        if "=" in line
    )


def deployment_ids(ids: dict[str, str]) -> list[str]:
    return list(dict.fromkeys(
        value
        for key, value in ids.items()
        if "DEPLOYMENT" in key and value.startswith("depl_")
    ))


def main() -> None:
    load_env()
    ids = load_ids()
    client = Anthropic()
    dep_ids = deployment_ids(ids)
    if not dep_ids:
        sys.exit("No deployment IDs in .env.ids.")

    for dep_id in dep_ids:
        dep = client.beta.deployments.retrieve(dep_id)
        if getattr(dep, "status", None) != "paused":
            print(f"  skip {dep.id} ({dep.name}) — status={dep.status}")
            continue
        client.beta.deployments.unpause(dep.id)
        print(f"  Unpaused {dep.id} ({dep.name})")


if __name__ == "__main__":
    main()
