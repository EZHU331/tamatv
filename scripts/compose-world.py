#!/usr/bin/env python3
"""Write world.m3u from a probed public news and documentary table."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTS = (ROOT / "world.m3u",)
EPG = ",".join(
    [
        "https://animenosekai.github.io/japanterebi-xmltv/guide.xml",
        "https://epgshare01.online/epgshare01/epg_ripper_ALJAZEERA1.xml.gz",
        "https://epgshare01.online/epgshare01/epg_ripper_UK1.xml.gz",
    ]
)

# Curated after probing official CDNs (Al Jazeera, France 24, DW, NHK, CGTN,
# Bloomberg, NASA, Euronews, CBS, CNA, TRT) plus working iptv-org FAST feeds.
# Skip IP restreams, URL shorteners, Pluto proxies, and dead hosts.
CHANNELS = [
    {
        "id": "AlJazeera.qa@English",
        "name": "Al Jazeera English",
        "logo": "https://i.imgur.com/7bRVpnu.png",
        "group": "News",
        "url": "https://live-hls-apps-aje-fa.getaj.net/AJE/index.m3u8",
    },
    {
        "id": "AlJazeera.qa@Arabic",
        "name": "Al Jazeera Arabic",
        "logo": "https://i.imgur.com/7bRVpnu.png",
        "group": "News",
        "url": "https://live-hls-apps-aja-fa.getaj.net/AJA/index.m3u8",
    },
    {
        "id": "AlJazeeraMubasher.qa",
        "name": "Al Jazeera Mubasher",
        "logo": "https://i.imgur.com/X80DQvF.png",
        "group": "News",
        "url": "https://live-hls-apps-ajm-fa.getaj.net/AJM/index.m3u8",
    },
    {
        "id": "France24.fr@English",
        "name": "France 24 English",
        "logo": "https://i.imgur.com/u8N6uoj.png",
        "group": "News",
        "url": "https://static.france24.com/live/F24_EN_HI_HLS/live_tv.m3u8",
    },
    {
        "id": "France24.fr@French",
        "name": "France 24 French",
        "logo": "https://i.imgur.com/u8N6uoj.png",
        "group": "News",
        "url": "https://static.france24.com/live/F24_FR_HI_HLS/live_tv.m3u8",
    },
    {
        "id": "France24.fr@Arabic",
        "name": "France 24 Arabic",
        "logo": "https://i.imgur.com/u8N6uoj.png",
        "group": "News",
        "url": "https://static.france24.com/live/F24_AR_HI_HLS/live_tv.m3u8",
    },
    {
        "id": "France24.fr@Spanish",
        "name": "France 24 Español",
        "logo": "https://i.imgur.com/u8N6uoj.png",
        "group": "News",
        "url": "https://static.france24.com/live/F24_ES_HI_HLS/live_tv.m3u8",
    },
    {
        "id": "DW.de@English",
        "name": "DW English",
        "logo": "https://i.imgur.com/8MRNFb9.png",
        "group": "News",
        "url": "https://dwamdstream102.akamaized.net/hls/live/2015525/dwstream102/index.m3u8",
    },
    {
        "id": "DW.de@Deutsch",
        "name": "DW Deutsch",
        "logo": "https://i.imgur.com/8MRNFb9.png",
        "group": "News",
        "url": "https://dwamdstream104.akamaized.net/hls/live/2015530/dwstream104/index.m3u8",
    },
    {
        "id": "DW.de@Arabic",
        "name": "DW Arabic",
        "logo": "https://i.imgur.com/8MRNFb9.png",
        "group": "News",
        "url": "https://dwamdstream103.akamaized.net/hls/live/2015526/dwstream103/master.m3u8",
    },
    {
        "id": "DW.de@Russian",
        "name": "DW Russian",
        "logo": "https://i.imgur.com/8MRNFb9.png",
        "group": "News",
        "url": "https://dwamdstream110.akamaized.net/hls/live/2017971/dwstream110/master.m3u8",
    },
    {
        "id": "EuronewsEnglish.fr",
        "name": "Euronews English",
        "logo": "https://jiotvimages.cdn.jio.com/dare_images/images/Euro_News.png",
        "group": "News",
        "url": "https://cdn-euronews.akamaized.net/live/eds/euronews-en/25069/index.m3u8",
    },
    {
        "id": "NHKWorldJapan.jp",
        "name": "NHK World-Japan",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/NHK_World-Japan_TV.svg/960px-NHK_World-Japan_TV.svg.png",
        "group": "News",
        "url": "https://masterpl.hls.nhkworld.jp/hls/w/live/smarttv.m3u8",
    },
    {
        "id": "CGTN.cn",
        "name": "CGTN",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/CGTN.svg/960px-CGTN.svg.png",
        "group": "News",
        "url": "https://news.cgtn.com/resource/live/english/cgtn-news.m3u8",
    },
    {
        "id": "CGTNFrench.cn",
        "name": "CGTN Français",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/CGTN.svg/960px-CGTN.svg.png",
        "group": "News",
        "url": "https://news.cgtn.com/resource/live/french/cgtn-f.m3u8",
    },
    {
        "id": "CGTNSpanish.cn",
        "name": "CGTN Español",
        "logo": "https://i.imgur.com/Poz3xfi.png",
        "group": "News",
        "url": "https://espanol-livews.cgtn.com/hls/LSveOGBaBw41Ea7ukkVAUdKQ220802LSTexu6xAuFH8VZNBLE1ZNEa220802cd/playlist.m3u8",
    },
    {
        "id": "CGTNArabic.cn",
        "name": "CGTN Arabic",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/CGTN.svg/960px-CGTN.svg.png",
        "group": "News",
        "url": "https://news.cgtn.com/resource/live/arabic/cgtn-a.m3u8",
    },
    {
        "id": "CGTNRussian.cn",
        "name": "CGTN Русский",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/CGTN.svg/960px-CGTN.svg.png",
        "group": "News",
        "url": "https://news.cgtn.com/resource/live/russian/cgtn-r.m3u8",
    },
    {
        "id": "TRTWorld.tr",
        "name": "TRT World",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/TRT_World.svg/960px-TRT_World.svg.png",
        "group": "News",
        "url": "https://tv-trtworld.medya.trt.com.tr/master.m3u8",
    },
    {
        "id": "CNA.sg",
        "name": "CNA",
        "logo": "https://i.imgur.com/awIDugE.png",
        "group": "News",
        "url": "https://d2e1asnsl7br7b.cloudfront.net/7782e205e72f43aeb4a48ec97f66ebbe/index.m3u8",
    },
    {
        "id": "ABCNews.au",
        "name": "ABC News Australia",
        "logo": "https://i.imgur.com/BrW7gk8.png",
        "group": "News",
        "url": "https://abc-news-dmd-streams-1.akamaized.net/out/v1/701126012d044971b3fa89406a440133/index.m3u8",
    },
    {
        "id": "BloombergTV.us",
        "name": "Bloomberg TV",
        "logo": "https://i.imgur.com/OuogLHx.png",
        "group": "News",
        "url": "https://www.bloomberg.com/media-manifest/streams/us.m3u8",
    },
    {
        "id": "CBSNews.us",
        "name": "CBS News",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b0/CBS_News_247_logo.svg/960px-CBS_News_247_logo.svg.png",
        "group": "News",
        "url": "https://cbsn-us.cbsnstream.cbsnews.com/out/v1/55a8648e8f134e82a470f83d55a456bb/master.m3u8",
    },
    {
        "id": "NBCNewsNOW.us",
        "name": "NBC News NOW",
        "logo": "https://i.imgur.com/JZt2qh5.png",
        "group": "News",
        "url": "https://d1si3n1st4nkgb.cloudfront.net/10502/88896001/hls/master.m3u8?ads.xumo_channelId=88896001",
    },
    {
        "id": "CBCNewsNetwork.ca",
        "name": "CBC News",
        "logo": "https://i.imgur.com/SjTdhvJ.png",
        "group": "News",
        "url": "https://d2ny9lo79ujali.cloudfront.net/CBC_News_International.m3u8",
    },
    {
        "id": "ReutersTV.us",
        "name": "Reuters",
        "logo": "https://i.imgur.com/6eQ2nCJ.png",
        "group": "News",
        "url": "https://amg00453-reuters-amg00453c1-rakuten-uk-2110.playouts.now.amagi.tv/playlist/amg00453-reuters-reuters-rakutenuk/playlist.m3u8",
    },
    {
        "id": "Alarabiya.ae",
        "name": "Al Arabiya",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Al_Arabiya.svg/960px-Al_Arabiya.svg.png",
        "group": "News",
        "url": "https://live.alarabiya.net/alarabiapublish/alarabiya.smil/playlist.m3u8",
    },
    {
        "id": "AlArabiyaEnglish.sa",
        "name": "Al Arabiya English",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Al_Arabiya.svg/960px-Al_Arabiya.svg.png",
        "group": "News",
        "url": "https://live.alarabiya.net/alarabiapublish/english/playlist_dvr.m3u8",
    },
    {
        "id": "SkyNewsArabia.ae",
        "name": "Sky News Arabia",
        "logo": "https://i.imgur.com/SvjU4h6.png",
        "group": "News",
        "url": "https://live-stream.skynewsarabia.com/c-horizontal-channel/horizontal-stream/index.m3u8",
    },
    {
        "id": "i24NEWSEnglishWorld.il",
        "name": "i24NEWS English",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/79/LOGO_i24NEWS.png/960px-LOGO_i24NEWS.png",
        "group": "News",
        "url": "https://i24newsenglish-cdn.encoders.immergo.tv/master.m3u8",
    },
    {
        "id": "Alhurra.us",
        "name": "Alhurra",
        "logo": "https://i.imgur.com/tiQp2sR.png",
        "group": "News",
        "url": "https://mbn-ingest-worldsafe.akamaized.net/hls/live/2038900/MBN_Alhurra_Worldsafe_HLS/master.m3u8",
    },
    {
        "id": "TV5MondeInfo.fr",
        "name": "TV5Monde Info",
        "logo": "https://i.imgur.com/AJx5Fy2.png",
        "group": "News",
        "url": "https://ott.tv5monde.com/Content/HLS/Live/channel(info)/variant.m3u8",
    },
    {
        "id": "RaiNews24.it",
        "name": "Rai News 24",
        "logo": "https://i.imgur.com/n2u57y3.png",
        "group": "News",
        "url": "https://d3k8wzt41aflvx.cloudfront.net/RAINEWS24/Live.m3u8",
    },
    {
        "id": "tagesschau24.de",
        "name": "tagesschau24",
        "logo": "https://i.imgur.com/LH0Gctv.png",
        "group": "News",
        "url": "https://tagesschau.akamaized.net/hls/live/2020115/tagesschau/tagesschau_1/master.m3u8",
    },
    {
        "id": "ArirangTV.kr",
        "name": "Arirang TV",
        "logo": "https://i.imgur.com/Asu5pE9.png",
        "group": "News",
        "url": "https://amdlive-ch01-ctnd-cdn.ctnd.com.edgesuite.net/arirang_1ch/smil:arirang_1ch.smil/playlist.m3u8",
    },
    {
        "id": "AfricanewsEnglish.fr",
        "name": "Africanews English",
        "logo": "https://i.imgur.com/5UxU4zc.png",
        "group": "News",
        "url": "https://cdn-euronews.akamaized.net/live/eds/africanews-en/25049/index.m3u8",
    },
    {
        "id": "AfricanewsFrench.fr",
        "name": "Africanews French",
        "logo": "https://i.imgur.com/5UxU4zc.png",
        "group": "News",
        "url": "https://cdn-euronews.akamaized.net/live/eds/africanews-fr/25050/index.m3u8",
    },
    {
        "id": "SABCNews.za",
        "name": "SABC News",
        "logo": "https://i.imgur.com/liLta8j.png",
        "group": "News",
        "url": "https://sabconetanw.cdn.mangomolo.com/news/smil:news.stream.smil/master.m3u8",
    },
    {
        "id": "IndiaToday.in",
        "name": "India Today",
        "logo": "https://xstreamcp-assets-msp.streamready.in/assets/LIVETV/LIVECHANNEL/LIVETV_LIVETVCHANNEL_INDIA_TODAY/images/LOGO_HD/image.png",
        "group": "News",
        "url": "https://d1rc86nwwc9fag.cloudfront.net/vglive-sk-293160/master.m3u8",
    },
    {
        "id": "AlJazeeraDocumentary.qa",
        "name": "Al Jazeera Documentary",
        "logo": "https://i.imgur.com/5dNJlLo.png",
        "group": "Documentary",
        "url": "https://live-hls-apps-ajd-fa.getaj.net/AJD/index.m3u8",
        "referrer": "https://www.aljazeera.com/",
    },
    {
        "id": "CGTNDocumentary.cn",
        "name": "CGTN Documentary",
        "logo": "https://i.imgur.com/JHv0WxM.png",
        "group": "Documentary",
        "url": "https://news.cgtn.com/resource/live/document/cgtn-doc.m3u8",
    },
    {
        "id": "BBCEarth.uk",
        "name": "BBC Earth",
        "logo": "https://i.imgur.com/nGSsUd4.png",
        "group": "Documentary",
        "url": "https://amg00793-amg00793c6-xumo-us-2669.playouts.now.amagi.tv/BBCStudios-BBCEarthA-hls/playlist.m3u8",
    },
    {
        "id": "BloombergOriginals.us",
        "name": "Bloomberg Originals",
        "logo": "https://i.imgur.com/OuogLHx.png",
        "group": "Documentary",
        "url": "https://bloomberg.com/media-manifest/streams/qt.m3u8",
    },
    {
        "id": "CuriosityNOW.de",
        "name": "Curiosity Now",
        "logo": "https://i.imgur.com/gJ9eMaG.png",
        "group": "Documentary",
        "url": "https://amg00170-amg00170c4-samsung-gb-4232.playouts.now.amagi.tv/playlist.m3u8",
    },
    {
        "id": "CNAOriginals.sg",
        "name": "CNA Originals",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/CNA_new_logo.svg/500px-CNA_new_logo.svg.png",
        "group": "Documentary",
        "url": "https://amg01082-cna-amg01082c1-rlaxx-us-11304.playouts.now.amagi.tv/playlist.m3u8",
    },
    {
        "id": "NASATV.us",
        "name": "NASA TV Public",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/NASA_logo.svg/960px-NASA_logo.svg.png",
        "group": "Documentary",
        "url": "https://ntv1.akamaized.net/hls/live/2014075/NASA-NTV1-HLS/master.m3u8",
    },
    {
        "id": "NASATVMedia.us",
        "name": "NASA TV Media",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/NASA_logo.svg/960px-NASA_logo.svg.png",
        "group": "Documentary",
        "url": "https://ntv2.akamaized.net/hls/live/2013922/NASA-NTV2-HLS/master.m3u8",
    },
    {
        "id": "LoveNature.ca",
        "name": "Love Nature",
        "logo": "https://i.imgur.com/7uNdcWB.png",
        "group": "Documentary",
        "url": "https://aegis-cloudfront-1.tubi.video/6d6d0f24-8445-4b4c-bdf6-44f9e38beaa4/playlist.m3u8",
    },
    {
        "id": "RealWild.uk",
        "name": "Real Wild",
        "logo": "https://i.imgur.com/T9HHmAO.png",
        "group": "Documentary",
        "url": "https://lds-realwild-samsungau.amagi.tv/playlist.m3u8",
    },
]


def extinf(ch: dict) -> str:
    attrs = [
        f'tvg-id="{ch["id"]}"',
        f'tvg-name="{ch["name"]}"',
        f'tvg-logo="{ch["logo"]}"',
    ]
    if ch.get("referrer"):
        attrs.append(f'http-referrer="{ch["referrer"]}"')
    attrs.append(f'group-title="{ch["group"]}"')
    lines = [f'#EXTINF:-1 {" ".join(attrs)},{ch["name"]}']
    if ch.get("referrer"):
        lines.append(f'#EXTVLCOPT:http-referrer={ch["referrer"]}')
    lines.append(ch["url"])
    return "\n".join(lines)


def playlist_text() -> str:
    return "\n".join(
        [
            f'#EXTM3U url-tvg="{EPG}" x-tvg-url="{EPG}"',
            "# tamaTV world news and documentary — public HLS only. tamaTV does not host these streams.",
            "# Kept: official news CDNs and working HD FAST documentary feeds.",
            "# Dropped: IP restreams, URL shorteners, Pluto proxies, pay-TV copies, dead hosts.",
            "",
            *[extinf(ch) for ch in CHANNELS],
            "",
        ]
    )


def write_playlists() -> list[Path]:
    body = playlist_text()
    written: list[Path] = []
    for path in OUTS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    paths = write_playlists()
    print(f"Wrote {len(CHANNELS)} channels -> " + ", ".join(p.relative_to(ROOT).as_posix() for p in paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
