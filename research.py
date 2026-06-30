"""Run an interactive stock research session.

Usage: python research.py "Should I buy NVDA?"
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


def main() -> None:
    load_env()
    if len(sys.argv) < 2:
        sys.exit('Usage: python research.py "<your question>"')

    question = " ".join(sys.argv[1:])
    ids = load_ids()
    client = Anthropic()

    session = client.beta.sessions.create(
        agent=ids["AGENT_ID"],
        environment_id=ids["ENVIRONMENT_ID"],
        title=f"Research: {question[:60]}",
    )
    print(f"Session: https://platform.claude.com/workspaces/default/sessions/{session.id}\n")

    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[{
                "type": "user.message",
                "content": [{"type": "text", "text": question}],
            }],
        )

        for event in stream:
            match event.type:
                case "agent.message":
                    for block in event.content:
                        if getattr(block, "type", None) == "text":
                            print(block.text, end="", flush=True)
                case "agent.tool_use":
                    print(f"\n[tool: {event.name}]", flush=True)
                case "session.status_idle":
                    print("\n")
                    break
                case "session.status_terminated":
                    print("\n[session terminated]")
                    break


if __name__ == "__main__":
    main()
