"""Pulls events from the Ticketmaster Discovery API for both lanes.

- Local lane: events at Seattle venues listed in local_sources.yml with
  fetch_method: ticketmaster_venue (Paramount, Moore, Neptune, Benaroya...).
- Big lane: watchlist keyword search across every region in regions.yml,
  plus a big-venue sweep that pulls anything at an allowlisted arena/theater
  in those regions regardless of watchlist match.

Requires TICKETMASTER_API_KEY in the environment. Free tier: 5,000 calls/day,
5 req/s - https://developer.ticketmaster.com/

Runs standalone (writes data/raw_ticketmaster.json) or is called from
run_all.py.
"""
from __future__ import annotations

import os
import sys
import time

import requests

from common import load_local_sources, load_regions, load_watchlist_names, normalize_event, write_raw

API_BASE = "https://app.ticketmaster.com/discovery/v2"
REQUEST_DELAY_SECONDS = 0.25  # stay under the 5 req/s rate limit with margin


def _get(path: str, **params) -> dict:
    api_key = os.environ.get("TICKETMASTER_API_KEY")
    if not api_key:
        raise RuntimeError("TICKETMASTER_API_KEY is not set")
    params["apikey"] = api_key
    resp = requests.get(f"{API_BASE}/{path}", params=params, timeout=20)
    time.sleep(REQUEST_DELAY_SECONDS)
    if resp.status_code == 429:
        raise RuntimeError("Ticketmaster rate limit hit - back off or reduce watchlist size")
    resp.raise_for_status()
    return resp.json()


def _event_to_dict(e: dict) -> dict:
    venue = {}
    try:
        venue = e["_embedded"]["venues"][0]
    except (KeyError, IndexError):
        pass
    start = None
    dates = e.get("dates", {}).get("start", {})
    start = dates.get("dateTime") or dates.get("localDate")
    return {
        "id": e.get("id"),
        "title": e.get("name"),
        "url": e.get("url"),
        "venue": venue.get("name", ""),
        "city": venue.get("city", {}).get("name", ""),
        "state": venue.get("state", {}).get("stateCode", ""),
        "start": start,
    }


def find_venue_id(name: str, city: str, state: str | None = None) -> str | None:
    """Best-effort venue ID lookup by name+city. Returns None if not found."""
    try:
        data = _get("venues.json", keyword=name, city=city, stateCode=state, size=5)
    except requests.RequestException:
        return None
    venues = data.get("_embedded", {}).get("venues", [])
    for v in venues:
        if v.get("name", "").lower().startswith(name.lower()[:8]):
            return v.get("id")
    return venues[0].get("id") if venues else None


def fetch_seattle_venue_events() -> list[dict]:
    events = []
    for source in load_local_sources():
        if source.get("fetch_method") != "ticketmaster_venue":
            continue
        venue_id = source.get("ticketmaster_venue_id") or find_venue_id(source["name"], "Seattle", "WA")
        if not venue_id:
            print(f"[ticketmaster] could not resolve venue id for {source['name']!r}, skipping", file=sys.stderr)
            continue
        try:
            data = _get("events.json", venueId=venue_id, size=50)
        except requests.RequestException as exc:
            print(f"[ticketmaster] venue fetch failed for {source['name']!r}: {exc}", file=sys.stderr)
            continue
        for e in data.get("_embedded", {}).get("events", []):
            d = _event_to_dict(e)
            events.append(
                normalize_event(
                    id_=f"ticketmaster:{d['id']}",
                    title=d["title"],
                    url=d["url"],
                    venue=d["venue"] or source["name"],
                    city="Seattle",
                    state="WA",
                    start=d["start"],
                    lane="local",
                    category=source.get("category", "performances"),
                    source="ticketmaster",
                )
            )
    return events


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
                data = _get(
                    "events.json",
                    keyword=name,
                    city=region["city"],
                    stateCode=region.get("state"),
                    countryCode=region.get("country", "US"),
                    size=10,
                )
            except requests.RequestException as exc:
                print(f"[ticketmaster] watchlist search failed for {name!r} in {region['name']}: {exc}", file=sys.stderr)
                continue
            for e in data.get("_embedded", {}).get("events", []):
                d = _event_to_dict(e)
                events.append(
                    normalize_event(
                        id_=f"ticketmaster:{d['id']}",
                        title=d["title"],
                        url=d["url"],
                        venue=d["venue"],
                        city=d["city"] or region["city"],
                        state=d["state"] or region.get("state"),
                        start=d["start"],
                        lane="big",
                        category="watchlist",
                        source="ticketmaster",
                        matched_watchlist_name=name,
                        flight_hours=flight_hours,
                    )
                )
    return events


def fetch_big_venue_sweep() -> list[dict]:
    regions_cfg = load_regions()
    threshold = regions_cfg["threshold_hours"]
    allowlist = regions_cfg.get("big_venue_allowlist", [])
    allowlist_names = {entry.split(" (")[0].strip().lower() for entry in allowlist}
    events = []
    for region in regions_cfg["regions"]:
        flight_hours = region.get("flight_hours", region.get("drive_hours"))
        if flight_hours is None or flight_hours > threshold:
            continue
        try:
            data = _get(
                "events.json",
                city=region["city"],
                stateCode=region.get("state"),
                countryCode=region.get("country", "US"),
                classificationName="Music,Sports,Arts & Theatre",
                size=100,
            )
        except requests.RequestException as exc:
            print(f"[ticketmaster] big-venue sweep failed for {region['name']}: {exc}", file=sys.stderr)
            continue
        for e in data.get("_embedded", {}).get("events", []):
            d = _event_to_dict(e)
            if d["venue"].strip().lower() not in allowlist_names:
                continue
            events.append(
                normalize_event(
                    id_=f"ticketmaster:{d['id']}",
                    title=d["title"],
                    url=d["url"],
                    venue=d["venue"],
                    city=d["city"] or region["city"],
                    state=d["state"] or region.get("state"),
                    start=d["start"],
                    lane="big",
                    category="big_venue",
                    source="ticketmaster",
                    flight_hours=flight_hours,
                )
            )
    return events


def main() -> None:
    events = fetch_seattle_venue_events() + fetch_watchlist_events() + fetch_big_venue_sweep()
    write_raw("ticketmaster", events)
    print(f"[ticketmaster] wrote {len(events)} events")


if __name__ == "__main__":
    main()
