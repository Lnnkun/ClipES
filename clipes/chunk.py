"""把字幕合并成 30-60 秒的块，保存到 data/chunks.jsonl。

    python -m clipes.chunk
"""
import json
import statistics

from .config import CHUNKS_PATH
from .ingest import load_all

# ---- 可调参数 ----
MIN_SEC = 30      # 一块至少这么长，才允许在句子结尾处切
MAX_SEC = 60      # 一块最长这么长，到了就强制切
OVERLAP_SEC = 10  # 下一块开头重复上一块最后这么多秒

SENTENCE_END = (".", "?", "!", "…")


def ends_sentence(text):
    return text.rstrip().endswith(SENTENCE_END)


def fmt_time(sec):
    """357.2 -> '05:57'"""
    m, s = divmod(int(sec), 60)
    return f"{m:02d}:{s:02d}"


def make_chunk(items):
    first = items[0]
    return {
        "video_id": first["video_id"],
        "channel": first["channel"],
        "title": first["title"],
        "url": first.get("url", ""),
        "start": first["start"],
        "end": items[-1]["end"],
        "text": " ".join(e["text"] for e in items),
    }


def chunk_video(entries):
    """entries：同一个视频、按时间排序的字幕列表。返回块的列表。"""
    chunks = []
    n = len(entries)
    i = 0
    while i < n:
        start = entries[i]["start"]
        j = i  # entries[i:j] 是这一块包含的字幕
        while j < n:
            j += 1
            dur = entries[j - 1]["end"] - start
            if dur >= MAX_SEC:
                break
            if dur >= MIN_SEC and ends_sentence(entries[j - 1]["text"]):
                break
        chunks.append(make_chunk(entries[i:j]))
        if j >= n:
            break
        # 下一块从哪条字幕开始：往回退，直到重叠约 OVERLAP_SEC 秒
        k = j
        while k - 1 > i and entries[j - 1]["end"] - entries[k - 1]["start"] <= OVERLAP_SEC:
            k -= 1
        i = k
    for idx, c in enumerate(chunks):
        c["chunk_id"] = f"{c['video_id']}_{idx:04d}"
    return chunks


def main():
    by_video = {}
    for e in load_all():
        by_video.setdefault(e["video_id"], []).append(e)

    all_chunks = []
    print(f"{'视频':<6}{'块数':>5}{'平均秒':>8}{'最短':>6}{'最长':>6}{'最多字符':>9}")
    for vid, entries in by_video.items():
        chunks = chunk_video(entries)
        durs = [c["end"] - c["start"] for c in chunks]
        longest_chars = max(len(c["text"]) for c in chunks)
        print(f"{vid:<6}{len(chunks):>5}{statistics.mean(durs):>8.0f}"
              f"{min(durs):>6.0f}{max(durs):>6.0f}{longest_chars:>9}")
        all_chunks.extend(chunks)

    with open(CHUNKS_PATH, "w", encoding="utf-8", newline="\n") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"\n共 {len(all_chunks)} 块，已保存到 {CHUNKS_PATH}")


if __name__ == "__main__":
    main()
