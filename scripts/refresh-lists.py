#!/usr/bin/env python3
"""Build curated playlists and lists.json from public GitHub indexes."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import enrich  # noqa: E402
import harvest  # noqa: E402
import m3u  # noqa: E402

OUT = ROOT / "lists.json"
PLAYLISTS = ROOT / "playlists"
SITE = os.environ.get("TAMATV_SITE", "https://ezhu331.github.io/tamatv").rstrip("/")
CHANNELS_API = "https://iptv-org.github.io/api/channels.json"
IPTV_INDEX = "https://iptv-org.github.io/iptv/index.m3u"

COUNTRIES_API = "https://iptv-org.github.io/api/countries.json"
CATEGORIES_API = "https://iptv-org.github.io/api/categories.json"
NGO5_README = "https://raw.githubusercontent.com/ngo5/IPTV/main/README.md"
IPTV_ORG = "https://github.com/iptv-org/iptv"
IPTV_ORG_SITE = "https://iptv-org.github.io/iptv"
TAMATV_JAPAN_M3U = "https://ezhu331.github.io/tamatv/japan.m3u"
TAMATV_WORLD_M3U = "https://ezhu331.github.io/tamatv/world.m3u"
JAPANTEREBI_EPG = "https://animenosekai.github.io/japanterebi-xmltv/guide.xml"
WORLD_EPG = "https://i.mjh.nz/SamsungTVPlus/us.xml.gz"
JAPANTEREBI_HREF = "https://github.com/Animenosekai/japanterebi-xmltv"
TAMATV_HREF = "https://github.com/EZHU331/tamatv"

CODE_RE = re.compile(r"^[A-Z]{2}$")
CAT_RE = re.compile(r"^[a-z][a-z0-9-]{0,40}$")
SKIP_CATEGORIES = {"xxx"}
SKIP_SECTIONS = ("点播源", "推荐软件", "GitHub镜像", "官方电视直播", "第三方电视直播")
COUNTRY_GROUP_ALIASES = {
    "usa",
    "u.s.a",
    "u.s.a.",
    "america",
    "uk",
    "great britain",
    "england",
    "britain",
    "korea",
    "south korea",
    "north korea",
    "holland",
    "the netherlands",
    "uae",
    "czechia",
    "czech republic",
    "russia",
    "viet nam",
    "vietnam",
}

HOST_ALLOW = {
    "iptv-org.github.io",
    "raw.githubusercontent.com",
    "github.com",
    "live.zbds.top",
    "live.zbds.org",
    "live.fanmingming.cn",
    "live.fanmingming.com",
    "tv.iill.top",
    "m3u.ibert.me",
    "epg.112114.xyz",
    "e.erw.cc",
    "yang-1989.eu.org",
    "i.mjh.nz",
    "epgshare01.online",
    "animenosekai.github.io",
    "epg.aptv.app",
}

ORIGIN_HREF = {
    "vbskycn": "https://github.com/vbskycn/iptv",
    "guovin": "https://github.com/Guovin/iptv-api",
    "fanmingming": "https://github.com/fanmingming/live",
    "yuechan": "https://github.com/YueChan/Live",
    "kimentanm": "https://github.com/Kimentanm/aptv",
    "burningc4": "https://github.com/BurningC4/Chinese-IPTV",
    "zwc456baby": "https://github.com/zwc456baby/iptv_alive",
    "hujingguang": "https://github.com/hujingguang/ChinaIPTV",
    "chinaiptv": "https://github.com/hujingguang/ChinaIPTV",
    "suxuang": "https://github.com/suxuang/myIPTV",
    "myiptv": "https://github.com/suxuang/myIPTV",
    "iptvsources": "https://m3u.ibert.me/",
    "yang1989": "https://yang-1989.eu.org/",
    "112114": "https://epg.112114.xyz/",
    "erw": "https://e.erw.cc/",
    "tamatv": TAMATV_HREF,
    "japanterebi": JAPANTEREBI_HREF,
    "freetv": "https://github.com/Free-TV/IPTV",
    "imjhnz": "https://i.mjh.nz/",
    "buddychewchew": "https://github.com/BuddyChewChew/app-m3u-generator",
}
GITHUB_REPO = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$")

CURATED_VARIANTS = [
    {
        "origin": "vbskycn",
        "name": "vbskycn",
        "country": "CN",
        "variants": [
            {
                "label": "IPv4",
                "url": "https://live.zbds.top/tv/iptv4.m3u",
                "stack": "v4",
                "format": "M3U",
                "epg": True,
                "logos": True,
                "extras": [
                    {"key": "txt", "url": "https://live.zbds.top/tv/iptv4.txt"},
                    {
                        "key": "mirror",
                        "url": "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.m3u",
                    },
                ],
            },
            {
                "label": "IPv6",
                "url": "https://live.zbds.top/tv/iptv6.m3u",
                "stack": "v6",
                "format": "M3U",
                "epg": True,
                "logos": True,
                "extras": [
                    {"key": "txt", "url": "https://live.zbds.top/tv/iptv6.txt"},
                    {
                        "key": "mirror",
                        "url": "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv6.m3u",
                    },
                ],
            },
        ],
    }
]


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "tamatv-lists-refresh/1.0", "Accept": "application/json, text/plain"},
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        if resp.status != 200:
            raise RuntimeError(f"{url} -> {resp.status}")
        return resp.read().decode("utf-8")


def safe_https(url: str) -> str | None:
    cleaned = url.strip().split()[0].strip(".,;)\">'")
    try:
        parsed = urlparse(cleaned)
    except Exception:
        return None
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").lower()
    if host not in HOST_ALLOW:
        return None
    if ".." in parsed.path:
        return None
    return parsed.geturl()


def safe_origin_href(url: str | None, fallback_name: str) -> str:
    known = ORIGIN_HREF.get(origin_key(fallback_name))
    if known:
        return known
    if not url:
        return IPTV_ORG
    clean = safe_https(url)
    if clean and GITHUB_REPO.match(clean.rstrip("/")):
        return clean.rstrip("/")
    if clean and urlparse_host(clean) in HOST_ALLOW:
        return clean
    return IPTV_ORG


def urlparse_host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def load_json(url: str):
    return json.loads(fetch(url))


def country_name_set(country_rows: list[dict]) -> set[str]:
    names = {row["name"].lower() for row in country_rows}
    names |= {row["code"].lower() for row in country_rows}
    names |= COUNTRY_GROUP_ALIASES
    return names


def countries():
    rows = []
    for item in load_json(COUNTRIES_API):
        code = str(item.get("code") or "").upper()
        name = str(item.get("name") or "").strip()
        flag = str(item.get("flag") or "").strip()
        if not CODE_RE.match(code) or not name:
            continue
        slug = code.lower()
        url = safe_https(f"{IPTV_ORG_SITE}/countries/{slug}.m3u")
        if not url:
            continue
        rows.append(
            {
                "id": f"country-{slug}",
                "kind": "country",
                "code": code,
                "name": name,
                "flag": flag[:4],
                "letter": name[0].upper() if name[0].isascii() else "#",
                "url": url,
                "format": "M3U",
                "origin": "iptv-org",
                "originHref": IPTV_ORG,
            }
        )
    rows.sort(key=lambda r: (r["letter"], r["name"]))
    return rows


def categories():
    rows = []
    for item in load_json(CATEGORIES_API):
        cat_id = str(item.get("id") or "").lower()
        name = str(item.get("name") or "").strip()
        if cat_id in SKIP_CATEGORIES or not CAT_RE.match(cat_id) or not name:
            continue
        if cat_id == "undefined":
            name = "Other"
        url = safe_https(f"{IPTV_ORG_SITE}/categories/{cat_id}.m3u")
        if not url:
            continue
        rows.append(
            {
                "id": f"cat-{cat_id}",
                "kind": "category",
                "code": cat_id,
                "name": name,
                "url": url,
                "format": "M3U",
                "origin": "iptv-org",
                "originHref": IPTV_ORG,
            }
        )
    rows.sort(key=lambda r: r["name"].lower())
    return rows


def origin_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def parse_ngo5_readme(text: str) -> tuple[list[dict], list[dict]]:
    live_rows: list[dict] = []
    epg_rows: list[dict] = []
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            if title in SKIP_SECTIONS:
                section = "skip"
            elif "直播源" in title:
                section = "live"
            elif title == "EPG":
                section = "epg"
            else:
                section = section if section == "epg" and title.startswith("[") else section
            continue
        if section == "skip":
            continue
        if line.startswith("~~") or "|~~" in line:
            continue
        urls = re.findall(r"https://[^\s)|]+", line)
        if not urls:
            continue
        if section == "epg":
            for url in urls:
                clean = safe_https(url.rstrip(".,;"))
                if not clean or not re.search(r"\.(xml|xmlgz)(\.gz)?$", clean, re.I) and "xml" not in clean:
                    if clean and ("/e.xml" in clean or "/pp.xml" in clean or clean.endswith(".xml")):
                        pass
                    else:
                        continue
                if not clean:
                    continue
                name = "EPG"
                if "112114" in clean:
                    name = "112114"
                elif "fanmingming" in clean:
                    name = "fanmingming"
                elif "erw.cc" in clean:
                    name = "ERW"
                epg_rows.append(
                    {
                        "id": f"epg-{origin_key(name)}",
                        "kind": "guide",
                        "name": name,
                        "url": clean,
                        "format": "XMLTV",
                        "origin": name,
                        "originHref": safe_origin_href(clean if name == "ERW" or name == "112114" else None, name),
                    }
                )
            continue
        if section != "live":
            continue
        if "|" not in line or line.startswith("|名称") or line.startswith("| ---") or line.startswith("| ----"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        name_cell = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cells[0]).strip()
        url = safe_https(cells[1].split()[0].rstrip(".,;"))
        if not name_cell or not url:
            continue
        if not re.search(r"\.(m3u8?|txt)(\?|$)", url, re.I) and "/m3u/" not in url and url.endswith("Gather"):
            pass
        elif not re.search(r"\.(m3u8?|txt)(\?|$)", url, re.I) and "/m3u/" not in url and "/tv/" not in url:
            if "Gather" not in url:
                continue
        stack = "v6" if "IPV6" in line.upper() or "IPv6" in line else "v4"
        fmt = "M3U8" if url.lower().endswith(".m3u8") else ("TXT" if url.lower().endswith(".txt") else "M3U")
        href_match = re.search(r"\((https://[^)\s]+)", cells[0])
        parsed_href = href_match.group(1) if href_match else None
        live_rows.append(
            {
                "origin": name_cell,
                "originHref": safe_origin_href(parsed_href, name_cell),
                "url": url,
                "stack": stack,
                "format": fmt,
                "epg": "✔️" in line,
                "logos": line.count("✔️") >= 2,
                "country": "CN",
            }
        )
    return live_rows, epg_rows


def merge_aggregators(scraped: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    seen_urls: set[str] = set()

    def add(origin: str, href: str, country: str, variant: dict):
        url = safe_https(variant["url"])
        if not url or url in seen_urls:
            return
        seen_urls.add(url)
        extras = []
        for extra in variant.get("extras") or []:
            extra_url = safe_https(extra.get("url", ""))
            if extra_url and extra_url not in seen_urls:
                seen_urls.add(extra_url)
                extras.append({"key": extra["key"], "url": extra_url})
        key = origin_key(origin)
        group = groups.setdefault(
            key,
            {
                "id": f"agg-{key}",
                "kind": "aggregator",
                "name": origin,
                "country": country,
                "origin": origin,
                "originHref": safe_origin_href(href, origin),
                "variants": [],
            },
        )
        label = variant.get("label") or ("IPv6" if variant.get("stack") == "v6" else "IPv4")
        stack = variant.get("stack") or "v4"
        existing = next((v for v in group["variants"] if v["stack"] == stack), None)
        if existing:
            if url != existing["url"]:
                existing["extras"].append({"key": "mirror", "url": url})
            for extra in extras:
                if extra["url"] not in {existing["url"], *(e["url"] for e in existing["extras"])}:
                    existing["extras"].append(extra)
            return
        group["variants"].append(
            {
                "label": label,
                "url": url,
                "stack": stack,
                "format": variant.get("format") or "M3U",
                "epg": bool(variant.get("epg")),
                "logos": bool(variant.get("logos")),
                "extras": extras,
            }
        )

    for curated in CURATED_VARIANTS:
        for variant in curated["variants"]:
            add(curated["origin"], ORIGIN_HREF[origin_key(curated["origin"])], curated["country"], variant)
    for row in scraped:
        label = "IPv6" if row["stack"] == "v6" else "IPv4"
        add(row["origin"], row["originHref"], row.get("country") or "CN", {**row, "label": label})

    out = list(groups.values())
    out.sort(key=lambda g: g["name"].lower())
    return out


def dedupe_guides(rows: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    seen = set()
    for row in rows:
        url = safe_https(row["url"])
        if not url or url in seen:
            continue
        seen.add(url)
        key = origin_key(row["name"])
        group = groups.get(key)
        if group:
            group.setdefault("extras", []).append({"key": "mirror", "url": url})
            continue
        groups[key] = {
            "id": f"epg-{key}",
            "kind": "guide",
            "name": row["name"],
            "url": url,
            "format": "XMLTV",
            "origin": row["name"],
            "originHref": safe_origin_href(row.get("originHref"), row["name"]),
            "extras": [],
        }
    return list(groups.values())


def hosted(rel: str) -> str:
    return f"{SITE}/{rel.lstrip('/')}"


def reset_playlist_dirs() -> None:
    for name in ("countries", "categories", "aggregators"):
        path = PLAYLISTS / name
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def write_playlist(rel: str, entries: list[m3u.Entry], epg: str = "") -> str:
    path = PLAYLISTS / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(m3u.write_m3u(entries, epg=epg), encoding="utf-8")
    return hosted(f"playlists/{rel}")


def epg_extras(urls: list[str]) -> list[dict]:
    extras = []
    seen: set[str] = set()
    for url in urls:
        clean = safe_https(url)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        extras.append({"key": "epg", "url": clean})
    return extras


def pair_row(row: dict, items: list[m3u.Entry], rel: str, epgshare: dict[str, str], country: str = "") -> dict:
    items = list(items)
    china = country in enrich.CN_CODES
    items.sort(key=lambda item: m3u.sort_key(item, china=china))
    guides = enrich.epg_for_entries(items, epgshare, country=country)
    next_row = dict(row)
    next_row["url"] = write_playlist(rel, items, epg=enrich.join_epg(guides))
    next_row["channels"] = len(items)
    next_row["format"] = "M3U"
    extras = list(next_row.get("extras") or [])
    extras.extend(epg_extras(guides))
    next_row["extras"] = extras
    return next_row


def build_live(
    country_rows: list[dict],
    category_rows: list[dict],
    probe: bool,
    channels: dict[str, dict],
    logos: dict[str, list[dict]],
) -> tuple[list[dict], list[dict], dict[str, str], dict]:
    country_names = country_name_set(country_rows)
    sources = harvest.collect()
    raw: list[m3u.Entry] = []
    header_guides: list[str] = []
    for src in sources:
        parsed = m3u.parse_playlist(src.text)
        raw.extend(parsed)
        header_guides.extend(harvest.header_epg_urls(src.text))
        print(f"  {src.origin}: {len(parsed)} from {src.url}", flush=True)
    epgshare = enrich.parse_epgshare_map(header_guides)
    attached = enrich.attach(raw, channels, logos, country_names)
    curated = m3u.curate(attached, china="auto", country_names=country_names)
    if probe:
        curated, probe_counts = m3u.probe_entries(curated)
    else:
        probe_counts = {"ok": 0, "dead": 0, "unknown": 0, "skipped": len(curated)}

    by_country: dict[str, list[m3u.Entry]] = {}
    by_category: dict[str, list[m3u.Entry]] = {}
    for entry in curated:
        if entry.country:
            by_country.setdefault(entry.country, []).append(entry)
        cat_key = "undefined" if entry.group == "Other" else entry.group.lower()
        by_category.setdefault(cat_key, []).append(entry)

    out_countries = []
    for row in country_rows:
        items = by_country.get(row["code"], [])
        if not items:
            continue
        out_countries.append(
            pair_row(row, items, f"countries/{row['code'].lower()}.m3u", epgshare, country=row["code"])
        )

    out_categories = []
    for row in category_rows:
        items = by_category.get(row["code"], [])
        if not items:
            continue
        out_categories.append(pair_row(row, items, f"categories/{row['code']}.m3u", epgshare))

    extra = by_category.get("undefined") or by_category.get("other") or []
    if extra and not any(row["code"] == "undefined" for row in out_categories):
        out_categories.append(
            pair_row(
                {
                    "id": "cat-undefined",
                    "kind": "category",
                    "code": "undefined",
                    "name": "Other",
                    "format": "M3U",
                    "origin": "iptv-org",
                    "originHref": IPTV_ORG,
                },
                extra,
                "categories/undefined.m3u",
                epgshare,
            )
        )
        out_categories.sort(key=lambda row: row["name"].lower())

    return (
        out_countries,
        out_categories,
        epgshare,
        {
            "playlists": len(sources),
            "source": len(raw),
            "kept": len(curated),
            "countries": len(out_countries),
            "categories": len(out_categories),
            "probe": probe_counts,
            "quality": m3u.quality_stats(curated),
        },
    )


def build_aggregators(
    aggregators: list[dict],
    probe: bool,
    channels: dict[str, dict],
    logos: dict[str, list[dict]],
    country_names: set[str] | None = None,
) -> tuple[list[dict], dict]:
    out = []
    totals = {
        "source": 0,
        "kept": 0,
        "lists": 0,
        "probe": {"ok": 0, "dead": 0, "unknown": 0, "skipped": 0},
    }
    for group in aggregators:
        variants = []
        for variant in group.get("variants") or []:
            source = variant.get("url")
            if not source:
                continue
            try:
                text = fetch(source)
            except Exception as err:
                print(f"skip {group.get('name')} {variant.get('label')}: {err}", file=sys.stderr)
                continue
            parsed = enrich.attach(m3u.parse_playlist(text), channels, logos, country_names)
            totals["source"] += len(parsed)
            curated = m3u.curate(parsed, china=True, country_names=country_names)
            stack = variant.get("stack") or "v4"
            if probe and stack != "v6":
                curated, counts = m3u.probe_entries(curated, china=True)
                for key, value in counts.items():
                    totals["probe"][key] = totals["probe"].get(key, 0) + value
            else:
                totals["probe"]["skipped"] += len(curated)
            if not curated:
                continue
            totals["kept"] += len(curated)
            for key, value in m3u.quality_stats(curated).items():
                totals.setdefault("quality", {})
                totals["quality"][key] = totals["quality"].get(key, 0) + value
            slug = origin_key(group["name"])
            guides = harvest.header_epg_urls(text) or [enrich.FANMINGMING_EPG, enrich.GUIDE_112114]
            variants.append(
                {
                    "label": variant.get("label") or ("IPv6" if stack == "v6" else "IPv4"),
                    "url": write_playlist(
                        f"aggregators/{slug}-{stack}.m3u", curated, epg=enrich.join_epg(guides[:2])
                    ),
                    "stack": stack,
                    "format": "M3U",
                    "epg": True,
                    "logos": any(item.logo.startswith("https://") for item in curated),
                    "channels": len(curated),
                    "extras": epg_extras(guides[:2]),
                }
            )
        if not variants:
            continue
        row = dict(group)
        row["variants"] = variants
        out.append(row)
        totals["lists"] += 1
    return out, totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build curated tamaTV playlists")
    parser.add_argument("--probe", action="store_true", help="Check harvested and aggregator stream URLs")
    parser.add_argument("--probe-all", action="store_true", help="Same as --probe")
    parser.add_argument("--catalog-only", action="store_true", help="Write lists.json without rewriting playlists")
    args = parser.parse_args(argv)

    country_rows = countries()
    category_rows = categories()
    scraped_live, scraped_epg = parse_ngo5_readme(fetch(NGO5_README))
    aggregators = merge_aggregators(scraped_live)
    guides = dedupe_guides(scraped_epg)
    stats: dict = {}

    if not args.catalog_only:
        reset_playlist_dirs()
        print("loading channel logos and guides", flush=True)
        channels = enrich.load_channels()
        logos = enrich.load_logos()
        country_names = country_name_set(country_rows)
        country_rows, category_rows, epgshare, live_stats = build_live(
            country_rows, category_rows, args.probe or args.probe_all, channels, logos
        )
        aggregators, agg_stats = build_aggregators(
            aggregators,
            args.probe or args.probe_all,
            channels,
            logos,
            country_names,
        )
        stats = {"live": live_stats, "aggregators": agg_stats, "epgshare": len(epgshare)}
    else:
        epgshare = {}

    def load_composer(name: str):
        spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name.replace('_', '-')}.py")
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(mod)
        return mod

    compose_japan = load_composer("compose_japan")
    compose_world = load_composer("compose_world")
    compose_japan.write_playlists()
    compose_world.write_playlists()
    japan_count = len(compose_japan.CHANNELS)
    world_count = len(compose_world.CHANNELS)
    for row in country_rows:
        if row.get("code") == "JP":
            row["channels"] = japan_count
            extras = [{"key": "epg", "url": JAPANTEREBI_EPG}]
            row["extras"] = extras
            break
    if not any(g.get("id") == "epg-japanterebi" for g in guides):
        guides.insert(
            0,
            {
                "id": "epg-japanterebi",
                "kind": "guide",
                "name": "japanterebi",
                "url": JAPANTEREBI_EPG,
                "format": "XMLTV",
                "origin": "japanterebi",
                "originHref": JAPANTEREBI_HREF,
                "extras": [],
            },
        )
    featured = [
        {
            "id": "tamatv-world",
            "kind": "featured",
            "name": "World news & documentary",
            "flag": "🌍",
            "url": TAMATV_WORLD_M3U,
            "format": "M3U",
            "origin": "tamaTV",
            "originHref": TAMATV_HREF,
            "channels": world_count,
            "extras": epg_extras(
                [
                    JAPANTEREBI_EPG,
                    "https://epgshare01.online/epgshare01/epg_ripper_ALJAZEERA1.xml.gz",
                    "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
                ]
            ),
        },
        {
            "id": "tamatv-japan",
            "kind": "featured",
            "name": "Japan",
            "flag": "🇯🇵",
            "url": TAMATV_JAPAN_M3U,
            "format": "M3U",
            "origin": "tamaTV",
            "originHref": TAMATV_HREF,
            "channels": japan_count,
            "extras": [{"key": "epg", "url": JAPANTEREBI_EPG}],
        },
    ]

    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "site": SITE,
        "sources": [
            {"name": "tamaTV World", "href": TAMATV_HREF},
            {"name": "tamaTV Japan", "href": TAMATV_HREF},
            {"name": "iptv-org/iptv", "href": IPTV_ORG},
            {"name": "Free-TV/IPTV", "href": "https://github.com/Free-TV/IPTV"},
            {"name": "ngo5/IPTV", "href": "https://github.com/ngo5/IPTV"},
            {"name": "vbskycn/iptv", "href": "https://github.com/vbskycn/iptv"},
            {"name": "i.mjh.nz", "href": "https://i.mjh.nz/"},
        ],
        "featured": featured,
        "countries": country_rows,
        "categories": category_rows,
        "aggregators": aggregators,
        "guides": guides,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if stats:
        PLAYLISTS.mkdir(parents=True, exist_ok=True)
        (PLAYLISTS / "status.json").write_text(
            json.dumps({"updated": payload["updated"], **stats}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        f"Wrote {OUT.name}: {len(country_rows)} countries, "
        f"{len(category_rows)} categories, {len(aggregators)} aggregators, {len(guides)} guides"
    )
    if stats:
        print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
