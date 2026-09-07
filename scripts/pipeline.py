#!/usr/bin/env python3
"""Single maintenance pipeline for public live lists.

Stages, in order:
  ingest   harvest public M3U/TXT indexes
  inspect  census junk, VOD, missing logos/ids, country-as-group
  enhance  match iptv-org metadata and upgrade logos/names
  pair     fill tvg-id, tvg-country, XMLTV guide URLs
  fix      drop junk/VOD/adult/labeled streams under 720p; clean names; pick best URL
  group    classify country + category (China 央视/卫视 in country lists)
  probe    optional liveness check; drop confirmed-dead streams
  compose  write country/category/aggregator M3Us and lists.json
  gate     fail the run if coverage or junk floors regress
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_playlists  # noqa: E402
import enrich  # noqa: E402
import m3u  # noqa: E402

PLAYLISTS = ROOT / "playlists"
STAGES = [
    "ingest",
    "inspect",
    "enhance",
    "pair",
    "fix",
    "group",
    "probe",
    "compose",
    "gate",
]


def add_counts(dst: dict, src: dict) -> dict:
    for key, value in src.items():
        if isinstance(value, dict):
            dst[key] = add_counts(dst.get(key) or {}, value)
        elif isinstance(value, (int, float)):
            dst[key] = dst.get(key, 0) + value
        else:
            dst[key] = value
    return dst


def process_entries(
    raw: list[m3u.Entry],
    channels: dict[str, dict],
    logos: dict[str, list[dict]],
    country_names: set[str] | None = None,
    *,
    china: bool | str = "auto",
    probe: bool = False,
    probe_china: bool = False,
) -> tuple[list[m3u.Entry], dict]:
    countries = country_names or set()
    inspect_in = m3u.inspect_entries(raw, countries)
    enhance_stats: dict[str, int] = {}
    enhanced = enrich.attach(raw, channels, logos, countries, stats=enhance_stats)
    fix_stats: dict[str, int] = {}
    curated = m3u.curate(enhanced, china=china, country_names=countries, stats=fix_stats)
    if probe:
        curated, probe_counts = m3u.probe_entries(curated, china=probe_china)
        fix_stats["dropped_dead"] = probe_counts.get("dead", 0)
    else:
        probe_counts = {"ok": 0, "dead": 0, "unknown": 0, "skipped": len(curated)}
        fix_stats["dropped_dead"] = 0
    report = {
        "inspect": inspect_in,
        "enhance": enhance_stats,
        "fix": fix_stats,
        "probe": probe_counts,
        "result": m3u.inspect_entries(curated, countries),
        "quality": m3u.quality_stats(curated),
        "source": len(raw),
        "kept": len(curated),
    }
    print(
        f"pipeline inspect {inspect_in['channels']} -> enhance {enhance_stats.get('kept', 0)} "
        f"matched {enhance_stats.get('matched', 0)} logos+{enhance_stats.get('logos_upgraded', 0)} "
        f"-> fix kept {fix_stats.get('kept', 0)} "
        f"(junk {fix_stats.get('dropped_junk', 0)}, vod {fix_stats.get('dropped_adult_or_vod', 0)}, "
        f"low {fix_stats.get('dropped_low_quality', 0)}, merged {fix_stats.get('merged', 0)})",
        flush=True,
    )
    return curated, report


def load_refresh():
    spec = importlib.util.spec_from_file_location("refresh_lists", SCRIPTS / "refresh-lists.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def write_status(extra: dict) -> None:
    path = PLAYLISTS / "status.json"
    payload: dict = {}
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    payload["pipeline"] = STAGES
    payload.update(extra)
    PLAYLISTS.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maintain tamaTV live lists")
    parser.add_argument("--probe", action="store_true", help="Drop confirmed-dead stream URLs")
    parser.add_argument("--probe-all", action="store_true", help="Same as --probe")
    parser.add_argument("--catalog-only", action="store_true", help="Rewrite lists.json only")
    parser.add_argument("--check-only", action="store_true", help="Run the quality gate on existing files")
    args = parser.parse_args(argv)

    if args.check_only:
        gate = check_playlists.evaluate()
        write_status({"gate": gate})
        if not gate["ok"]:
            for message in gate["errors"]:
                print(message, file=sys.stderr)
            return 1
        print(gate["summary"])
        return 0

    forwarded = []
    if args.probe or args.probe_all:
        forwarded.append("--probe")
    if args.catalog_only:
        forwarded.append("--catalog-only")
    refresh = load_refresh()
    code = refresh.main(forwarded)
    if code:
        return code

    gate = check_playlists.evaluate()
    write_status({"gate": gate})
    if not gate["ok"]:
        for message in gate["errors"]:
            print(message, file=sys.stderr)
        return 1
    print("pipeline gate", gate["summary"])
    return 0


if __name__ == "__main__":
    sys.modules.setdefault("pipeline", sys.modules[__name__])
    raise SystemExit(main())
