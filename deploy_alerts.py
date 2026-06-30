"""Create the scheduled price-alert deployment.

Schedule: every 15 min during US market hours (1300-2059 UTC, Mon-Fri).
Adjust CRON_SCHEDULE if you trade other markets.

Requires WATCHLIST_REPO_URL and GITHUB_TOKEN env vars. The repo must contain
a watchlist.json file (use watchlist.example.json as a template).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from anthropic import Anthropic


CRON_SCHEDULE = "*/15 13-20 * * MON-FRI"
WATCHLIST_MOUNT_PATH = "/workspace/watchlist"
KICKOFF_PROMPT = (
    "run alert check. Read /workspace/watchlist/watchlist.json, evaluate each "
    "armed alert, send SMS via Twilio for any that fired, commit the updated "
    "watchlist.json back to the repo, and write a run summary to "
    "/mnt/session/outputs/run-summary.md."
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
            "Upgrade with: pip install -U anthropic, "
            "or fall back to raw HTTP against POST /v1/deployments with "
            "anthropic-beta: managed-agents-2026-04-01."
        )

    deployment = client.beta.deployments.create(
        name="stock-price-alerts",
        agent=ids["AGENT_ID"],
        environment_id=ids["ENVIRONMENT_ID"],
        vault_ids=[ids["VAULT_ID"]],
        schedule=CRON_SCHEDULE,
        resources=[{
            "type": "github_repository",
            "url": repo_url,
            "mount_path": WATCHLIST_MOUNT_PATH,
            "authorization": repo_token,
        }],
        initial_events=[{
            "type": "user.message",
            "content": [{"type": "text", "text": KICKOFF_PROMPT}],
        }],
    )
    print(f"Deployment: {deployment.id}")
    print(f"Schedule:   {CRON_SCHEDULE}")
    print(f"Watchlist:  {repo_url}")
    print()
    print("Test a single run now with the ant CLI:")
    print(f"  ant beta:deployments run --deployment-id {deployment.id}")


if __name__ == "__main__":
    main()
