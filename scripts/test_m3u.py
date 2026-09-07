#!/usr/bin/env python3
from __future__ import annotations

import urllib.request

import enrich
import harvest
import m3u

SAMPLE = """
#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_US1.xml.gz"
#EXTINF:-1 tvg-id="NewsOne.us@SD" tvg-logo="https://example.com/n.png" group-title="News",News One (360p)
https://example.com/news-360.m3u8
#EXTINF:-1 tvg-id="NewsOne.us@SD" tvg-logo="https://example.com/n.png" group-title="News",News One (1080p)
https://example.com/news-1080.m3u8
#EXTINF:-1 tvg-id="KidsPlus.us@SD" group-title="Entertainment;Kids",Kids Plus (720p)
https://example.com/kids.m3u8
#EXTINF:-1 tvg-id="Adult.us@SD" group-title="XXX",Adult (1080p)
https://example.com/x.m3u8
#EXTINF:-1 tvg-id="Low.us@SD" group-title="General",Low Only (240p)
https://example.com/low.m3u8
#EXTINF:-1 tvg-name="CCTV1" group-title="央视频道",CCTV1 标清
http://203.0.113.10/cctv1-sd.m3u8
#EXTINF:-1 tvg-name="CCTV1" group-title="央视频道",CCTV1 高清
https://example.com/cctv1.m3u8
#EXTINF:-1 tvg-id="YouTubeLive.us" group-title="News",YouTube Live
https://www.youtube.com/@news/live
#EXTINF:-1 tvg-country="AL" tvg-id="News24.al" tvg-logo="https://example.com/n24.png" group-title="Albania",News 24 Ⓢ
https://example.com/news24.m3u8
#EXTINF:-1 tvg-id="Rai1.it" tvg-country="IT" group-title="Italy",Rai 1 [HD]
https://example.com/rai.m3u8
#EXTINF:-1 group-title="News",Mozilla/5.0 (Macintosh) Chrome/149.0.1.0
https://example.com/ua-leak.m3u8
#EXTINF:-1 tvg-id="Film.it" group-title="VOD Italy",Catchup Film
https://example.com/film.m3u8
#EXTINF:-1 tvg-country="CN" group-title="卫视频道",CCTV-1 综合
https://http.example/cctv1.m3u8
#EXTINF:-1 tvg-country="CN" group-title="卫视频道",CCTV1
https://example.com/cctv1-https.m3u8
"""


def test_curate() -> None:
    entries = m3u.parse_playlist(SAMPLE)
    org = m3u.curate([e for e in entries if e.tvg_id and e.country != "AL"], china=False)
    names = [e.display_name for e in org]
    groups = [e.group for e in org]
    assert "News One (1080p)" in names, names
    assert "News One (360p)" not in names
    assert "Low Only" not in names and "Low Only (240p)" not in names
    assert any(e.group == "Kids" for e in org), groups
    assert all(e.group != "XXX" for e in org)
    assert all("youtube" not in e.url for e in org)
    china = m3u.curate([e for e in entries if "CCTV" in e.name], china=True)
    assert len(china) == 1, china
    assert china[0].group == "央视"
    assert china[0].url.startswith("https://")
    albania = [e for e in entries if e.country == "AL"]
    assert albania and albania[0].name.startswith("News 24")
    classified = m3u.curate(entries, china="auto", country_names={"albania", "italy", "al", "it"})
    names = {m3u.clean_name(e.name) for e in classified}
    groups = {e.group for e in classified}
    assert "Rai 1" in names
    assert all(e.group != "Italy" for e in classified)
    assert "General" in groups or any(e.tvg_id == "Rai1.it" and e.group == "General" for e in classified)
    assert all("Chrome" not in e.name for e in classified)
    assert all("VOD" not in e.group and "Catchup" not in e.name for e in classified)
    china_alias = [e for e in classified if "cctv1" in m3u.compact_name(e.name)]
    assert len(china_alias) == 1, china_alias
    assert china_alias[0].url.startswith("https://")


def test_harvest_extract() -> None:
    html = """
    See https://iptv-org.github.io/iptv/index.m3u and
    href="/fmml_ipv6.m3u"
    https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist_zz_vod_it.m3u8
    https://evil.example/secret.m3u
    """
    urls = harvest.extract_playlist_urls(html, base="https://m3u.ibert.me/")
    assert "https://iptv-org.github.io/iptv/index.m3u" in urls
    assert "https://m3u.ibert.me/fmml_ipv6.m3u" in urls
    assert all("vod" not in u.lower() for u in urls)
    assert all("evil.example" not in u for u in urls)


def test_redirect_guard() -> None:
    import urlcheck

    req = urllib.request.Request("https://example.com/live.m3u8")
    handler = urlcheck.SafeFetchRedirectHandler()
    assert handler.redirect_request(req, None, 302, "Found", {}, "http://127.0.0.1/secret") is None
    assert handler.redirect_request(req, None, 302, "Found", {}, "http://169.254.169.254/") is None
    assert urlcheck.is_safe_fetch_url("http://127.0.0.1/x") is False
    assert urlcheck.is_safe_https_url("https://example.com/a.m3u8") is True
    assert urlcheck.is_safe_https_url("http://example.com/a.m3u8") is False


def test_epg_pair() -> None:
    mapping = enrich.parse_epgshare_map(
        [
            "https://epgshare01.online/epgshare01/epg_ripper_US1.xml.gz",
            "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
            "https://epgshare01.online/epgshare01/epg_ripper_ALL_SOURCES1.xml.gz",
        ]
    )
    assert mapping["US"].endswith("US1.xml.gz")
    assert mapping["UK"].endswith("UK1.xml.gz")
    jp = enrich.epg_for_country("JP", mapping)
    assert jp[0].endswith("guide.xml")
    cn = enrich.epg_for_country("CN", mapping)
    assert "fanmingming" in cn[0]
    svg = enrich.pick_logo(
        "AlJazeera.qa",
        "https://i.imgur.com/old.jpg",
        {
            "AlJazeera.qa": [
                {
                    "in_use": True,
                    "format": "SVG",
                    "width": 512,
                    "height": 512,
                    "url": "https://upload.wikimedia.org/logo.svg",
                }
            ]
        },
    )
    assert svg.endswith(".svg")
    body = m3u.write_m3u([], epg="https://example.com/guide.xml")
    assert 'url-tvg="https://example.com/guide.xml"' in body
    assert 'x-tvg-url="https://example.com/guide.xml"' in body
    tagged = m3u.write_m3u(
        [
            m3u.Entry(
                name="Rai 1",
                url="https://example.com/rai.m3u8",
                tvg_id="Rai1.it",
                country="IT",
                group="General",
                logo="https://example.com/rai.png",
            )
        ]
    )
    assert 'tvg-country="IT"' in tagged


def test_pipeline() -> None:
    import pipeline

    raw = m3u.parse_playlist(SAMPLE)
    countries = {"albania", "italy", "al", "it"}
    census = m3u.inspect_entries(raw, countries)
    assert census["junk_names"] >= 1
    assert census["vod_groups"] >= 1
    assert census["country_as_group"] >= 1
    kept, report = pipeline.process_entries(raw, {}, {}, countries, china="auto", probe=False)
    assert report["fix"]["dropped_junk"] >= 1
    assert report["fix"]["dropped_adult_or_vod"] >= 1
    assert report["fix"]["kept"] == len(kept)
    assert report["result"]["junk_names"] == 0
    assert report["result"]["vod_groups"] == 0
    assert report["result"]["country_as_group"] == 0
    assert all(e.group != "Italy" for e in kept)
    assert m3u.catalog_category(m3u.Entry(name="CCTV1", url="https://x", group="央视", country="CN")) == "General"


def test_submit_channel() -> None:
    import community
    import submit_channel

    body = """
### Channel name

Test News

### Stream URL

https://cdn.example.com/test-news.m3u8

### Country

GB

### Category

News

### Please confirm

- [x] This is a public live stream I am allowed to share. It is not adult or on-demand video.
"""
    fields = submit_channel.parse_issue_fields(body)
    assert fields["name"] == "Test News"
    assert "cdn.example.com" in fields["url"]
    entry, err = submit_channel.build_entry(fields, 9)
    assert err == "", err
    assert entry.name == "Test News"
    assert entry.country == "UK"
    assert entry.group == "News"
    assert entry.tvg_id == "TestNews.uk"

    http_fields = dict(fields)
    http_fields["url"] = "http://cdn.example.com/test-news.m3u8"
    _, err = submit_channel.build_entry(http_fields, 9)
    assert err

    page_fields = dict(fields)
    page_fields["url"] = "https://www.youtube.com/watch?v=dQw4w9wgGcQ"
    _, err = submit_channel.build_entry(page_fields, 9)
    assert err

    missing = submit_channel.evaluate("### Channel name\n\nOnly a name\n", 1, "tester", probe=False)
    assert missing["outcome"] == "rejected"

    dup_fields = dict(fields)
    dup_fields["name"] = "Al Jazeera English"
    dup_fields["url"] = "https://live-hls-apps-aje-fa.getaj.net/AJE/index.m3u8"
    dup_entry, dup_err = submit_channel.build_entry(dup_fields, 9)
    assert dup_err == ""
    assert submit_channel.is_duplicate(dup_entry)

    left = m3u.Entry(name="News One", url="https://a.example/live.m3u8", group="News", country="US")
    right = m3u.Entry(
        name="News One",
        url="https://b.example/live.m3u8",
        group="News",
        country="US",
        logo="https://l.example/n.png",
    )
    merged = community.merge_entries([left], [right])
    assert len(merged) == 1
    assert merged[0].logo.endswith("n.png")

    import urlcheck

    assert urlcheck.is_safe_https_url("https://cdn.example.com/live.m3u8")
    assert not urlcheck.is_safe_https_url("http://cdn.example.com/live.m3u8")
    assert not urlcheck.is_safe_https_url("https://user:pass@cdn.example.com/live.m3u8")
    assert not urlcheck.is_safe_https_url("https://127.0.0.1/live.m3u8")
    assert not urlcheck.is_safe_https_url("https://169.254.169.254/latest/meta-data/")
    assert not urlcheck.is_safe_https_url("https://localhost/live.m3u8")
    assert not urlcheck.is_safe_https_url("https://metadata.google.internal/computeMetadata/v1/")
    assert not urlcheck.is_safe_https_url("https://evil.localhost/live.m3u8")
    assert not urlcheck.is_safe_https_url("https://192.168.0.5/live.m3u8")
    assert not urlcheck.is_safe_https_url("https://[::1]/live.m3u8")

    inject_fields = dict(fields)
    inject_fields["name"] = 'News" tvg-logo="https://evil.example/x.png'
    inject_fields["url"] = "https://cdn.example.com/ok.m3u8"
    _, inject_err = submit_channel.build_entry(inject_fields, 3)
    assert inject_err

    quoted = m3u.Entry(
        name='News" tvg-logo="https://evil.example/x.png',
        url="https://cdn.example.com/ok.m3u8",
        group="News",
    )
    written = m3u.write_m3u([quoted])
    assert 'tvg-logo="https://evil.example/x.png"' not in written

    adult_fields = dict(fields)
    adult_fields["name"] = "Adult XXX"
    adult_fields["category"] = "News"
    _, adult_err = submit_channel.build_entry(adult_fields, 4)
    assert adult_err

    assert not m3u.is_playable_url("https://127.0.0.1/live.m3u8")
    assert not m3u.is_playable_url("https://0.0.0.0/live.m3u8")


def main() -> int:
    test_curate()
    test_harvest_extract()
    test_redirect_guard()
    test_epg_pair()
    test_pipeline()
    test_submit_channel()
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
