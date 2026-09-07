#!/usr/bin/env python3
"""Validate a GitHub channel suggestion and add it to the community list."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import community  # noqa: E402
import m3u  # noqa: E402
import urlcheck  # noqa: E402

HEADING_MAP = {
    "channel name": "name",
    "name": "name",
    "stream url": "url",
    "url": "url",
    "country": "country",
    "country code": "country",
    "category": "category",
    "logo url": "logo",
    "logo": "logo",
    "please confirm": "confirm",
    "confirm": "confirm",
}
SKIP_VALUES = {"", "_no response_", "n/a", "none", "null"}
MAX_NAME = 80
MAX_COMMUNITY = 200
ALLOWED_SITE = "https://ezhu331.github.io/tamatv"
GITHUB_USER_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")
NAME_UNSAFE_RE = re.compile(r'[\x00-\x1f\x7f"<>]')
ADDED = "This channel is in the Community list now."
DUPLICATE = "This channel is already in the lists."
REJECT_URL = "Use a public HTTPS live stream URL, not a page, download, or playlist file."
REJECT_DEAD = "This stream did not respond. Try again with a working live URL."
REJECT_NAME = "Add a short channel name and a public live stream URL."
REJECT_FULL = "The community list is full right now."
NEEDS_REVIEW = "This stream could not be confirmed yet. Leave the issue open and we will check it."
COMMENTS = {ADDED, DUPLICATE, REJECT_URL, REJECT_DEAD, REJECT_NAME, NEEDS_REVIEW, REJECT_FULL}


def parse_issue_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current = ""
    chunks: list[str] = []
    for raw in (body or "").replace("\r\n", "\n").splitlines():
        line = raw.strip()
        heading = re.match(r"^#{1,3}\s+(.+?)\s*$", line)
        if heading:
            if current:
                fields[current] = "\n".join(chunks).strip()
            current = HEADING_MAP.get(heading.group(1).strip().lower(), "")
            chunks = []
            continue
        if current:
            chunks.append(line)
    if current:
        fields[current] = "\n".join(chunks).strip()
    return fields


def field_value(fields: dict[str, str], key: str) -> str:
    value = (fields.get(key) or "").strip()
    if value.lower() in SKIP_VALUES:
        return ""
    return value


def first_url(text: str) -> str:
    match = re.search(r"https://[^\s<>\"']+", text or "")
    return match.group(0).rstrip(").,]}>\"'") if match else ""


def normalize_country(value: str) -> str:
    code = re.sub(r"[^A-Za-z]", "", value or "").upper()
    if code == "GB":
        return "UK"
    return code if len(code) == 2 else ""


def normalize_category(value: str) -> str:
    raw = (value or "General").strip()
    if m3u.ADULT_RE.search(raw) or m3u.SKIP_GROUP_RE.search(raw) or m3u.BAD_TITLE_RE.search(raw):
        return ""
    canon = m3u.CATEGORY_CANON.get(raw.lower())
    if canon == "":
        return ""
    if canon in m3u.CATEGORY_ORDER:
        return canon
    return "General"


def normalize_name(value: str) -> str:
    text = m3u.clean_name(re.sub(r"[\r\n]+", " ", value or ""))
    text = NAME_UNSAFE_RE.sub("", text)
    return text[:MAX_NAME]


def normalize_user(value: str) -> str:
    user = (value or "").strip()
    return user if GITHUB_USER_RE.fullmatch(user) else ""


def confirmed(fields: dict[str, str]) -> bool:
    blob = field_value(fields, "confirm").lower()
    if not blob:
        return True
    return "[x]" in blob.replace("[X]", "[x]")


def make_tvg_id(name: str, country: str, issue: int) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "", name)
    suffix = (country or "int").lower()
    if slug:
        return f"{slug}.{suffix}"
    return f"community{issue}.{suffix}" if issue else f"Community.{suffix}"


def existing_urls() -> set[str]:
    urls = {row["url"].strip() for row in community.load_records() if row.get("url")}
    paths = [ROOT / "japan.m3u", ROOT / "world.m3u", community.PLAYLIST]
    for folder in (ROOT / "playlists" / "countries", ROOT / "playlists" / "categories"):
        if folder.is_dir():
            paths.extend(sorted(folder.glob("*.m3u")))
    for path in paths:
        if not path.exists():
            continue
        for entry in m3u.parse_m3u(path.read_text(encoding="utf-8", errors="replace")):
            if entry.url:
                urls.add(entry.url.strip())
    return urls


def existing_keys() -> set[str]:
    keys = set()
    for entry in community.load_entries():
        china = m3u.uses_china_groups(entry, "auto")
        keys.add(m3u.alias_key(entry, china=china))
    return keys


def validate_url(url: str) -> str:
    if not urlcheck.is_safe_https_url(url, resolve=False):
        return REJECT_URL
    if not m3u.is_playable_url(url):
        return REJECT_URL
    return ""


def build_entry(fields: dict[str, str], issue: int) -> tuple[m3u.Entry | None, str]:
    name = normalize_name(field_value(fields, "name"))
    url = first_url(field_value(fields, "url"))
    if not name or not url:
        return None, REJECT_NAME
    if re.search(r"://|=|#EXT", name, re.I):
        return None, REJECT_NAME
    if m3u.is_junk_name(m3u.Entry(name=name, url=url)) or m3u.BAD_TITLE_RE.search(name) or m3u.ADULT_RE.search(name):
        return None, REJECT_NAME
    err = validate_url(url)
    if err:
        return None, err
    logo = first_url(field_value(fields, "logo"))
    if logo and validate_url(logo):
        logo = ""
    country = normalize_country(field_value(fields, "country"))
    group = normalize_category(field_value(fields, "category"))
    if not group:
        return None, REJECT_NAME
    entry = m3u.Entry(
        name=name,
        url=url,
        tvg_id=make_tvg_id(name, country, issue),
        tvg_name=name,
        logo=logo,
        group=group,
        country=country,
        height=m3u.quality_height(name),
    )
    curated = m3u.curate([entry], china="auto", min_height=0)
    if not curated:
        return None, REJECT_NAME
    return curated[0], ""


def is_duplicate(entry: m3u.Entry) -> bool:
    if entry.url in existing_urls():
        return True
    china = m3u.uses_china_groups(entry, "auto")
    return m3u.alias_key(entry, china=china) in existing_keys()


def probe_status(entry: m3u.Entry) -> str:
    return urlcheck.probe_https(entry.url)


def set_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        print(f"{name}={value}")
        return
    with open(path, "a", encoding="utf-8") as handle:
        if "\n" in value:
            handle.write(f"{name}<<EOF\n{value}\nEOF\n")
        else:
            handle.write(f"{name}={value}\n")


def accept(entry: m3u.Entry, issue: int, user: str) -> dict | None:
    if len(community.load_records()) >= MAX_COMMUNITY:
        return None
    record = {
        "name": entry.name,
        "url": entry.url,
        "country": entry.country,
        "group": entry.group,
        "logo": entry.logo,
        "tvg_id": entry.tvg_id,
        "issue": issue if issue > 0 else 0,
        "by": normalize_user(user),
        "added": community.utc_now(),
    }
    community.append_record(record)
    community.patch_catalog(ALLOWED_SITE, "https://github.com/EZHU331/tamatv")
    return record


def evaluate(body: str, issue: int, user: str, *, probe: bool = True) -> dict:
    fields = parse_issue_fields(body)
    if not confirmed(fields):
        return {"outcome": "rejected", "comment": REJECT_NAME}
    entry, err = build_entry(fields, issue)
    if err or entry is None:
        return {"outcome": "rejected", "comment": err or REJECT_NAME}
    if is_duplicate(entry):
        return {"outcome": "duplicate", "comment": DUPLICATE}
    if probe:
        status = probe_status(entry)
        if status == "dead":
            return {"outcome": "rejected", "comment": REJECT_DEAD}
        if status != "ok":
            return {"outcome": "needs-review", "comment": NEEDS_REVIEW}
    if len(community.load_records()) >= MAX_COMMUNITY:
        return {"outcome": "rejected", "comment": REJECT_FULL}
    record = accept(entry, issue, user)
    if not record:
        return {"outcome": "rejected", "comment": REJECT_FULL}
    return {"outcome": "added", "comment": ADDED}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and add a community channel")
    parser.add_argument("--body-file", help="Issue body markdown")
    parser.add_argument("--issue", type=int, default=0)
    parser.add_argument("--user", default="")
    parser.add_argument("--no-probe", action="store_true")
    args = parser.parse_args(argv)

    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    else:
        body = os.environ.get("ISSUE_BODY") or ""
    if len(body) > 20000:
        body = body[:20000]
    try:
        issue = args.issue or int(os.environ.get("ISSUE_NUMBER") or "0")
    except ValueError:
        issue = 0
    user = args.user or os.environ.get("ISSUE_USER") or ""
    result = evaluate(body, issue, user, probe=not args.no_probe)
    comment = result["comment"] if result["comment"] in COMMENTS else REJECT_NAME
    outcome = result["outcome"] if result["outcome"] in {"added", "duplicate", "rejected", "needs-review"} else "rejected"
    set_output("outcome", outcome)
    set_output("comment", comment)
    print(outcome)
    print(comment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
