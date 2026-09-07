#!/usr/bin/env python3
"""Pair live channels with logos and XMLTV guide URLs."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from urllib.parse import quote, urlparse

import m3u

CHANNELS_API = "https://iptv-org.github.io/api/channels.json"
LOGOS_API = "https://iptv-org.github.io/api/logos.json"
FANMINGMING_EPG = "https://live.fanmingming.com/e.xml"
FANMINGMING_LOGO = "https://live.fanmingming.com/tv/{name}.png"
GUIDE_112114 = "https://epg.112114.xyz/pp.xml"
JAPANTEREBI_EPG = "https://animenosekai.github.io/japanterebi-xmltv/guide.xml"
EPGSHARE = "https://epgshare01.online/epgshare01/"
MJH_WORLD_EPG = "https://i.mjh.nz/world/epg.xml.gz"

CN_CODES = {"CN", "HK", "MO", "TW"}
GB_TO_UK = {"GB": "UK"}
FORMAT_SCORE = {"SVG": 4, "PNG": 3, "WEBP": 2, "JPEG": 1, "JPG": 1, "GIF": 0}
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
EPGSHARE_COUNTRY_RE = re.compile(r"epg_ripper_([A-Z]{2})\d+\.xml\.gz$", re.I)


def is_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text or ""))


def canon_country(code: str) -> str:
    value = (code or "").upper()
    return GB_TO_UK.get(value, value)


def norm_name(text: str) -> str:
    cleaned = m3u.clean_name(text)
    cleaned = cleaned.replace("综合", "").replace("频道", "")
    cleaned = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", cleaned.lower())
    cleaned = re.sub(r"^cctv0*", "cctv", cleaned)
    return cleaned


def load_channels() -> dict[str, dict]:
    data = json.loads(m3u.fetch_text(CHANNELS_API))
    return {str(item.get("id") or ""): item for item in data if item.get("id")}


def load_logos() -> dict[str, list[dict]]:
    rows = json.loads(m3u.fetch_text(LOGOS_API))
    by_id: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        cid = str(row.get("channel") or "")
        if cid:
            by_id[cid].append(row)
    return by_id


def name_index(channels: dict[str, dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = defaultdict(list)
    for item in channels.values():
        names = [str(item.get("name") or "")]
        names.extend(str(n) for n in (item.get("alt_names") or []))
        for name in names:
            key = norm_name(name)
            if key:
                index[key].append(item)
    return index


def score_logo(row: dict) -> int:
    if not row.get("in_use"):
        return -1
    url = str(row.get("url") or "")
    if not url.startswith("https://"):
        return -1
    width = int(row.get("width") or 0)
    height = int(row.get("height") or 0)
    longest = max(width, height)
    size_score = 0
    if 128 <= longest <= 1280:
        size_score = 3
    elif longest > 1280:
        size_score = 1
    elif longest >= 64:
        size_score = 1
    fmt = str(row.get("format") or "").upper()
    return FORMAT_SCORE.get(fmt, 0) * 10 + size_score


def pick_logo(channel_id: str, current: str, logos: dict[str, list[dict]]) -> str:
    best_url = current if current.startswith("https://") else ""
    best_score = 12 if best_url else -1
    for row in logos.get(channel_id, []):
        score = score_logo(row)
        if score > best_score:
            best_score = score
            best_url = str(row.get("url") or best_url)
    return best_url


def match_channel(entry: m3u.Entry, channels: dict[str, dict], names: dict[str, list[dict]]) -> dict | None:
    cid = entry.channel_id or (entry.tvg_id.split("@", 1)[0] if entry.tvg_id else "")
    if cid in channels:
        return channels[cid]
    key = norm_name(entry.tvg_name or entry.name)
    hits = names.get(key) or []
    if not hits:
        return None
    country = canon_country(entry.country)
    if country:
        local = [item for item in hits if str(item.get("country") or "").upper() == country]
        if len(local) == 1:
            return local[0]
        if local:
            hits = local
    open_hits = [item for item in hits if not item.get("closed") and not item.get("is_nsfw")]
    if len(open_hits) == 1:
        return open_hits[0]
    return None


def china_logo(entry: m3u.Entry) -> str:
    name = entry.tvg_name or m3u.clean_name(entry.name)
    if not name:
        return ""
    return FANMINGMING_LOGO.format(name=quote(name))


def attach(
    entries: list[m3u.Entry],
    channels: dict[str, dict],
    logos: dict[str, list[dict]],
    country_names: set[str] | None = None,
) -> list[m3u.Entry]:
    names = name_index(channels)
    countries = {item.lower() for item in (country_names or set())}
    kept: list[m3u.Entry] = []
    for entry in entries:
        cid = entry.tvg_id.split("@", 1)[0] if entry.tvg_id else entry.channel_id
        if cid.startswith("mjh-"):
            cid = ""
        entry.channel_id = cid
        meta = match_channel(entry, channels, names)
        if meta:
            if meta.get("is_nsfw") or meta.get("closed"):
                continue
            entry.channel_id = str(meta.get("id") or entry.channel_id)
            if not entry.tvg_id or entry.tvg_id.startswith("mjh-"):
                entry.tvg_id = entry.channel_id
            entry.country = canon_country(str(meta.get("country") or entry.country))
            if not entry.tvg_name:
                entry.tvg_name = str(meta.get("name") or "")
            cats = [str(c) for c in (meta.get("categories") or []) if c]
            group = (entry.group or "").strip()
            if m3u.SKIP_GROUP_RE.search(group):
                pass
            elif not group or group.lower() in countries or group.lower() in {"undefined", "general"}:
                entry.group = ";".join(cats)
        else:
            if not entry.country:
                entry.country = canon_country(m3u.country_from_tvg(entry.tvg_id))
            if (entry.group or "").lower() in countries:
                entry.group = ""
        entry.country = canon_country(entry.country)
        entry.logo = pick_logo(entry.channel_id, entry.logo, logos)
        china = entry.country in CN_CODES or is_cjk(entry.name) or is_cjk(entry.group)
        if china:
            if not entry.tvg_name:
                entry.tvg_name = m3u.clean_name(entry.name)
            if not entry.tvg_id or entry.tvg_id.startswith("mjh-"):
                entry.tvg_id = entry.tvg_name or entry.tvg_id
            if not entry.logo.startswith("https://"):
                entry.logo = china_logo(entry)
        kept.append(entry)
    return kept


def parse_epgshare_map(urls: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for url in urls:
        match = EPGSHARE_COUNTRY_RE.search(urlparse_path(url))
        if not match:
            continue
        code = canon_country(match.group(1))
        mapping.setdefault(code, url)
    return mapping


def urlparse_path(url: str) -> str:
    return urlparse(url).path


def epg_for_country(code: str, epgshare: dict[str, str], has_mjh: bool = False) -> list[str]:
    code = canon_country(code)
    urls: list[str] = []
    if code == "JP":
        urls.append(JAPANTEREBI_EPG)
    elif code in CN_CODES:
        urls.extend([FANMINGMING_EPG, GUIDE_112114])
    elif code in epgshare:
        urls.append(epgshare[code])
    if has_mjh and MJH_WORLD_EPG not in urls:
        urls.append(MJH_WORLD_EPG)
    return urls[:3]


def epg_for_entries(entries: list[m3u.Entry], epgshare: dict[str, str], country: str = "") -> list[str]:
    has_mjh = any((e.tvg_id or "").startswith("mjh-") for e in entries)
    if country:
        return epg_for_country(country, epgshare, has_mjh=has_mjh)
    counts: dict[str, int] = defaultdict(int)
    for entry in entries:
        if entry.country:
            counts[entry.country] += 1
    ranked = sorted(counts, key=lambda key: counts[key], reverse=True)
    urls: list[str] = []
    seen: set[str] = set()
    for code in ranked[:4]:
        for url in epg_for_country(code, epgshare, has_mjh=has_mjh and not urls):
            if url not in seen:
                seen.add(url)
                urls.append(url)
        if len(urls) >= 3:
            break
    return urls[:3]


def join_epg(urls: list[str]) -> str:
    return ",".join(urls)
