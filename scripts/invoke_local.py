"""Invoke the real Lambda entrypoint locally, no AWS needed.

Exercises the exact function AWS calls in prod, so a passing local run is
strong evidence the deployed Lambda will behave the same way.

Usage:
    uv run python scripts/invoke_local.py [YYYY-MM-DD]
"""

from __future__ import annotations

import sys

from mortgage_rates.handler import handler


def main() -> None:
    event = {}
    if len(sys.argv) > 1:
        event["target_date"] = sys.argv[1]
    result = handler(event, None)
    print(result)


if __name__ == "__main__":
    main()
