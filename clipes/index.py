"""把 data/chunks.jsonl 里的所有块向量化，存进 Chroma。

    python -m clipes.index
每次运行都会完全重建索引。
"""
import json
import time

import chromadb
from sentence_transformers import SentenceTransformer

from .config import CHUNKS_PATH, COLLECTION, DB_PATH, MODEL_NAME

BATCH = 16


def main():
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f]
    print(f"读到 {len(chunks)} 块")

    t0 = time.perf_counter()
    model = SentenceTransformer(MODEL_NAME, device="cuda")
    print(f"模型加载 {time.perf_counter() - t0:.1f} 秒，设备 {model.device}")

    client = chromadb.PersistentClient(path=str(DB_PATH))
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass  # 第一次运行时还没有这个集合
    col = client.create_collection(COLLECTION, configuration={"hnsw": {"space": "cosine"}})

    t1 = time.perf_counter()
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        embs = model.encode([c["text"] for c in batch], batch_size=BATCH,
                            normalize_embeddings=True)
        col.add(
            ids=[c["chunk_id"] for c in batch],
            embeddings=embs.tolist(),
            documents=[c["text"] for c in batch],
            metadatas=[{
                "video_id": c["video_id"],
                "channel": c["channel"],
                "title": c["title"],
                "url": c.get("url", ""),
                "start": c["start"],
                "end": c["end"],
            } for c in batch],
        )
        if (i // BATCH) % 10 == 0:
            print(f"  已处理 {min(i + BATCH, len(chunks))} / {len(chunks)}")

    elapsed = time.perf_counter() - t1
    print(f"\n建索引耗时 {elapsed:.1f} 秒（{len(chunks) / elapsed:.1f} 块/秒）")
    print(f"库里共 {col.count()} 块，保存在 {DB_PATH}")


if __name__ == "__main__":
    main()
