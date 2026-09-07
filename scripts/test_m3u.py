#!/usr/bin/env python3
from __future__ import annotations

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


def main() -> int:
    test_curate()
    test_harvest_extract()
    test_epg_pair()
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
