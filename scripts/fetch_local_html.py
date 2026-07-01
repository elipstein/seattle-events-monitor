"""Best-effort HTML scraper for Seattle venues with no public feed/API.

This is the fragile part of the pipeline by nature - bookstore and small
venue websites change markup without notice. Each source in
local_sources.yml carries its own CSS selectors so a single site breaking
doesn't take down the others; failures are logged and skipped.

No API key required, but be a reasonable citizen: one request per source,
default requests User-Agent replaced with something identifiable.
"""
from __future__ import annotations

import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from common import load_local_sources, normalize_event, write_raw

HEADERS = {"User-Agent": "seattle-events-monitor/1.0 (personal project, contact via github)"}


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return dateparser.parse(raw, fuzzy=True, default=datetime.now()).isoformat()
    except (ValueError, OverflowError):
        return None


def _scrape_source(source: dict) -> list[dict]:
    events = []
    try:
        resp = requests.get(source["url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[local_html] fetch failed for {source['name']!r}: {exc}", file=sys.stderr)
        return events

    soup = BeautifulSoup(resp.text, "html.parser")
    selectors = source.get("selectors", {})
    nodes = soup.select(selectors.get("event", "")) if selectors.get("event") else []

    for i, node in enumerate(nodes):
        title_el = node.select_one(selectors.get("title", ""))
        date_el = node.select_one(selectors.get("date", ""))
        link_el = node.select_one(selectors.get("link", "a"))

        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            continue

        date_raw = date_el.get("datetime") if date_el and date_el.has_attr("datetime") else None
        if not date_raw and date_el:
            date_raw = date_el.get_text(strip=True)

        href = link_el.get("href") if link_el else None
        if href and href.startswith("/"):
            base = "/".join(source["url"].split("/")[:3])
            href = base + href

        events.append(
            normalize_event(
                id_=f"html:{source['name']}:{i}:{title[:40]}",
                title=title,
                url=href,
                venue=source["name"],
                city="Seattle",
                state="WA",
                start=_parse_date(date_raw),
                lane="local",
                category=source.get("category", "other"),
                source=f"html:{source['name']}",
            )
        )

    if not nodes:
        print(
            f"[local_html] no events matched selectors for {source['name']!r} - "
            "site markup likely changed, update config/local_sources.yml",
            file=sys.stderr,
        )
    return events


def main() -> None:
    all_events = []
    for source in load_local_sources():
        if source.get("fetch_method") != "html":
            continue
        all_events.extend(_scrape_source(source))
    write_raw("local_html", all_events)
    print(f"[local_html] wrote {len(all_events)} events")


if __name__ == "__main__":
    main()
