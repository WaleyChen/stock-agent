"""Create the daily watchlist digest deployment.

Schedule: once per day at 17:00 America/New_York (after US market close).
Sends a single Pushover summary of watchlist prices and armed alerts.

Requires the same env vars as deploy_alerts.py. Run update_agent.py first if
you set up before daily digest was added to the system prompt.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from anthropic import Anthropic

from load_env import load_env

# 5pm ET every day — digest after the US cash session.
CRON_EXPRESSION = "0 17 * * *"
CRON_TIMEZONE = "America/New_York"
WATCHLIST_MOUNT_PATH = "/workspace/watchlist"
KICKOFF_PROMPT = (
    "run daily digest. Read /workspace/watchlist/watchlist.json, fetch current "
    "prices for every ticker in the watchlist, send one Pushover summary "
    "notification, and write a run summary to "
    "/mnt/session/outputs/run-summary.md. Do not modify watchlist.json."
)


def load_ids() -> dict[str, str]:
    env_file = Path(__file__).parent / ".env.ids"
    if not env_file.exists():
        sys.exit("Missing .env.ids — run setup.py first.")
    return dict(
        line.split("=", 1)
        for line in env_file.read_text().splitlines()
        if "=" in line
    )


def main() -> None:
    load_env()
    repo_url = os.environ.get("WATCHLIST_REPO_URL")
    repo_token = os.environ.get("GITHUB_TOKEN")
    if not repo_url:
        sys.exit("Set WATCHLIST_REPO_URL=https://github.com/you/stock-watchlist")
    if not repo_token:
        sys.exit("Set GITHUB_TOKEN=<fine-grained PAT with Contents: read & write>")

    ids = load_ids()
    client = Anthropic()

    if not hasattr(client.beta, "deployments"):
        sys.exit(
            "anthropic SDK is missing client.beta.deployments. "
            "Upgrade with: pip install -U anthropic"
        )

    deployment = client.beta.deployments.create(
        name="stock-daily-digest",
        agent=ids["AGENT_ID"],
        environment_id=ids["ENVIRONMENT_ID"],
        vault_ids=[ids["VAULT_ID"]],
        schedule={
            "type": "cron",
            "expression": CRON_EXPRESSION,
            "timezone": CRON_TIMEZONE,
        },
        resources=[{
            "type": "github_repository",
            "url": repo_url,
            "mount_path": WATCHLIST_MOUNT_PATH,
            "authorization_token": repo_token,
        }],
        initial_events=[{
            "type": "user.message",
            "content": [{"type": "text", "text": KICKOFF_PROMPT}],
        }],
    )
    print(f"Deployment: {deployment.id}")
    print(f"Schedule:   {CRON_EXPRESSION} ({CRON_TIMEZONE})")
    print(f"Watchlist:  {repo_url}")
    print()
    print("Test a single run now:")
    print(f"  python -c \"from anthropic import Anthropic; from load_env import load_env; load_env(); Anthropic().beta.deployments.run('{deployment.id}')\"")


if __name__ == "__main__":
    main()
