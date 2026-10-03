#!/usr/bin/env python3
"""Gate composed M3Us after the maintenance pipeline runs."""

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


def check_file(path: Path) -> tuple[int, int, int, list[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    rel = str(path.relative_to(ROOT))
    errors: list[str] = []
    if not text.lstrip().startswith("#EXTM3U"):
        errors.append(f"{rel}: missing #EXTM3U")
        return 0, 0, 0, errors
    channels = logos = tvg = 0
    for line in text.splitlines():
        if not line.startswith("#EXTINF:"):
            continue
        channels += 1
        title = line.split(",", 1)[-1] if "," in line else line
        lower = title.lower()
        for token in JUNK:
            if token in lower:
                errors.append(f"{rel}: junk title {title!r}")
                break
        if 'tvg-logo="https://' in line:
            logos += 1
        if 'tvg-id="' in line and 'tvg-id=""' not in line:
            tvg += 1
    return channels, logos, tvg, errors


def evaluate() -> dict:
    errors: list[str] = []
    country_dir = PLAYLISTS / "countries"
    category_dir = PLAYLISTS / "categories"
    if not country_dir.is_dir():
        return {
            "ok": False,
            "errors": ["missing playlists/countries"],
            "countries": 0,
            "categories": 0,
            "channels": 0,
            "logo_ratio": 0.0,
            "tvg_ratio": 0.0,
            "summary": "missing playlists/countries",
        }

    country_files = sorted(country_dir.glob("*.m3u"))
    category_files = sorted(category_dir.glob("*.m3u")) if category_dir.is_dir() else []
    if len(country_files) < MIN_COUNTRIES:
        errors.append(f"too few country playlists: {len(country_files)}")
    if len(category_files) < MIN_CATEGORIES:
        errors.append(f"too few category playlists: {len(category_files)}")

    files = list(country_files) + list(category_files)
    agg_dir = PLAYLISTS / "aggregators"
    if agg_dir.is_dir():
        files.extend(sorted(agg_dir.glob("*.m3u")))
    for extra in (ROOT / "japan.m3u", ROOT / "world.m3u"):
        if extra.exists():
            files.append(extra)

    channels = logos = tvg = 0
    for path in files:
        file_channels, file_logos, file_tvg, file_errors = check_file(path)
        channels += file_channels
        logos += file_logos
        tvg += file_tvg
        errors.extend(file_errors[:5])

    logo_ratio = (logos / channels) if channels else 0.0
    tvg_ratio = (tvg / channels) if channels else 0.0
    if channels < MIN_CHANNELS:
        errors.append(f"too few channels: {channels}")
    if logo_ratio < MIN_LOGO_RATIO:
        errors.append(f"logo coverage {logo_ratio:.1%} below {MIN_LOGO_RATIO:.0%}")
    if tvg_ratio < MIN_TVG_RATIO:
        errors.append(f"tvg-id coverage {tvg_ratio:.1%} below {MIN_TVG_RATIO:.0%}")

    status = PLAYLISTS / "status.json"
    if status.exists():
        payload = json.loads(status.read_text(encoding="utf-8"))
        kept = (payload.get("live") or {}).get("kept") or 0
        if kept and kept < 1000:
            errors.append(f"live kept too low: {kept}")

    summary = (
        f"{len(country_files)} countries, {len(category_files)} categories, "
        f"{channels} entries, logos {logo_ratio:.1%}, tvg-id {tvg_ratio:.1%}"
    )
    return {
        "ok": not errors,
        "errors": errors,
        "countries": len(country_files),
        "categories": len(category_files),
        "channels": channels,
        "logo_ratio": round(logo_ratio, 4),
        "tvg_ratio": round(tvg_ratio, 4),
        "summary": ("ok: " if not errors else "fail: ") + summary,
    }


def main() -> int:
    report = evaluate()
    if not report["ok"]:
        for message in report["errors"]:
            print(message, file=sys.stderr)
        return 1
    print(report["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
