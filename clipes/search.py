"""语义搜索：输入问题，返回最相关的块。

    python -m clipes.search                  # 连续提问模式，输入空行退出
    python -m clipes.search "你的问题"        # 只问一次
"""
import sys
import time

import chromadb
from sentence_transformers import SentenceTransformer

from .chunk import fmt_time
from .config import COLLECTION, DB_PATH, MODEL_NAME

TOP_K = 10


def load():
    model = SentenceTransformer(MODEL_NAME, device="cuda")
    col = chromadb.PersistentClient(path=str(DB_PATH)).get_collection(COLLECTION)
    return model, col


def search(model, col, query, k=TOP_K):
    """返回最相关的 k 块：[{chunk_id, text, score, video_id, channel, title, url, start, end}, ...]"""
    emb = model.encode([query], normalize_embeddings=True)
    res = col.query(query_embeddings=emb.tolist(), n_results=k,
                    include=["documents", "metadatas", "distances"])
    hits = []
    for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0],
                                    res["metadatas"][0], res["distances"][0]):
        hits.append({"chunk_id": cid, "text": doc, "score": 1 - dist, **meta})
    return hits


def citation(h):
    return f"[{h['video_id']} · {h['channel']} {fmt_time(h['start'])}]"


def timestamped_url(h):
    """给一条检索结果拼出能直接跳到那个时间点的 YouTube 链接。"""
    url = h.get("url", "")
    if not url:
        return ""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}t={int(h['start'])}s"


def show(hits):
    for rank, h in enumerate(hits, 1):
        print(f"{rank}. {citation(h)}  相似度 {h['score']:.3f}")
        print(f"   {h['text'][:200]}...")


def main():
    model, col = load()
    if len(sys.argv) > 1:
        show(search(model, col, " ".join(sys.argv[1:])))
        return
    while True:
        q = input("\n问题（空行退出）> ").strip()
        if not q:
            break
        t0 = time.perf_counter()
        hits = search(model, col, q)
        print(f"（检索用时 {time.perf_counter() - t0:.2f} 秒）")
        show(hits)


if __name__ == "__main__":
    main()
