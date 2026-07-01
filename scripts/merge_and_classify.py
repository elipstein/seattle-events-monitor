"""Combines every fetcher's output into data/events.json.

Reads data/raw_ticketmaster.json, data/raw_seatgeek.json,
data/raw_local_html.json (written by the other fetch_*.py scripts) plus
data/manual_events.json (hand-curated entries - chef dinners on Tock/Resy
that can't be scraped, see config/local_sources.yml fetch_method: manual).

Dedupes on (normalized title, date, venue), drops events already in the
past, sorts chronologically, and writes the merged result.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from common import DATA_DIR, read_raw, write_raw


def _dedupe_key(event: dict) -> tuple[str, str, str]:
    title = (event.get("title") or "").strip().lower()
    date_part = (event.get("start") or "")[:10]  # just the date, ignore time-of-day drift between sources
    venue = (event.get("venue") or "").strip().lower()
    return (title, date_part, venue)


def _is_future(event: dict, now: datetime) -> bool:
    start = event.get("start")
    if not start:
        return True  # keep events with no parseable date rather than silently dropping them
    try:
        dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    except ValueError:
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt >= now


def load_manual_events() -> list[dict]:
    path = DATA_DIR / "manual_events.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    now = datetime.now(timezone.utc)
    sources = ["ticketmaster", "seatgeek", "local_html"]
    all_events = [e for name in sources for e in read_raw(name)]
    all_events += load_manual_events()

    seen = {}
    for event in all_events:
        key = _dedupe_key(event)
        if key not in seen:
            seen[key] = event
        # if duplicate seen across sources, keep the first (ticketmaster > seatgeek > local_html > manual order above)

    deduped = [e for e in seen.values() if _is_future(e, now)]
    deduped.sort(key=lambda e: e.get("start") or "9999")

    output = {
        "generated_at": now.isoformat(),
        "count": len(deduped),
        "events": deduped,
    }
    with open(DATA_DIR / "events.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"[merge] {len(all_events)} raw -> {len(deduped)} deduped/future events written to data/events.json")


if __name__ == "__main__":
    main()
