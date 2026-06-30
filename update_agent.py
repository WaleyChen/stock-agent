"""Push the latest SYSTEM_PROMPT from setup.py to your existing agent.

Run after changing setup.py (e.g. new daily digest mode) without re-running
full setup.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

from anthropic import Anthropic

from load_env import load_env
from setup import SYSTEM_PROMPT


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
    ids = load_ids()
    client = Anthropic()
    current = client.beta.agents.retrieve(ids["AGENT_ID"])

    agent = client.beta.agents.update(
        ids["AGENT_ID"],
        version=current.version,
        system=SYSTEM_PROMPT,
    )
    print(f"Updated agent {agent.id} (version {getattr(agent, 'version', '?')})")


if __name__ == "__main__":
    main()
