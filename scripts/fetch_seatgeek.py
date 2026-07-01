"""Secondary source for the big lane: SeatGeek watchlist search.

Cross-checks Ticketmaster for coverage gaps (comedy and some theater tend to
list on one platform but not the other). Local lane is intentionally not
covered here - SeatGeek doesn't have useful data for small author/bookstore
events.

Requires SEATGEEK_CLIENT_ID in the environment (free, no secret needed for
read-only search) - https://platform.seatgeek.com/
"""
from __future__ import annotations

import os
import sys

import requests

from common import load_regions, load_watchlist_names, normalize_event, write_raw

API_BASE = "https://api.seatgeek.com/2"


def _get(path: str, **params) -> dict:
    client_id = os.environ.get("SEATGEEK_CLIENT_ID")
    if not client_id:
        raise RuntimeError("SEATGEEK_CLIENT_ID is not set")
    params["client_id"] = client_id
    resp = requests.get(f"{API_BASE}/{path}", params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_watchlist_events() -> list[dict]:
    regions_cfg = load_regions()
    threshold = regions_cfg["threshold_hours"]
    names = load_watchlist_names()
    events = []
    for region in regions_cfg["regions"]:
        flight_hours = region.get("flight_hours", region.get("drive_hours"))
        if flight_hours is None or flight_hours > threshold:
            continue
        for name in names:
            try:
                data = _get("events", q=name, **{"venue.city": region["city"]}, per_page=10)
            except requests.RequestException as exc:
                print(f"[seatgeek] search failed for {name!r} in {region['name']}: {exc}", file=sys.stderr)
                continue
            for e in data.get("events", []):
                venue = e.get("venue", {})
                events.append(
                    normalize_event(
                        id_=f"seatgeek:{e.get('id')}",
                        title=e.get("title") or e.get("short_title"),
                        url=e.get("url"),
                        venue=venue.get("name", ""),
                        city=venue.get("city") or region["city"],
                        state=venue.get("state") or region.get("state"),
                        start=e.get("datetime_utc"),
                        lane="big",
                        category="watchlist",
                        source="seatgeek",
                        matched_watchlist_name=name,
                        flight_hours=flight_hours,
                    )
                )
    return events


def main() -> None:
    events = fetch_watchlist_events()
    write_raw("seatgeek", events)
    print(f"[seatgeek] wrote {len(events)} events")


if __name__ == "__main__":
    main()
