#!/usr/bin/env python3
"""Write japan.m3u from the curated public Japan channel table."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTS = (ROOT / "japan.m3u", ROOT / "playlists" / "countries" / "jp.m3u")
EPG = "https://animenosekai.github.io/japanterebi-xmltv/guide.xml"

# Curated after probing iptv-org / Free-TV Japan / gitee ieyer mirrors,
# official NHK World CDNs, Shop Channel, QVC, Weathernews, GSTV, CGNTV,
# and Rakuten FAST (TOKYO MX + news).
# Skip non-Japan rows, dead hosts, private IPs, session tokens, naori proxies,
# willfonk CS restreams, and DASH/ClearKey sources the app cannot play.
#
# Groups (browse order): ニュース → 地上波 → アニメ → 通販 → 天気 → 宗教
CHANNELS = [
    # --- ニュース ---
    {
        "id": "NHKWorldJapan.jp",
        "name": "NHKワールド JAPAN",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/NHK_World-Japan_TV.svg/960px-NHK_World-Japan_TV.svg.png",
        "group": "ニュース",
        "url": "https://masterpl.hls.nhkworld.jp/hls/w/live/smarttv.m3u8",
    },
    {
        "id": "NHKWorldPremium.jp",
        "name": "NHKワールド・プレミアム",
        "logo": "https://i.imgur.com/4ESi2La.png",
        "group": "ニュース",
        "url": "https://media-tyo.hls.nhkworld.jp/hls/wp/live/master.m3u8",
    },
    {
        "id": "NTVNews.jp",
        "name": "日テレNEWS",
        "logo": "https://channel.rakuten.co.jp/service/img/logo/chlogo-with-number/104_ntvnews.png",
        "group": "ニュース",
        "url": "https://cdn-apne1.tsv2.amagi.tv/linear/amg01287-rakutentvjapan-news1hlscmaf-rakutenjp/playlist.m3u8",
    },
    {
        "id": "FNNPrimeOnline.jp",
        "name": "FNNプライムオンライン",
        "logo": "https://channel.rakuten.co.jp/service/img/logo/chlogo-with-number/105_fnn.png",
        "group": "ニュース",
        "url": "https://cdn-uw2-prod.tsv2.amagi.tv/linear/amg01287-rakutentvjapan-news4-cmaf-rakutenjp/playlist.m3u8",
    },
    {
        "id": "MBSNews.jp",
        "name": "MBSニュース",
        "logo": "https://i.imgur.com/RfrkGrd.png",
        "group": "ニュース",
        "url": "https://cdn-uw2-prod.tsv2.amagi.tv/linear/amg01287-rakutentvjapan-news5-cmaf-rakutenjp/playlist.m3u8",
    },
    # --- 地上波 ---
    {
        "id": "JOAKDTV.jp",
        "name": "NHK総合",
        "logo": "https://i.imgur.com/fAZ2BEZ.png",
        "group": "地上波",
        "url": "https://nhk4.mov3.co/hls/nhk.m3u8",
    },
    {
        "id": "JOAXDTV.jp",
        "name": "日本テレビ",
        "logo": "https://i.imgur.com/IxD8V5X.png",
        "group": "地上波",
        "url": "https://ntv5.mov3.co/hls/ntv.m3u8",
    },
    {
        "id": "JOEXDTV.jp",
        "name": "テレビ朝日",
        "logo": "https://i.imgur.com/YCqB5Kj.png",
        "group": "地上波",
        "url": "https://tvasahi.mov3.co/hls/tvasahi.m3u8",
    },
    {
        "id": "JORXDTV.jp",
        "name": "TBSテレビ",
        "logo": "https://i.imgur.com/dUn2GRn.png",
        "group": "地上波",
        "url": "https://tbs5.mov3.co/hls/tbs.m3u8",
    },
    {
        "id": "JOTXDTV.jp",
        "name": "テレビ東京",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/TV_Tokyo_%28Japanese%29_2023.svg/960px-TV_Tokyo_%28Japanese%29_2023.svg.png",
        "group": "地上波",
        "url": "https://tvtokyo.mov3.co/hls/tvtokyo.m3u8",
    },
    {
        "id": "JOCXDTV.jp",
        "name": "フジテレビ",
        "logo": "https://i.imgur.com/sEWDmMD.png",
        "group": "地上波",
        "url": "https://fujitv4.mov3.co/hls/fujitv.m3u8",
    },
    {
        "id": "TokyoMX1.jp",
        "name": "TOKYO MX",
        "logo": "https://i.imgur.com/igia8OX.png",
        "group": "地上波",
        "url": "https://cdn-uw2-prod.tsv2.amagi.tv/linear/amg01287-rakutentvjapan-tokyomx-cmaf-rakutenjp/playlist.m3u8",
    },
    # --- アニメ ---
    {
        "id": "Aniplus.sg",
        "name": "Aniplus",
        "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0a/ANIPLUS_logo.svg/640px-ANIPLUS_logo.svg.png",
        "group": "アニメ",
        "url": "https://amg18481-amg18481c1-amgplt0352.playout.now3.amagi.tv/playlist/amg18481-amg18481c1-amgplt0352/playlist.m3u8",
    },
    # --- 通販 ---
    {
        "id": "ShopChannel.jp",
        "name": "ショップチャンネル",
        "logo": "https://www.shopch.jp/com/images/common/logo_2021.png",
        "group": "通販",
        "url": "https://stream3.shopch.jp/HLS/master.m3u8",
    },
    {
        "id": "QVC.jp",
        "name": "QVC",
        "logo": "https://i.imgur.com/6TWUVrh.png",
        "group": "通販",
        "url": "https://d1flvb4iqlercm.cloudfront.net/live/live_1080p_2nd.m3u8",
    },
    {
        "id": "GSTV.jp",
        "name": "GSTV",
        "logo": "https://i.imgur.com/ECnVG5I.png",
        "group": "通販",
        "url": "https://japaneast.av.mk.io/mediakindcdn-mediakind/ca01a143-f823-4432-b670-c22ff9643ce4/index.qfm/manifest(format=m3u8-cmaf)",
    },
    # --- 天気 ---
    {
        "id": "Weathernews.jp",
        "name": "ウェザーニュースLiVE",
        "logo": "https://i.imgur.com/A8uRSTS.png",
        "group": "天気",
        "url": "https://rch01e-alive-hls.akamaized.net/38fb45b25cdb05a1/out/v1/4e907bfabc684a1dae10df8431a84d21/index.m3u8",
    },
    # --- 宗教 ---
    {
        "id": "CGNTVJapan.jp",
        "name": "CGNTV Japan",
        "logo": "https://i.imgur.com/5LNZeVq.png",
        "group": "宗教",
        "url": "https://d2p4mrcwl6ly4.cloudfront.net/out/v1/8d50f69fdbbf411a8d302743e4263716/CGNWebLiveJP.m3u8",
        "referrer": "http://japan.cgntv.net/HD_player_jp.html",
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
            f'#EXTM3U url-tvg="{EPG}"',
            "# tamaTV Japan collection — public HLS only. tamaTV does not host these streams.",
            "# Groups: ニュース, 地上波, アニメ, 通販, 天気, 宗教.",
            "# Kept: NHK World, Rakuten FAST news/MX, Aniplus FAST, shopping/weather/religious, working Tokyo terrestrial.",
            "# Dropped: gitee private-IP/token CS, Free-TV naori/willfonk, dead NTV News24 CDNs, DASH/ClearKey.",
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
