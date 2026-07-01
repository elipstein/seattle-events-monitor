"""Generates data/events.ics from data/events.json.

Lets the board double as a subscribable calendar feed - point Google/Apple
Calendar at the raw GitHub URL for events.ics and new events show up
automatically after each daily run.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from icalendar import Calendar, Event

from common import DATA_DIR


def _parse_start(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.fromisoformat(raw + "T00:00:00+00:00")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def main() -> None:
    with open(DATA_DIR / "events.json", encoding="utf-8") as f:
        data = json.load(f)

    cal = Calendar()
    cal.add("prodid", "-//Seattle Events Monitor//seattle-events-monitor//")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Seattle Events Monitor")

    for e in data["events"]:
        start = _parse_start(e.get("start"))
        if not start:
            continue
        vevent = Event()
        vevent.add("uid", e["id"])
        lane_label = "In Your Backyard" if e["lane"] == "local" else "Worth the Flight"
        vevent.add("summary", f"[{lane_label}] {e['title']}")
        vevent.add("dtstart", start)
        vevent.add("dtend", start + timedelta(hours=2))
        location_bits = [b for b in (e.get("venue"), e.get("city"), e.get("state")) if b]
        vevent.add("location", ", ".join(location_bits))
        if e.get("url"):
            vevent.add("url", e["url"])
        description_bits = [f"Category: {e.get('category', 'other')}"]
        if e.get("matched_watchlist_name"):
            description_bits.append(f"Matched watchlist: {e['matched_watchlist_name']}")
        if e.get("flight_hours") is not None:
            description_bits.append(f"~{e['flight_hours']}h flight from SEA")
        vevent.add("description", "\n".join(description_bits))
        cal.add_component(vevent)

    with open(DATA_DIR / "events.ics", "wb") as f:
        f.write(cal.to_ical())

    print(f"[ics] wrote data/events.ics ({len(data['events'])} events considered)")


if __name__ == "__main__":
    main()
