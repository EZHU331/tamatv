#!/usr/bin/env python3
"""Discover public live M3U/TXT playlists from known indexes."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import m3u

SEED_PLAYLISTS = [
    "https://iptv-org.github.io/iptv/index.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
    "https://i.mjh.nz/world/raw-tv.m3u8",
    "https://live.fanmingming.com/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.m3u",
    "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u",
    "https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u",
    "https://raw.githubusercontent.com/BurningC4/Chinese-IPTV/master/IPTV-Unicom.m3u",
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/master/cnTV_AutoUpdate.m3u8",
    "https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u",
    "https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv6.m3u",
    "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/ipv4/result.m3u",
    "https://raw.githubusercontent.com/joevess/IPTV/main/home.m3u8",
    "https://raw.githubusercontent.com/wwb521/live/main/tv.m3u",
    "https://raw.githubusercontent.com/ssili126/tv/main/itvlist.m3u",
]

SEED_INDEXES = [
    "https://raw.githubusercontent.com/ngo5/IPTV/main/README.md",
    "https://m3u.ibert.me/",
]

GITHUB_LISTS = [
    ("BuddyChewChew/app-m3u-generator", "playlists", "_all.m3u"),
]

SKIP_PLAYLIST_RE = re.compile(
    r"(vod|xxx|adult|porn|点播|radio|movie.?box|/all\.m3u|o_all|/all\.txt|get\.php|player_api)",
    re.I,
)
PLAYLIST_URL_RE = re.compile(
    r"""https://[^\s"'<>)]+\.(?:m3u8?|txt)(?:\?[^\s"'<>)]*)?""",
    re.I,
)
REL_PLAYLIST_RE = re.compile(r"""href=["']([^"']+\.(?:m3u8?|txt))["']""", re.I)
MAX_PLAYLISTS = 90
FETCH_WORKERS = 16

PLAYLIST_HOSTS = {
    "iptv-org.github.io",
    "raw.githubusercontent.com",
    "github.com",
    "i.mjh.nz",
    "m3u.ibert.me",
    "live.zbds.top",
    "live.zbds.org",
    "live.fanmingming.cn",
    "live.fanmingming.com",
    "tv.iill.top",
    "yang-1989.eu.org",
    "cdn.jsdelivr.net",
}


@dataclass
class PlaylistSource:
    url: str
    origin: str
    text: str


def host_ok(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower()
    if host in PLAYLIST_HOSTS:
        return True
    return host.endswith(".github.io")


def playlist_url_ok(url: str) -> bool:
    if not host_ok(url):
        return False
    if SKIP_PLAYLIST_RE.search(url):
        return False
    path = urlparse(url).path.lower()
    return path.endswith((".m3u", ".m3u8", ".txt"))


def origin_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    path = urlparse(url).path
    if "iptv-org" in host or "/iptv-org/" in path:
        return "iptv-org"
    if "Free-TV/IPTV" in path:
        return "Free-TV"
    if host == "i.mjh.nz":
        return "i.mjh.nz"
    if "fanmingming" in host or "fanmingming" in path:
        return "fanmingming"
    if "BuddyChewChew" in path:
        return "BuddyChewChew"
    if host == "m3u.ibert.me":
        return "iptv-sources"
    if "vbskycn" in path or "zbds." in host:
        return "vbskycn"
    return host.split(".")[0]


def extract_playlist_urls(text: str, base: str = "") -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in PLAYLIST_URL_RE.findall(text or ""):
        url = match.rstrip(".,);")
        if playlist_url_ok(url) and url not in seen:
            seen.add(url)
            found.append(url)
    if base:
        for match in REL_PLAYLIST_RE.findall(text or ""):
            url = urljoin(base, match.lstrip("/"))
            if playlist_url_ok(url) and url not in seen:
                seen.add(url)
                found.append(url)
    return found


def github_download_urls(repo: str, path: str, suffix: str) -> list[str]:
    api = f"https://api.github.com/repos/{repo}/contents/{path}"
    try:
        rows = json.loads(m3u.fetch_text(api, timeout=30))
    except Exception as err:
        print(f"skip github {repo}: {err}", flush=True)
        return []
    urls = []
    for row in rows:
        name = str(row.get("name") or "")
        download = str(row.get("download_url") or "")
        if name.endswith(suffix) and download.startswith("https://") and playlist_url_ok(download):
            urls.append(download)
    return urls


def discover() -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        if url in seen or not playlist_url_ok(url):
            return
        seen.add(url)
        urls.append(url)

    for url in SEED_PLAYLISTS:
        add(url)
    for repo, path, suffix in GITHUB_LISTS:
        for url in github_download_urls(repo, path, suffix):
            add(url)
    for index in SEED_INDEXES:
        try:
            text = m3u.fetch_text(index, timeout=30)
        except Exception as err:
            print(f"skip index {index}: {err}", flush=True)
            continue
        for url in extract_playlist_urls(text, base=index):
            add(url)
    return urls[:MAX_PLAYLISTS]


def _fetch_one(url: str) -> PlaylistSource | None:
    try:
        text = m3u.fetch_text(url, timeout=45)
    except Exception as err:
        print(f"skip playlist {url}: {err}", flush=True)
        return None
    if "#EXTINF" not in text and "#genre#" not in text:
        return None
    return PlaylistSource(url=url, origin=origin_from_url(url), text=text)


def collect(urls: list[str] | None = None) -> list[PlaylistSource]:
    targets = urls if urls is not None else discover()
    out: list[PlaylistSource] = []
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        futures = {pool.submit(_fetch_one, url): url for url in targets}
        done = 0
        total = len(futures)
        for fut in as_completed(futures):
            done += 1
            item = fut.result()
            if item:
                out.append(item)
            if done == total or done % 10 == 0:
                print(f"harvest {done}/{total} ({len(out)} playlists)", flush=True)
    return out


def header_epg_urls(text: str) -> list[str]:
    first = (text or "").lstrip().splitlines()[0] if text else ""
    match = re.search(r'(?:url-tvg|x-tvg-url)="([^"]+)"', first, re.I)
    if not match:
        return []
    urls = []
    for raw in match.group(1).split(","):
        url = raw.strip()
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            continue
        if "ALL_SOURCES" in url or "DUMMY" in url:
            continue
        urls.append(url)
    return urls
