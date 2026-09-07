#!/usr/bin/env python3
"""Parse, curate, and write M3U playlists."""

from __future__ import annotations

import ipaddress
import re
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from urllib.parse import urlparse

import urlcheck

USER_AGENT = "tamatv-playlist/1.0"
FETCH_TIMEOUT = 45
PROBE_TIMEOUT = 6
PROBE_WORKERS = 32
READ_BYTES = 2048

ATTR_RE = re.compile(r'([A-Za-z0-9-]+)="([^"]*)"')
QUALITY_RE = re.compile(
    r"(?:\((\d{3,4})p\)|\[(\d{3,4})p\]|\b(\d{3,4})p\b|\b(4k|8k|uhd|fhd|hd|sd)\b|(超清|蓝光|高清|标清|流畅|普清))",
    re.I,
)
NAME_STRIP_RE = re.compile(
    r"\s*(?:\((\d{3,4})p\)|\[(\d{3,4})[pP]\]|\[(?:HD|FHD|SD|4K|UHD|IPV6|IPv4|Geo-blocked|Not 24/7)\]|[ⓈⓉⓎ🅖]|超清|蓝光|高清|标清|流畅|普清)+\s*",
    re.I,
)
PAGE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "twitch.tv",
    "www.twitch.tv",
    "m.twitch.tv",
}
VOD_EXT = {".mp4", ".mkv", ".avi", ".mpg", ".wmv", ".flv"}
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
TVG_COUNTRY_RE = re.compile(r"\.([A-Za-z]{2})(?:@|$)")

HEIGHT = {
    "8k": 4320,
    "4k": 2160,
    "uhd": 2160,
    "fhd": 1080,
    "hd": 720,
    "sd": 480,
    "超清": 1080,
    "蓝光": 1080,
    "高清": 720,
    "标清": 480,
    "普清": 480,
    "流畅": 360,
}

CATEGORY_ORDER = [
    "News",
    "Sports",
    "Movies",
    "Series",
    "Entertainment",
    "Kids",
    "Animation",
    "Documentary",
    "Science",
    "Education",
    "Culture",
    "Music",
    "Lifestyle",
    "Cooking",
    "Travel",
    "Outdoor",
    "Auto",
    "Business",
    "Weather",
    "Legislative",
    "Religious",
    "Classic",
    "Comedy",
    "Family",
    "Relax",
    "Shop",
    "Public",
    "General",
    "Other",
]
CATEGORY_RANK = {name.lower(): i for i, name in enumerate(CATEGORY_ORDER)}
CATEGORY_CANON = {name.lower(): name for name in CATEGORY_ORDER}
CATEGORY_CANON.update(
    {
        "undefined": "Other",
        "interactive": "General",
        "xxx": "",
        "adult": "",
        "tv & entertainment": "Entertainment",
        "tv and entertainment": "Entertainment",
        "kids & family": "Kids",
        "news (es)": "News",
        "news (en)": "News",
        "news (fr)": "News",
        "sports (en)": "Sports",
        "movies & series": "Movies",
        "series & movies": "Series",
        "tv": "General",
    }
)

CN_GROUP_ORDER = ["央视", "卫视", "港澳台", "地方", "新闻", "体育", "少儿", "电影", "纪录", "国际", "其他"]
CN_GROUP_RANK = {name: i for i, name in enumerate(CN_GROUP_ORDER)}
CN_TO_CATEGORY = {
    "新闻": "News",
    "体育": "Sports",
    "少儿": "Kids",
    "电影": "Movies",
    "纪录": "Documentary",
    "国际": "General",
    "央视": "General",
    "卫视": "General",
    "港澳台": "General",
    "地方": "General",
    "其他": "Other",
}
CN_GROUP_RULES = (
    (re.compile(r"央视|cctv", re.I), "央视"),
    (re.compile(r"卫视|卫视频道"), "卫视"),
    (re.compile(r"港澳台|香港|台湾|澳门|凤凰"), "港澳台"),
    (re.compile(r"少儿|儿童|动漫|卡通"), "少儿"),
    (re.compile(r"体育|足球|NBA", re.I), "体育"),
    (re.compile(r"电影|影视|院线"), "电影"),
    (re.compile(r"纪录"), "纪录"),
    (re.compile(r"新闻"), "新闻"),
    (re.compile(r"国际|海外|外语"), "国际"),
    (re.compile(r"地方|省市"), "地方"),
)

ADULT_RE = re.compile(r"(?:^|[;/\s])(?:xxx|adult|成人|色情)(?:$|[;/\s])", re.I)
BAD_TITLE_RE = re.compile(r"(成人|色情|xxx)", re.I)
SKIP_GROUP_RE = re.compile(r"(?:\bvod\b|点播|catch.?up|replay)", re.I)
JUNK_NAME_RE = re.compile(
    r"chrome/|safari/|mozilla/|like gecko|user-agent|group-title=|http-user-agent|"
    r"^(?:\d{4}[-./年]\d{1,2}[-./月]\d{1,2}|更新|公告|测试|请阅读|telegram|http)",
    re.I,
)


@dataclass
class Entry:
    name: str
    url: str
    tvg_id: str = ""
    tvg_name: str = ""
    logo: str = ""
    group: str = ""
    user_agent: str = ""
    referrer: str = ""
    extras: list[str] = field(default_factory=list)
    height: int = 0
    country: str = ""
    channel_id: str = ""

    @property
    def display_name(self) -> str:
        base = clean_name(self.name)
        if self.height >= 720:
            return f"{base} ({self.height}p)"
        return base


def ssl_ctx(insecure: bool = False) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_bytes(url: str, timeout: int = FETCH_TIMEOUT, headers: dict | None = None) -> bytes:
    if not urlcheck.is_safe_https_url(url, resolve=True):
        raise RuntimeError(f"blocked fetch {url}")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*", **(headers or {})},
    )
    opener = urlcheck.opener_for(https_only=True)
    with opener.open(req, timeout=timeout) as resp:
        final = resp.geturl()
        if final and not urlcheck.is_safe_https_url(final, resolve=True):
            raise RuntimeError(f"blocked redirect {url} -> {final}")
        if resp.status >= 400:
            raise RuntimeError(f"{url} -> {resp.status}")
        return resp.read()


def fetch_text(url: str, timeout: int = FETCH_TIMEOUT) -> str:
    return fetch_bytes(url, timeout=timeout).decode("utf-8", "replace")


def parse_attrs(line: str) -> dict[str, str]:
    return {k.lower(): v for k, v in ATTR_RE.findall(line)}


def quality_height(text: str) -> int:
    best = 0
    for match in QUALITY_RE.finditer(text or ""):
        token = next((g for g in match.groups() if g), "")
        if token.isdigit():
            best = max(best, int(token))
            continue
        best = max(best, HEIGHT.get(token.lower(), 0))
    return best


def clean_name(name: str) -> str:
    text = NAME_STRIP_RE.sub(" ", name or "")
    return re.sub(r"\s+", " ", text).strip(" -,")


def is_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text or ""))


def channel_key(entry: Entry, china: bool = False) -> str:
    cid = (entry.channel_id or (entry.tvg_id.split("@", 1)[0] if entry.tvg_id else "")).lower()
    if cid and "." in cid and not cid.startswith("mjh-"):
        return "id:" + cid
    name = re.sub(r"\s+", "", clean_name(entry.name) or entry.tvg_name or "").lower()
    country = (entry.country or country_from_tvg(entry.tvg_id) or "").lower()
    if china:
        return "cn:" + name
    if name and country:
        return f"n:{country}:{name}"
    if cid:
        return "id:" + cid
    return "n:" + name


def country_from_tvg(tvg_id: str) -> str:
    match = TVG_COUNTRY_RE.search(tvg_id or "")
    code = match.group(1).upper() if match else ""
    return "UK" if code == "GB" else code


def compact_name(text: str) -> str:
    cleaned = clean_name(text)
    cleaned = cleaned.replace("综合", "").replace("频道", "")
    cleaned = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", cleaned.lower())
    cleaned = re.sub(r"^cctv0*", "cctv", cleaned)
    return cleaned


def is_junk_name(entry: Entry) -> bool:
    blob = f"{entry.name} {entry.tvg_name}"
    return bool(JUNK_NAME_RE.search(clean_name(entry.name)) or JUNK_NAME_RE.search(entry.tvg_name or "") or JUNK_NAME_RE.search(blob))


def is_ipv6_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return ":" in host


def better_entry(entry: Entry, prev: Entry) -> bool:
    return (
        entry.height,
        entry.url.lower().startswith("https://"),
        entry.logo.startswith("https://"),
        bool(entry.tvg_id) and "." in entry.tvg_id and not entry.tvg_id.startswith("mjh-"),
        bool(entry.tvg_name),
        -len(entry.url),
    ) > (
        prev.height,
        prev.url.lower().startswith("https://"),
        prev.logo.startswith("https://"),
        bool(prev.tvg_id) and "." in prev.tvg_id and not prev.tvg_id.startswith("mjh-"),
        bool(prev.tvg_name),
        -len(prev.url),
    )


def merge_best(pool: dict[str, Entry], key: str, entry: Entry) -> None:
    prev = pool.get(key)
    if prev is None or better_entry(entry, prev):
        pool[key] = entry


def alias_key(entry: Entry, china: bool = False) -> str:
    name = compact_name(entry.name) or compact_name(entry.tvg_name)
    country = (entry.country or country_from_tvg(entry.tvg_id) or "").lower()
    if china or uses_china_groups(entry, "auto"):
        return "cn:" + name
    if name and country:
        return f"n:{country}:{name}"
    return channel_key(entry, china=china)


def is_playable_url(url: str) -> bool:
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or urlcheck.host_is_blocked(host) or host in PAGE_HOSTS:
        return False
    path = (parsed.path or "").lower()
    if any(path.endswith(ext) for ext in VOD_EXT):
        return False
    try:
        ip = ipaddress.ip_address(host)
        return urlcheck.ip_is_public(ip)
    except ValueError:
        return True


def primary_category(raw: str, country_names: set[str] | None = None) -> str:
    parts = [p.strip() for p in (raw or "").replace("|", ";").split(";") if p.strip()]
    countries = country_names or set()
    named: list[str] = []
    for part in parts:
        if ADULT_RE.search(part) or SKIP_GROUP_RE.search(part):
            return ""
        lower = part.lower()
        if lower in countries:
            continue
        canon = CATEGORY_CANON.get(lower)
        if canon == "":
            return ""
        if canon:
            named.append(canon)
            continue
        if is_cjk(part):
            named.append(part)
    if not named:
        return "General"
    preferred = [name for name in named if name.lower() not in {"general", "undefined", "other", "entertainment"}]
    pool = preferred or named
    pool.sort(key=lambda name: CATEGORY_RANK.get(name.lower(), len(CATEGORY_ORDER)))
    return pool[0]


def catalog_category(entry: Entry) -> str:
    mapped = CN_TO_CATEGORY.get(entry.group)
    if mapped:
        return mapped
    return entry.group or "General"


def china_group(raw: str, name: str) -> str:
    blob = f"{raw} {name}"
    if ADULT_RE.search(blob) or BAD_TITLE_RE.search(name):
        return ""
    for rule, label in CN_GROUP_RULES:
        if rule.search(raw or "") or rule.search(name or ""):
            return label
    if "cctv" in name.lower() or name.upper().startswith("CCTV"):
        return "央视"
    return "其他" if not (raw or "").strip() else "地方"


def parse_m3u(text: str) -> list[Entry]:
    entries: list[Entry] = []
    current: Entry | None = None
    pending_opts: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF:"):
            if current and current.url:
                entries.append(current)
            meta, _, title = line.partition(",")
            attrs = parse_attrs(meta)
            ua = attrs.get("http-user-agent") or attrs.get("user-agent") or ""
            ref = attrs.get("http-referrer") or attrs.get("referrer") or ""
            name = title.strip() or attrs.get("tvg-name") or ""
            country = (attrs.get("tvg-country") or "").upper()
            if country == "GB":
                country = "UK"
            current = Entry(
                name=name,
                url="",
                tvg_id=attrs.get("tvg-id", ""),
                tvg_name=attrs.get("tvg-name", ""),
                logo=attrs.get("tvg-logo", ""),
                group=attrs.get("group-title", ""),
                user_agent=ua,
                referrer=ref,
                extras=pending_opts,
                height=quality_height(f"{name} {attrs.get('tvg-name', '')}"),
                country=country if len(country) == 2 else "",
            )
            pending_opts = []
            continue
        if line.startswith("#EXTVLCOPT:"):
            value = line.split(":", 1)[1]
            if value.lower().startswith("http-user-agent="):
                ua = value.split("=", 1)[1]
                if current:
                    current.user_agent = current.user_agent or ua
                else:
                    pending_opts.append(line)
            elif value.lower().startswith("http-referrer="):
                ref = value.split("=", 1)[1]
                if current:
                    current.referrer = current.referrer or ref
                else:
                    pending_opts.append(line)
            elif current:
                current.extras.append(line)
            else:
                pending_opts.append(line)
            continue
        if line.startswith("#"):
            continue
        url = line.split()[0]
        if current is None:
            current = Entry(name=url, url="", height=0)
        current.url = url
        if is_playable_url(url):
            entries.append(current)
        current = None
        pending_opts = []
    if current and current.url and is_playable_url(current.url):
        entries.append(current)
    return entries


def parse_txt(text: str) -> list[Entry]:
    entries: list[Entry] = []
    group = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.endswith("#genre#"):
            group = line.rsplit(",", 1)[0].strip() if "," in line else line.replace("#genre#", "").strip()
            continue
        if "," not in line and "#" not in line:
            continue
        name, _, url = line.partition(",")
        url = url.strip().split()[0]
        name = name.strip()
        if not name or not is_playable_url(url):
            continue
        entries.append(
            Entry(name=name, url=url, group=group, tvg_name=name, height=quality_height(f"{name} {group}"))
        )
    return entries


def parse_playlist(text: str) -> list[Entry]:
    if "#EXTINF" in text or text.lstrip().startswith("#EXTM3U"):
        return parse_m3u(text)
    return parse_txt(text)


def sort_key(entry: Entry, china: bool = False) -> tuple:
    group = entry.group or ("其他" if china else "General")
    if china:
        rank = CN_GROUP_RANK.get(group, len(CN_GROUP_ORDER))
    else:
        rank = CATEGORY_RANK.get(group.lower(), len(CATEGORY_ORDER))
    name = clean_name(entry.name)
    parts = []
    for piece in re.split(r"(\d+)", name):
        if not piece:
            continue
        if piece.isdigit():
            parts.append((0, int(piece)))
        else:
            parts.append((1, piece.lower()))
    plus = 0 if "+" in name else 1
    return (rank, group.lower(), tuple(parts), plus, -entry.height, entry.name.lower())


def uses_china_groups(entry: Entry, china: bool | str) -> bool:
    if china is True:
        return True
    if china is False:
        return False
    return is_cjk(entry.name) or is_cjk(entry.group) or entry.country in {"CN", "HK", "TW", "MO"}


def empty_curate_stats() -> dict[str, int]:
    return {
        "input": 0,
        "kept": 0,
        "dropped_unplayable": 0,
        "dropped_junk": 0,
        "dropped_adult_or_vod": 0,
        "dropped_low_quality": 0,
        "merged": 0,
        "merged_alias": 0,
        "merged_url": 0,
        "names_cleaned": 0,
    }


def inspect_entries(entries: list[Entry], country_names: set[str] | None = None) -> dict[str, int]:
    countries = country_names or set()
    junk = vod = low = no_logo = no_id = http_only = country_group = 0
    for entry in entries:
        if is_junk_name(entry):
            junk += 1
        if SKIP_GROUP_RE.search(entry.group or ""):
            vod += 1
        if 0 < entry.height < 480:
            low += 1
        if not entry.logo.startswith("https://"):
            no_logo += 1
        if not entry.tvg_id:
            no_id += 1
        if entry.url.lower().startswith("http://"):
            http_only += 1
        if (entry.group or "").lower() in countries:
            country_group += 1
    return {
        "channels": len(entries),
        "junk_names": junk,
        "vod_groups": vod,
        "low_quality": low,
        "no_logo": no_logo,
        "no_tvg_id": no_id,
        "http": http_only,
        "country_as_group": country_group,
    }


def curate(
    entries: list[Entry],
    *,
    china: bool | str = False,
    min_height: int = 480,
    country_names: set[str] | None = None,
    stats: dict[str, int] | None = None,
) -> list[Entry]:
    tallies = stats if stats is not None else empty_curate_stats()
    tallies.update(empty_curate_stats())
    tallies["input"] = len(entries)
    best: dict[str, Entry] = {}
    for entry in entries:
        if not is_playable_url(entry.url):
            tallies["dropped_unplayable"] += 1
            continue
        if is_junk_name(entry):
            tallies["dropped_junk"] += 1
            continue
        china_entry = uses_china_groups(entry, china)
        group = (
            china_group(entry.group, entry.name)
            if china_entry
            else primary_category(entry.group, country_names)
        )
        if not group:
            tallies["dropped_adult_or_vod"] += 1
            continue
        if 0 < entry.height < min_height:
            tallies["dropped_low_quality"] += 1
            continue
        cleaned = clean_name(entry.name)
        if cleaned and cleaned != entry.name:
            tallies["names_cleaned"] += 1
            entry.name = cleaned
        elif cleaned:
            entry.name = cleaned
        if entry.tvg_name:
            entry.tvg_name = clean_name(entry.tvg_name) or entry.tvg_name
        entry.group = group
        key = channel_key(entry, china=china_entry)
        if key in best:
            tallies["merged"] += 1
        merge_best(best, key, entry)

    aliased: dict[str, Entry] = {}
    for entry in best.values():
        merge_best(aliased, alias_key(entry, china=uses_china_groups(entry, china)), entry)
    tallies["merged_alias"] = max(0, len(best) - len(aliased))

    by_url: dict[str, Entry] = {}
    for entry in aliased.values():
        merge_best(by_url, entry.url, entry)
    tallies["merged_url"] = max(0, len(aliased) - len(by_url))

    kept = list(by_url.values())
    kept.sort(key=lambda item: sort_key(item, china=china is True))
    tallies["kept"] = len(kept)
    return kept


def quality_stats(entries: list[Entry]) -> dict[str, int]:
    return {
        "channels": len(entries),
        "https": sum(1 for item in entries if item.url.lower().startswith("https://")),
        "logos": sum(1 for item in entries if item.logo.startswith("https://")),
        "tvg_id": sum(1 for item in entries if item.tvg_id),
        "hd": sum(1 for item in entries if item.height >= 720),
    }


def sanitize_attr(value: str) -> str:
    return re.sub(r"[\x00-\x1f\x7f\"]+", "", value or "").strip()


def write_m3u(entries: list[Entry], epg: str = "") -> str:
    header = "#EXTM3U"
    epg_clean = sanitize_attr(epg)
    if epg_clean:
        header += f' url-tvg="{epg_clean}" x-tvg-url="{epg_clean}"'
    lines = [header]
    for entry in entries:
        attrs = ["#EXTINF:-1"]
        tvg_id = sanitize_attr(entry.tvg_id)
        country = sanitize_attr(entry.country)
        tvg_name = sanitize_attr(clean_name(entry.tvg_name) or clean_name(entry.name))
        logo = sanitize_attr(entry.logo)
        group = sanitize_attr(entry.group)
        user_agent = sanitize_attr(entry.user_agent)
        referrer = sanitize_attr(entry.referrer)
        title = sanitize_attr(entry.display_name)
        if not title or not entry.url:
            continue
        if tvg_id:
            attrs.append(f'tvg-id="{tvg_id}"')
        if country:
            attrs.append(f'tvg-country="{country}"')
        if tvg_name:
            attrs.append(f'tvg-name="{tvg_name}"')
        if logo.startswith("https://"):
            attrs.append(f'tvg-logo="{logo}"')
        attrs.append(f'group-title="{group}"')
        if user_agent:
            attrs.append(f'http-user-agent="{user_agent}"')
        if referrer:
            attrs.append(f'http-referrer="{referrer}"')
        lines.append(" ".join(attrs) + f",{title}")
        if user_agent:
            lines.append(f"#EXTVLCOPT:http-user-agent={user_agent}")
        if referrer:
            lines.append(f"#EXTVLCOPT:http-referrer={referrer}")
        for extra in entry.extras:
            if extra.startswith("#EXTVLCOPT:") and "\n" not in extra and "\r" not in extra:
                lines.append(sanitize_attr(extra))
        lines.append(entry.url)
    return "\n".join(lines) + "\n"


def _probe_one(entry: Entry) -> str:
    if not is_playable_url(entry.url) or not urlcheck.is_safe_fetch_url(entry.url, resolve=True):
        return "dead"
    headers = {
        "User-Agent": sanitize_attr(entry.user_agent) or USER_AGENT,
        "Accept": "*/*",
        "Range": "bytes=0-2047",
    }
    referrer = sanitize_attr(entry.referrer)
    if referrer.startswith("https://"):
        headers["Referer"] = referrer
    req = urllib.request.Request(entry.url, headers=headers, method="GET")

    def probe(insecure: bool) -> tuple[int, bytes, str]:
        opener = urlcheck.opener_for(insecure=insecure)
        with opener.open(req, timeout=PROBE_TIMEOUT) as resp:
            return resp.status, resp.read(READ_BYTES), resp.geturl()

    try:
        status, chunk, final = probe(False)
    except urllib.error.HTTPError as err:
        err_url = str(getattr(err, "url", "") or getattr(err, "filename", "") or entry.url)
        if not is_playable_url(err_url) or not urlcheck.is_safe_fetch_url(err_url, resolve=True):
            return "dead"
        status = err.code
        try:
            chunk = err.read(READ_BYTES)
        except Exception:
            chunk = b""
        final = err_url
        if status in {404, 410, 451}:
            return "dead"
        if status in {401, 403, 407, 429, 457}:
            return "unknown"
        if status >= 500:
            return "unknown"
    except ssl.SSLError:
        try:
            status, chunk, final = probe(True)
        except Exception:
            return "unknown"
    except Exception:
        return "unknown"
    if final and (not is_playable_url(final) or not urlcheck.is_safe_fetch_url(final, resolve=True)):
        return "dead"
    body = chunk.lstrip().lower()
    if body.startswith((b"<!doctype", b"<html", b"<head")):
        return "dead"
    if status in {200, 206} or 300 <= status < 400:
        return "ok"
    if status in {404, 410, 451}:
        return "dead"
    return "unknown"


def probe_entries(
    entries: list[Entry], workers: int = PROBE_WORKERS, china: bool = False
) -> tuple[list[Entry], dict[str, int]]:
    if not entries:
        return [], {"ok": 0, "dead": 0, "unknown": 0}
    results: dict[int, str] = {}
    futures: dict = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, entry in enumerate(entries):
            if is_ipv6_url(entry.url):
                results[i] = "unknown"
                continue
            futures[pool.submit(_probe_one, entry)] = i
        done = len(results)
        total = len(entries)
        if done and (done == total or done % 200 == 0):
            print(f"probe {done}/{total} (skipped ipv6)", flush=True)
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()
            done += 1
            if done == total or done % 200 == 0:
                print(f"probe {done}/{total}", flush=True)
    counts = {"ok": 0, "dead": 0, "unknown": 0}
    by_key: dict[str, list[tuple[Entry, str]]] = {}
    for i, entry in enumerate(entries):
        status = results.get(i, "unknown")
        counts[status] = counts.get(status, 0) + 1
        by_key.setdefault(channel_key(entry, china=china), []).append((entry, status))
    kept: list[Entry] = []
    for group in by_key.values():
        live = [item for item in group if item[1] == "ok"]
        if live:
            live.sort(key=lambda item: (-item[0].height, not item[0].url.startswith("https://")))
            kept.append(live[0][0])
            continue
        unclear = [item for item in group if item[1] != "dead"]
        if unclear:
            unclear.sort(key=lambda item: (-item[0].height, not item[0].url.startswith("https://")))
            kept.append(unclear[0][0])
    kept.sort(key=lambda item: sort_key(item, china=china))
    return kept, counts
