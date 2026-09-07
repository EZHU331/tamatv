#!/usr/bin/env python3
"""Persistent community channel submissions."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import m3u
import urlcheck

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
STORE = ROOT / "community" / "channels.json"
PLAYLIST = ROOT / "playlists" / "community.m3u"
ALLOWED_SITE = "https://ezhu331.github.io/tamatv"
MAX_COMMUNITY = 200


def load_records() -> list[dict]:
    if not STORE.exists():
        return []
    payload = json.loads(STORE.read_text(encoding="utf-8"))
    channels = payload.get("channels") if isinstance(payload, dict) else payload
    if not isinstance(channels, list):
        return []
    return [row for row in channels if isinstance(row, dict) and row.get("url")][:MAX_COMMUNITY]


def save_records(records: list[dict]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"channels": records}
    STORE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_to_entry(row: dict) -> m3u.Entry | None:
    url = str(row.get("url") or "").strip()
    if not urlcheck.is_safe_https_url(url):
        return None
    name = m3u.clean_name(str(row.get("name") or ""))
    name = re.sub(r'[\x00-\x1f\x7f"<>]', "", name)
    if not name:
        return None
    country = str(row.get("country") or "").strip().upper()
    if country == "GB":
        country = "UK"
    if len(country) != 2:
        country = ""
    group = m3u.CATEGORY_CANON.get(str(row.get("group") or row.get("category") or "General").strip().lower())
    if not group:
        group = "General"
    logo = str(row.get("logo") or "").strip()
    if not urlcheck.is_safe_https_url(logo):
        logo = ""
    tvg_id = re.sub(r"[^A-Za-z0-9._@-]+", "", str(row.get("tvg_id") or ""))
    return m3u.Entry(
        name=name,
        url=url,
        tvg_id=tvg_id,
        tvg_name=name,
        logo=logo,
        group=group,
        country=country,
        height=m3u.quality_height(name),
    )


def load_entries() -> list[m3u.Entry]:
    entries = []
    for row in load_records():
        entry = record_to_entry(row)
        if entry:
            entries.append(entry)
    return entries


def merge_entries(base: list[m3u.Entry], extra: list[m3u.Entry]) -> list[m3u.Entry]:
    if not extra:
        return base
    pool: dict[str, m3u.Entry] = {}
    for entry in list(base) + list(extra):
        china = m3u.uses_china_groups(entry, "auto")
        m3u.merge_best(pool, m3u.alias_key(entry, china=china), entry)
    by_url: dict[str, m3u.Entry] = {}
    for entry in pool.values():
        m3u.merge_best(by_url, entry.url, entry)
    return list(by_url.values())


def write_playlist() -> int:
    entries = load_entries()
    PLAYLIST.parent.mkdir(parents=True, exist_ok=True)
    if not entries:
        if PLAYLIST.exists():
            PLAYLIST.unlink()
        return 0
    PLAYLIST.write_text(m3u.write_m3u(entries), encoding="utf-8")
    return len(entries)


def featured_row(site: str, origin_href: str, count: int) -> dict:
    base = site.rstrip("/") if site.rstrip("/") == ALLOWED_SITE else ALLOWED_SITE
    href = origin_href if origin_href == "https://github.com/EZHU331/tamatv" else "https://github.com/EZHU331/tamatv"
    return {
        "id": "tamatv-community",
        "kind": "featured",
        "name": "Community",
        "flag": "",
        "url": f"{base}/playlists/community.m3u",
        "format": "M3U",
        "origin": "tamaTV",
        "originHref": href,
        "channels": count,
        "extras": [],
    }


def patch_catalog(site: str, origin_href: str) -> int:
    count = write_playlist()
    path = ROOT / "lists.json"
    if not path.exists():
        return count
    payload = json.loads(path.read_text(encoding="utf-8"))
    featured = [row for row in payload.get("featured") or [] if row.get("id") != "tamatv-community"]
    if count:
        featured.append(featured_row(site, origin_href, count))
    payload["featured"] = featured
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return count


def append_record(record: dict) -> list[dict]:
    records = load_records()
    if len(records) >= MAX_COMMUNITY:
        return records
    records.append(record)
    save_records(records)
    return records


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
