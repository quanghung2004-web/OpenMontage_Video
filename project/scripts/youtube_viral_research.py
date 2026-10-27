#!/usr/bin/env python3
"""Analyze a YouTube channel, then find viral videos that match what already
works on that channel.

Steps:
  1. Pull every upload of the channel (YouTube Data API v3) with stats.
  2. Score each upload against the channel's own median (views/day and
     total views) to find the "winners".
  3. Extract the keywords/phrases/tags that distinguish winners from the
     rest, plus the winning format (Shorts vs long-form, typical length).
  4. Use those phrases as search seeds to find recent high-velocity videos
     from OTHER channels in the same niche/format, and rank them by
     velocity, outlier ratio (views / channel subscribers) and topic match.
  5. Write a JSON dump and a Markdown report.

Usage:
  export YOUTUBE_API_KEY=...        # never commit the key
  python3 project/scripts/youtube_viral_research.py \
      --channel UCKmCKddwkQ-NJ82TZl-Rq0Q --days 90 --region US

Quota: ~1 unit per 50 uploads + 100 units per search query (default 10
queries) -> roughly 1,100-1,300 of the 10,000 daily units.
"""

import argparse
import json
import math
import os
import re
import statistics
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://www.googleapis.com/youtube/v3/"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "research"

STOPWORDS = set("""
a an the and or but of to in on at for with from by is are was were be been it
its this that these those you your we our they their he she his her i me my
how what why when who which will can do does did not no yes vs v s t just
all more most new full part ep episode official video videos shorts short
than into about over after before up out so if as there here one two
và của là có cho với những các một này đó khi được không thì mà để trong
ra vào lại cũng như người đã sẽ đang rất nhất từ theo bị nhưng nên hay
ở về tại bạn tôi chúng ta họ anh em video phần tập
""".split())


def api_get(endpoint, key, **params):
    params["key"] = key
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        sys.exit(f"YouTube API error {e.code} on {endpoint}: {body[:500]}")


def parse_duration(iso):
    """ISO-8601 duration (PT1H2M3S) -> seconds."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def age_days(published_at, now):
    ts = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    return max((now - ts).total_seconds() / 86400, 1.0)


def tokens(text):
    words = re.findall(r"[^\W\d_]+", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def ngrams(text, n_max=3):
    toks = tokens(text)
    grams = []
    for n in range(1, n_max + 1):
        for i in range(len(toks) - n + 1):
            grams.append(" ".join(toks[i:i + n]))
    return grams


def chunks(seq, n=50):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def fetch_videos(ids, key):
    out = []
    for batch in chunks(ids):
        data = api_get("videos", key, part="snippet,statistics,contentDetails",
                       id=",".join(batch), maxResults=50)
        out.extend(data.get("items", []))
    return out


def fetch_channels(ids, key):
    out = {}
    for batch in chunks(list(ids)):
        data = api_get("channels", key, part="snippet,statistics",
                       id=",".join(batch), maxResults=50)
        for it in data.get("items", []):
            out[it["id"]] = it
    return out


def video_record(item, now):
    st = item.get("statistics", {})
    sn = item["snippet"]
    views = int(st.get("viewCount", 0))
    likes = int(st.get("likeCount", 0))
    comments = int(st.get("commentCount", 0))
    days = age_days(sn["publishedAt"], now)
    dur = parse_duration(item.get("contentDetails", {}).get("duration"))
    return {
        "id": item["id"],
        "url": f"https://www.youtube.com/watch?v={item['id']}",
        "title": sn["title"],
        "channel_id": sn["channelId"],
        "channel_title": sn.get("channelTitle", ""),
        "published_at": sn["publishedAt"],
        "tags": sn.get("tags", []),
        "category_id": sn.get("categoryId"),
        "language": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage"),
        "duration_s": dur,
        "is_short": dur <= 180,
        "views": views,
        "likes": likes,
        "comments": comments,
        "age_days": round(days, 1),
        "views_per_day": round(views / days, 1),
        "engagement": round((likes + comments) / views, 4) if views else 0.0,
    }


def analyze_channel(channel_id, key, max_uploads, now):
    ch = api_get("channels", key, part="snippet,statistics,contentDetails",
                 id=channel_id).get("items")
    if not ch:
        sys.exit(f"Channel {channel_id} not found.")
    ch = ch[0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]

    ids, page = [], None
    while len(ids) < max_uploads:
        params = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50}
        if page:
            params["pageToken"] = page
        data = api_get("playlistItems", key, **params)
        ids += [it["contentDetails"]["videoId"] for it in data.get("items", [])]
        page = data.get("nextPageToken")
        if not page:
            break
    videos = [video_record(v, now) for v in fetch_videos(ids[:max_uploads], key)]
    if not videos:
        sys.exit("Channel has no public uploads to analyze.")

    med_vpd = statistics.median(v["views_per_day"] for v in videos) or 1
    med_views = statistics.median(v["views"] for v in videos) or 1
    for v in videos:
        # Blend lifetime and velocity so old evergreen hits and fresh spikes both count.
        v["perf_score"] = round(0.5 * v["views"] / med_views + 0.5 * v["views_per_day"] / med_vpd, 2)
    videos.sort(key=lambda v: v["perf_score"], reverse=True)

    n_top = max(3, math.ceil(len(videos) * 0.2))
    winners = [v for v in videos[:n_top] if v["perf_score"] >= 1.2] or videos[:3]
    rest = [v for v in videos if v not in winners]

    top_grams = Counter(g for v in winners for g in set(ngrams(v["title"]) + [t.lower() for t in v["tags"]]))
    rest_grams = Counter(g for v in rest for g in set(ngrams(v["title"]) + [t.lower() for t in v["tags"]]))
    keywords = []
    for g, c in top_grams.items():
        lift = (c / len(winners)) / ((rest_grams[g] + 1) / (len(rest) + 1))
        keywords.append({"phrase": g, "in_winners": c, "in_rest": rest_grams[g],
                         "lift": round(lift, 2), "score": round(lift * math.log1p(c) * (1 + 0.3 * g.count(" ")), 3)})
    keywords.sort(key=lambda k: k["score"], reverse=True)

    shorts_share = sum(v["is_short"] for v in winners) / len(winners)
    win_durs = sorted(v["duration_s"] for v in winners)
    langs = Counter(v["language"] for v in winners if v["language"])
    cats = Counter(v["category_id"] for v in winners if v["category_id"])

    return {
        "channel": {
            "id": channel_id,
            "title": ch["snippet"]["title"],
            "description": ch["snippet"].get("description", ""),
            "country": ch["snippet"].get("country"),
            "subscribers": int(ch["statistics"].get("subscriberCount", 0)),
            "total_views": int(ch["statistics"].get("viewCount", 0)),
            "video_count": int(ch["statistics"].get("videoCount", 0)),
        },
        "analyzed_uploads": len(videos),
        "median_views": med_views,
        "median_views_per_day": med_vpd,
        "winners": winners,
        "all_videos": videos,
        "keywords": keywords[:40],
        "format": {
            "winner_shorts_share": round(shorts_share, 2),
            "winner_median_duration_s": win_durs[len(win_durs) // 2],
            "dominant_language": langs.most_common(1)[0][0] if langs else None,
            "dominant_category": cats.most_common(1)[0][0] if cats else None,
        },
    }


def pick_seed_queries(profile, n, extra):
    """Highest-scoring phrases, preferring multi-word ones and dropping
    phrases fully contained in an already chosen one."""
    chosen = list(extra)

    def overlaps(q):
        qs = set(q.split())
        for c in chosen:
            cs = set(c.split())
            if qs <= cs or cs <= qs or len(qs & cs) / len(qs | cs) >= 0.5:
                return True
        return False

    def add(q):
        if q and len(chosen) < n and not overlaps(q):
            chosen.append(q)

    ranked = sorted(profile["keywords"], key=lambda k: k["score"], reverse=True)
    for k in ranked:
        if " " in k["phrase"]:
            add(k["phrase"])
    # Make sure every winner's topic is searched, even one-off hits.
    for v in profile["winners"]:
        add(" ".join(tokens(v["title"])[:5]))
    for k in ranked:
        add(k["phrase"])
    return chosen[:n]


def search_viral(profile, queries, key, days, region, max_per_query, now):
    fmt = profile["format"]
    if fmt["winner_shorts_share"] >= 0.6:
        duration_filter = "short"      # < 4 min
    elif fmt["winner_shorts_share"] <= 0.4 and fmt["winner_median_duration_s"] >= 1200:
        duration_filter = "long"       # > 20 min
    elif fmt["winner_shorts_share"] <= 0.4:
        duration_filter = "medium"     # 4-20 min
    else:
        duration_filter = "any"
    after = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    found = {}
    for q in queries:
        params = {"part": "snippet", "q": q, "type": "video", "order": "viewCount",
                  "publishedAfter": after, "maxResults": max_per_query,
                  "videoDuration": duration_filter}
        if region:
            params["regionCode"] = region
        if fmt["dominant_language"]:
            params["relevanceLanguage"] = fmt["dominant_language"].split("-")[0]
        for it in api_get("search", key, **params).get("items", []):
            vid = it["id"].get("videoId")
            if vid and it["snippet"]["channelId"] != profile["channel"]["id"]:
                found.setdefault(vid, set()).add(q)

    videos = [video_record(v, now) for v in fetch_videos(list(found), key)]
    chans = fetch_channels({v["channel_id"] for v in videos}, key)
    kw_weights = {k["phrase"]: k["score"] for k in profile["keywords"]}
    # Topic match = best weighted phrase overlap with any single winner, so a
    # secondary winning topic counts as fully as the channel's dominant one.
    winner_grams = []
    for w in profile["winners"]:
        g = {p for p in set(ngrams(w["title"]) + [t.lower() for t in w["tags"]]) if p in kw_weights}
        if g:
            winner_grams.append((g, sum(sorted((kw_weights[p] for p in g), reverse=True)[:5])))

    for v in videos:
        subs = int(chans.get(v["channel_id"], {}).get("statistics", {}).get("subscriberCount", 0) or 0)
        v["channel_subscribers"] = subs
        v["matched_queries"] = sorted(found[v["id"]])
        v["outlier_ratio"] = round(v["views"] / max(subs, 1000), 2)
        grams = set(ngrams(v["title"]) + [t.lower() for t in v["tags"]])
        v["topic_match"] = round(max((min(sum(kw_weights[p] for p in grams & g) / tot, 1.0)
                                      for g, tot in winner_grams), default=0.0), 2)
        v["format_match"] = v["is_short"] == (fmt["winner_shorts_share"] >= 0.5)
        v["viral_score"] = round(
            math.log10(v["views_per_day"] + 1) * 1.0
            + math.log10(v["outlier_ratio"] + 1) * 1.5
            + v["topic_match"] * 2.0
            + (0.5 if v["format_match"] else 0)
            + min(v["engagement"] * 20, 1.0), 3)
    videos.sort(key=lambda v: v["viral_score"], reverse=True)
    return {"duration_filter": duration_filter, "published_after": after, "videos": videos}


def next_video_ideas(profile, viral, n=5):
    """Pair top on-topic viral videos with the channel winner sharing the most
    keyword phrases; one idea per winner so ideas cover different topics."""
    kw = {k["phrase"] for k in profile["keywords"]}
    ideas, seen = [], set()
    for v in viral["videos"]:
        if v["topic_match"] < 0.2:
            continue
        vg = set(ngrams(v["title"]) + [t.lower() for t in v["tags"]]) & kw
        best, shared = None, set()
        for w in profile["winners"]:
            s = vg & set(ngrams(w["title"]) + [t.lower() for t in w["tags"]])
            if len(s) > len(shared):
                best, shared = w, s
        topic = sorted(shared, key=len, reverse=True)[:3]
        tag = best["id"] if best else v["id"]
        if tag in seen:
            continue
        seen.add(tag)
        ideas.append({"viral": v, "winner": best, "shared": topic})
        if len(ideas) >= n:
            break
    return ideas


def fmt_n(n):
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= div:
            return f"{n / div:.1f}{suf}"
    return str(int(n))


def fmt_dur(s):
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def write_report(profile, queries, viral, path, top_n):
    c = profile["channel"]
    f = profile["format"]
    L = [f"# Phân tích kênh & video viral liên quan — {c['title']}", "",
         f"_Tạo lúc {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}_", "",
         "## 1. Tổng quan kênh", "",
         f"- Subscribers: **{fmt_n(c['subscribers'])}** · Tổng view: **{fmt_n(c['total_views'])}** · Số video: **{c['video_count']}**",
         f"- Đã phân tích: {profile['analyzed_uploads']} video · View trung vị: {fmt_n(profile['median_views'])} · View/ngày trung vị: {profile['median_views_per_day']:.1f}",
         f"- Định dạng của video hiệu quả: Shorts chiếm {f['winner_shorts_share']:.0%}, thời lượng trung vị {fmt_dur(f['winner_median_duration_s'])}",
         f"- Ngôn ngữ chính: {f['dominant_language'] or 'không khai báo'} · Category ID: {f['dominant_category']}", "",
         "## 2. Video đang hiệu quả nhất của kênh", "",
         "Điểm hiệu quả = trung bình của (view / trung vị kênh) và (view/ngày / trung vị kênh). >1 là tốt hơn mức thường của kênh.", "",
         "| # | Video | View | View/ngày | Tương tác | Thời lượng | Điểm |",
         "|---|---|---|---|---|---|---|"]
    for i, v in enumerate(profile["winners"], 1):
        L.append(f"| {i} | [{v['title'].replace('|', '/')}]({v['url']}) | {fmt_n(v['views'])} | {v['views_per_day']:.0f} | {v['engagement']:.1%} | {fmt_dur(v['duration_s'])} | {v['perf_score']}× |")
    L += ["", "## 3. Chủ đề / từ khóa làm nên video hiệu quả", "",
          "`lift` = tần suất trong video hiệu quả so với các video còn lại.", "",
          "| Cụm từ | Trong video hiệu quả | Trong video còn lại | Lift |", "|---|---|---|---|"]
    for k in profile["keywords"][:15]:
        L.append(f"| {k['phrase']} | {k['in_winners']} | {k['in_rest']} | {k['lift']} |")
    L += ["", "## 4. Truy vấn tìm kiếm đã dùng", "",
          f"Lọc: đăng sau {viral['published_after'][:10]}, thời lượng `{viral['duration_filter']}`, sắp xếp theo view, loại trừ kênh của bạn.", ""]
    L += [f"- `{q}`" for q in queries]
    L += ["", "## 5. Video viral bám sát nội dung hiệu quả của kênh", "",
          "Viral score kết hợp tốc độ view/ngày, tỉ lệ đột biến (view ÷ subscriber của kênh đăng), mức khớp chủ đề với video hiệu quả của bạn, khớp định dạng và tương tác.", "",
          "| # | Video | Kênh (subs) | View | View/ngày | Đột biến | Khớp chủ đề | Thời lượng | Score |",
          "|---|---|---|---|---|---|---|---|---|"]
    for i, v in enumerate(viral["videos"][:top_n], 1):
        L.append(f"| {i} | [{v['title'].replace('|', '/')}]({v['url']}) | {v['channel_title'].replace('|', '/')} ({fmt_n(v['channel_subscribers'])}) | {fmt_n(v['views'])} | {fmt_n(v['views_per_day'])} | {v['outlier_ratio']}× | {v['topic_match']:.0%} | {fmt_dur(v['duration_s'])} | {v['viral_score']} |")
    L += ["", "## 6. Ý tưởng cho video tiếp theo", "",
          "Mỗi ý tưởng ghép một video viral (đã chứng minh nhu cầu) với video hiệu quả nhất của bạn có cùng chủ đề — làm theo định dạng của kênh bạn.", ""]
    for i, idea in enumerate(next_video_ideas(profile, viral), 1):
        v, w = idea["viral"], idea["winner"]
        L += [f"### Ý tưởng {i}: {', '.join(idea['shared']) or v['title']}", "",
              f"- Bằng chứng viral: [{v['title']}]({v['url']}) — {fmt_n(v['views'])} view, {fmt_n(v['views_per_day'])}/ngày, đột biến {v['outlier_ratio']}×",
              f"- Bám theo video hiệu quả của bạn: [{w['title']}]({w['url']}) ({w['perf_score']}×)" if w else "- Chủ đề mới gần với từ khóa hiệu quả của kênh",
              f"- Định dạng đề xuất: {'Shorts' if profile['format']['winner_shorts_share'] >= 0.5 else 'video dài'} ~{fmt_dur(profile['format']['winner_median_duration_s'])}",
              ""]
    L += ["## 7. Gợi ý hành động", "",
          "- Ưu tiên video có **Đột biến ≥ 3×** và **Khớp chủ đề ≥ 50%**: kênh nhỏ mà vẫn viral nghĩa là chủ đề/tiêu đề tự kéo view, không nhờ lượng sub.",
          "- Giữ định dạng giống các video hiệu quả của bạn (Shorts vs dài, thời lượng ở mục 1) khi làm lại chủ đề.",
          "- So sánh tiêu đề/thumbnail của video viral với video hiệu quả nhất của bạn để rút ra hook chung.",
          "- Chạy lại script mỗi 1–2 tuần (`--days 30`) để bắt xu hướng mới.", ""]
    path.write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", default="UCKmCKddwkQ-NJ82TZl-Rq0Q")
    ap.add_argument("--days", type=int, default=90, help="only search videos published in the last N days")
    ap.add_argument("--region", default=None, help="regionCode for search, e.g. US or VN")
    ap.add_argument("--queries", type=int, default=10, help="number of search seeds (100 quota units each)")
    ap.add_argument("--extra-query", action="append", default=[], help="add your own search seed (repeatable)")
    ap.add_argument("--max-uploads", type=int, default=500)
    ap.add_argument("--per-query", type=int, default=25)
    ap.add_argument("--top", type=int, default=30, help="rows in the viral table")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        sys.exit("Set YOUTUBE_API_KEY (YouTube Data API v3 key) in the environment.")

    now = datetime.now(timezone.utc)
    profile = analyze_channel(args.channel, key, args.max_uploads, now)
    queries = pick_seed_queries(profile, args.queries, args.extra_query)
    viral = search_viral(profile, queries, key, args.days, args.region, args.per_query, now)

    args.out.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%d")
    (args.out / f"channel_{args.channel}_{stamp}.json").write_text(
        json.dumps({"profile": profile, "queries": queries, "viral": viral}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    report = args.out / f"viral_report_{args.channel}_{stamp}.md"
    write_report(profile, queries, viral, report, args.top)
    print(f"Channel: {profile['channel']['title']} — {len(profile['winners'])} winners, "
          f"{len(viral['videos'])} viral candidates\nReport: {report}")


if __name__ == "__main__":
    main()
