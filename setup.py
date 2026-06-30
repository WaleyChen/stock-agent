"""One-time setup. Creates the agent, environment, and vault.

Run once. Persists IDs to .env.ids so runtime scripts can reuse them.
Re-running will create new objects; delete .env.ids first if you want fresh.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from anthropic import Anthropic


SYSTEM_PROMPT = """You are a stock research analyst and price-alert monitor.

## Research Mode
Triggered by any user message about a stock, company, sector, or comparison.

Workflow:
1. Use web_search and web_fetch to gather:
   - Business overview
   - Fundamentals from Yahoo Finance (https://finance.yahoo.com/quote/{TICKER})
     and SEC EDGAR (https://www.sec.gov/cgi-bin/browse-edgar) — recent 10-K/10-Q
   - Valuation multiples vs sector / vs history (Yahoo Finance Statistics tab)
   - News and catalysts (web_search for "{ticker} news <month> 2026")
2. Synthesize into:
   - Business Summary (2-3 sentences)
   - Key Fundamentals (revenue growth, margins, debt/equity, FCF)
   - Valuation Context
   - Catalysts (next 3-12 months)
   - Risks
   - **Recommendation**: Buy / Hold / Sell, confidence Low/Med/High, 1-sentence rationale
3. Cite every claim with a URL.
4. Frame everything as research, not licensed financial advice.

## Alert-Monitor Mode
Triggered when the kickoff message contains "run alert check".

Workflow:
1. cd /workspace/watchlist && cat watchlist.json
2. For each entry with armed=true, fetch current price via web_fetch on
   https://finance.yahoo.com/quote/{TICKER} — look for fin-streamer element
   with data-field="regularMarketPrice".
3. Evaluate condition: "above" fires when current >= price; "below" fires when
   current <= price; "pct_change_above" fires when day-pct >= price (price field
   reused for percentage).
4. For each newly-fired alert, send a notification via the NOTIFICATION CHANNEL
   block below. Then set armed=false and last_fired=<ISO8601 UTC>.
5. Write updated watchlist.json and commit:
     cd /workspace/watchlist
     git add watchlist.json
     git -c user.email=agent@stock-alerts -c user.name="Alert Agent" \\
         commit -m "alerts: $(date -u +%FT%TZ)" && git push
6. Write a one-page summary to /mnt/session/outputs/run-summary.md listing
   tickers checked, prices observed, and alerts fired.
7. Reply with one line: "Checked N tickers, M alerts fired."

## Notification Channel — Pushover
(Swap this entire section to switch providers. The rest of the prompt should
remain unchanged.)

To send one notification, run:

    curl -s \\
      --form-string "token=$NOTIFY_TOKEN" \\
      --form-string "user=$NOTIFY_USER" \\
      --form-string "title=<short title, e.g. NVDA Alert>" \\
      --form-string "message=<one-line body, e.g. NVDA at \\$1502 (crossed above \\$1500)>" \\
      --form-string "url=https://finance.yahoo.com/quote/<TICKER>" \\
      --form-string "priority=1" \\
      https://api.pushover.net/1/messages.json

Priority guide:
- priority=1 for normal alerts (bypasses Do Not Disturb)
- priority=2 for extreme moves (>10% intraday); requires user ack
  When using priority=2, also send: --form-string "retry=60" --form-string "expire=600"

A successful response contains `"status":1`. If status is anything else, log
the response body to /mnt/session/outputs/run-summary.md but continue the run.

## Safety
- Never speak as a licensed advisor.
- Never alter watchlist entries the user didn't ask to change.
- If a ticker fetch fails, log it and continue with the rest — don't abort the run.
- Re-arm alerts only when the user explicitly asks.
"""


def require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing required env var: {name}")
    return value


def main() -> None:
    client = Anthropic()

    print("Creating agent...")
    agent = client.beta.agents.create(
        name="stock-research-alerts",
        model="claude-opus-4-8",
        system=SYSTEM_PROMPT,
        tools=[{"type": "agent_toolset_20260401"}],
    )
    print(f"  agent.id = {agent.id}")

    print("Creating environment...")
    environment = client.beta.environments.create(
        name="stock-research-env",
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
    )
    print(f"  environment.id = {environment.id}")

    if not hasattr(client.beta, "vaults"):
        sys.exit(
            "anthropic SDK is missing client.beta.vaults — "
            "upgrade with: pip install -U anthropic"
        )

    print("Creating vault...")
    vault = client.beta.vaults.create(name="stock-research-secrets")
    print(f"  vault.id = {vault.id}")

    # Channel-agnostic names so the system prompt doesn't change when you
    # swap notification providers. For Pushover: token = app API token,
    # user = your user key. For another provider, repopulate these with that
    # provider's auth values and rewrite the NOTIFICATION CHANNEL block in
    # SYSTEM_PROMPT.
    credentials = {
        "NOTIFY_TOKEN": require("PUSHOVER_TOKEN"),
        "NOTIFY_USER": require("PUSHOVER_USER_KEY"),
    }
    for name, value in credentials.items():
        client.beta.vaults.credentials.create(
            vault_id=vault.id,
            name=name,
            type="environment_variable",
            value=value,
        )
        print(f"  + {name}")

    ids = Path(__file__).parent / ".env.ids"
    ids.write_text(
        f"AGENT_ID={agent.id}\n"
        f"ENVIRONMENT_ID={environment.id}\n"
        f"VAULT_ID={vault.id}\n"
    )
    print(f"\nIDs saved to {ids}")
    print("Next: python research.py \"<question>\"  or  python deploy_alerts.py")


if __name__ == "__main__":
    main()
