"""Entry point for both local runs and the GitHub Action.

Runs every fetcher, then merges and rebuilds the ICS feed. Each fetcher is
independent and failures don't stop the others - a missing API key or a
scraper breaking on one source shouldn't block the rest of the pipeline.
"""
from __future__ import annotations

import os
import sys

import build_ics
import fetch_local_html
import fetch_seatgeek
import fetch_ticketmaster
import merge_and_classify


def _run(label: str, fn) -> None:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - a single source failing shouldn't kill the run
        print(f"[run_all] {label} failed: {exc}", file=sys.stderr)


def main() -> None:
    if os.environ.get("TICKETMASTER_API_KEY"):
        _run("fetch_ticketmaster", fetch_ticketmaster.main)
    else:
        print("[run_all] TICKETMASTER_API_KEY not set, skipping", file=sys.stderr)

    if os.environ.get("SEATGEEK_CLIENT_ID"):
        _run("fetch_seatgeek", fetch_seatgeek.main)
    else:
        print("[run_all] SEATGEEK_CLIENT_ID not set, skipping", file=sys.stderr)

    _run("fetch_local_html", fetch_local_html.main)
    _run("merge_and_classify", merge_and_classify.main)
    _run("build_ics", build_ics.main)


if __name__ == "__main__":
    main()
