"""Shared helpers: config loading and the normalized event shape.

Every fetcher (Ticketmaster, SeatGeek, local HTML) produces a list of dicts
in this shape, so merge_and_classify.py doesn't need to know where an event
came from:

    {
        "id": str,              # stable-ish dedupe key, source-prefixed
        "title": str,
        "url": str | None,
        "venue": str,
        "city": str,
        "state": str | None,
        "start": str | None,    # ISO 8601, may be None if a source only gives a date
        "lane": "local" | "big",
        "category": str,        # e.g. authors, chef_dinners, performances, comedy, music
        "source": str,          # e.g. ticketmaster, seatgeek, html:Elliott Bay Book Company, manual
        "matched_watchlist_name": str | None,
    }
"""
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_regions() -> dict:
    return load_yaml("regions.yml")


def load_watchlist_names() -> list[str]:
    watchlist = load_yaml("watchlist.yml")
    names = []
    for group in watchlist.values():
        if isinstance(group, list):
            names.extend(group)
    return names


def load_local_sources() -> list[dict]:
    return load_yaml("local_sources.yml")["venues"]


def normalize_event(
    *,
    id_,
    title,
    url,
    venue,
    city,
    state,
    start,
    lane,
    category,
    source,
    matched_watchlist_name=None,
    flight_hours=None,
) -> dict:
    return {
        "id": id_,
        "title": title,
        "url": url,
        "venue": venue,
        "city": city,
        "state": state,
        "start": start,
        "lane": lane,
        "category": category,
        "source": source,
        "matched_watchlist_name": matched_watchlist_name,
        "flight_hours": flight_hours,
    }


def write_raw(name: str, events: list[dict]) -> None:
    import json

    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_DIR / f"raw_{name}.json", "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, default=str)


def read_raw(name: str) -> list[dict]:
    import json

    path = DATA_DIR / f"raw_{name}.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)
