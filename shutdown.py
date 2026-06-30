"""Stop all scheduled Managed Agent deployments for this project.

Default: pause deployments (reversible — no more cron runs, no new spend).
Use --archive to permanently stop deployments (cannot be unpaused).

Does not archive the agent itself, so `research.py` still works on demand.

Usage:
  python shutdown.py              # pause all deployments
  python shutdown.py --archive    # permanently archive deployments
"""

from __future__ import annotations

import argparse
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


def discover_deployments(client: Anthropic, agent_id: str) -> list[str]:
    """Best-effort list; falls back to .env.ids when the list API is empty."""
    found: list[str] = []
    for page in client.beta.deployments.list(agent_id=agent_id).iter_pages():
        for dep in page.data:
            ref = getattr(dep, "agent", None)
            ref_id = getattr(ref, "id", None) if ref else None
            if ref_id == agent_id or ref_id is None:
                found.append(dep.id)
    return list(dict.fromkeys(found))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Permanently archive deployments (terminal; use pause by default)",
    )
    args = parser.parse_args()

    load_env()
    ids = load_ids()
    client = Anthropic()

    if not hasattr(client.beta, "deployments"):
        sys.exit(
            "anthropic SDK is missing client.beta.deployments. "
            "Upgrade with: pip install -U anthropic"
        )

    agent_id = ids["AGENT_ID"]
    dep_ids = deployment_ids(ids) or discover_deployments(client, agent_id)
    if not dep_ids:
        sys.exit(
            "No deployment IDs found. Add DEPLOYMENT_ID=depl_... lines to .env.ids "
            "after running deploy_alerts.py / deploy_daily_digest.py."
        )

    action = client.beta.deployments.archive if args.archive else client.beta.deployments.pause
    action_name = "Archived" if args.archive else "Paused"

    for dep_id in dep_ids:
        dep = client.beta.deployments.retrieve(dep_id)
        status = getattr(dep, "status", None)
        if status == "archived":
            print(f"  skip {dep.id} ({dep.name}) — already archived")
            continue
        if not args.archive and status == "paused":
            print(f"  skip {dep.id} ({dep.name}) — already paused")
            continue

        action(dep.id)
        print(f"  {action_name} {dep.id} ({dep.name})")

    running = client.beta.sessions.list(agent_id=agent_id, statuses=["running"])
    if running.data:
        print("\nSessions still running (finish on their own; idle sessions cost nothing):")
        for session in running.data:
            print(f"  {session.id}  status={session.status}")

    print()
    if args.archive:
        print("Deployments archived. Re-run deploy_alerts.py / deploy_daily_digest.py to recreate.")
    else:
        print("Deployments paused. Resume with: python unpause.py")


if __name__ == "__main__":
    main()
