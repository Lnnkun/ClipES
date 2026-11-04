"""全项目共用的配置：搜索和建库必须用同一个模型。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_NAME = "BAAI/bge-m3"
DB_PATH = ROOT / "chroma_db"
COLLECTION = "clipes_chunks"
DATA_DIR = ROOT / "data"
CHUNKS_PATH = DATA_DIR / "chunks.jsonl"
VIDEOS_CSV = DATA_DIR / "videos.csv"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
UPLOADS_DIR = DATA_DIR / "uploads"
