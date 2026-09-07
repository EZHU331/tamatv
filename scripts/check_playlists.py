#!/usr/bin/env python3
"""Fail the playlist refresh if composed M3Us look broken."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAYLISTS = ROOT / "playlists"
JUNK = ("chrome/", "safari/", "mozilla/", "like gecko", "group-title=", "http-user-agent")
MIN_COUNTRIES = 20
MIN_CATEGORIES = 8
MIN_CHANNELS = 100
MIN_LOGO_RATIO = 0.60
MIN_TVG_RATIO = 0.50


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def check_file(path: Path) -> tuple[int, int, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    rel = path.relative_to(ROOT)
    if not text.lstrip().startswith("#EXTM3U"):
        fail(f"{rel}: missing #EXTM3U")
    channels = logos = tvg = 0
    for line in text.splitlines():
        if not line.startswith("#EXTINF:"):
            continue
        channels += 1
        title = line.split(",", 1)[-1] if "," in line else line
        lower = title.lower()
        for token in JUNK:
            if token in lower:
                fail(f"{rel}: junk title {title!r}")
        if 'tvg-logo="https://' in line:
            logos += 1
        if 'tvg-id="' in line and 'tvg-id=""' not in line:
            tvg += 1
    return channels, logos, tvg


def main() -> int:
    country_dir = PLAYLISTS / "countries"
    category_dir = PLAYLISTS / "categories"
    if not country_dir.is_dir():
        fail("missing playlists/countries")
    country_files = sorted(country_dir.glob("*.m3u"))
    category_files = sorted(category_dir.glob("*.m3u")) if category_dir.is_dir() else []
    if len(country_files) < MIN_COUNTRIES:
        fail(f"too few country playlists: {len(country_files)}")
    if len(category_files) < MIN_CATEGORIES:
        fail(f"too few category playlists: {len(category_files)}")

    files = list(country_files) + list(category_files)
    agg_dir = PLAYLISTS / "aggregators"
    if agg_dir.is_dir():
        files.extend(sorted(agg_dir.glob("*.m3u")))
    for extra in (ROOT / "japan.m3u", ROOT / "world.m3u"):
        if extra.exists():
            files.append(extra)

    channels = logos = tvg = 0
    for path in files:
        file_channels, file_logos, file_tvg = check_file(path)
        channels += file_channels
        logos += file_logos
        tvg += file_tvg
    if channels < MIN_CHANNELS:
        fail(f"too few channels: {channels}")
    logo_ratio = logos / channels
    tvg_ratio = tvg / channels
    if logo_ratio < MIN_LOGO_RATIO:
        fail(f"logo coverage {logo_ratio:.1%} below {MIN_LOGO_RATIO:.0%}")
    if tvg_ratio < MIN_TVG_RATIO:
        fail(f"tvg-id coverage {tvg_ratio:.1%} below {MIN_TVG_RATIO:.0%}")

    status = PLAYLISTS / "status.json"
    if status.exists():
        payload = json.loads(status.read_text(encoding="utf-8"))
        kept = (payload.get("live") or {}).get("kept") or 0
        if kept and kept < 1000:
            fail(f"live kept too low: {kept}")

    print(
        f"ok: {len(country_files)} countries, {len(category_files)} categories, "
        f"{channels} entries, logos {logo_ratio:.1%}, tvg-id {tvg_ratio:.1%}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
