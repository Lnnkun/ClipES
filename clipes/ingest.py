"""读取 data/transcripts/*.srt，输出统一格式的字幕列表。

直接运行可以看到每个视频的统计：
    python -m clipes.ingest
"""
import csv
import re

from .config import TRANSCRIPTS_DIR, VIDEOS_CSV

TIME_RE = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})")


def to_seconds(t):
    """'00:05:57,200' -> 357.2"""
    h, m, s, ms = TIME_RE.match(t.strip()).groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(path):
    """把一个 .srt 文件解析成 [{start, end, text}, ...]"""
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    entries = []
    for block in re.split(r"\n\s*\n", text):
        lines = block.split("\n")
        if len(lines) < 3 or "-->" not in lines[1]:
            continue  # 不是正常的字幕块，跳过
        start_str, end_str = lines[1].split("-->")
        body = " ".join(l.strip() for l in lines[2:]).strip()
        if not body:
            continue  # 空字幕丢掉
        entries.append({
            "start": round(to_seconds(start_str), 2),
            "end": round(to_seconds(end_str), 2),
            "text": body,
        })
    return entries


VIDEOS_FIELDS = ["id", "topic_id", "topic", "channel", "title", "url", "duration_min", "notes"]


def load_videos():
    """读 videos.csv，返回 {'v14': {...一行信息...}, ...}"""
    with open(VIDEOS_CSV, encoding="utf-8-sig", newline="") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def next_video_id():
    """根据现有 id（v01, v02, ...）算出下一个可用 id。"""
    videos = load_videos()
    nums = [int(vid[1:]) for vid in videos if vid[1:].isdigit()]
    return f"v{(max(nums, default=0) + 1):02d}"


def append_video_row(video_id, channel, title, duration_min, topic="", url="", notes=""):
    """往 videos.csv 追加一行新视频。"""
    is_new_file = not VIDEOS_CSV.exists()
    with open(VIDEOS_CSV, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=VIDEOS_FIELDS)
        if is_new_file:
            w.writeheader()
        w.writerow({
            "id": video_id, "topic_id": "", "topic": topic, "channel": channel,
            "title": title, "url": url, "duration_min": duration_min, "notes": notes,
        })


def load_all():
    """读取所有有字幕的视频，返回统一格式的列表。没有 .srt 的视频自动跳过。"""
    videos = load_videos()
    entries = []
    for srt in sorted(TRANSCRIPTS_DIR.glob("v*.srt")):
        vid = srt.stem
        info = videos.get(vid)
        if info is None:
            print(f"[警告] {srt.name} 在 videos.csv 里找不到，跳过")
            continue
        for e in parse_srt(srt):
            e["video_id"] = vid
            e["channel"] = info["channel"]
            e["title"] = info["title"]
            e["url"] = info.get("url", "")
            entries.append(e)
    return entries


if __name__ == "__main__":
    entries = load_all()
    print(f"{'视频':<6}{'字幕条数':>8}{'时长(分)':>10}  频道")
    by_video = {}
    for e in entries:
        by_video.setdefault(e["video_id"], []).append(e)
    for vid, items in by_video.items():
        minutes = items[-1]["end"] / 60
        print(f"{vid:<6}{len(items):>8}{minutes:>10.1f}  {items[0]['channel']}")
    print(f"\n共 {len(by_video)} 个视频，{len(entries)} 条字幕")
