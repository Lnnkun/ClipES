"""ClipES 后端 API：统一包装转录+生成简介（原 VideoListo）和检索+RAG 问答（原 VideoBusca）两套流程。

    uvicorn api:app --reload
启动后访问 http://127.0.0.1:8000/docs 看接口文档。
"""
import shutil
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from clipes import ask as ask_mod
from clipes import chunk as chunk_mod
from clipes import index as index_mod
from clipes import ingest as ingest_mod
from clipes import meta as meta_mod
from clipes import search as search_mod
from clipes import transcribe as transcribe_mod
from clipes.config import ROOT, UPLOADS_DIR, TRANSCRIPTS_DIR

load_dotenv(ROOT / ".env")

app = FastAPI(title="ClipES API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_model = None
_col = None


def get_model_col():
    """向量模型 + Chroma 集合只在第一次请求时加载，之后复用。"""
    global _model, _col
    if _model is None:
        _model, _col = search_mod.load()
    return _model, _col


def invalidate_index_cache():
    """重建索引之后，让下一次请求重新加载模型和 Chroma 集合（否则还指着被删掉的旧集合）。"""
    global _model, _col
    _model, _col = None, None


class AskRequest(BaseModel):
    question: str
    top_k: Optional[int] = None


class Citation(BaseModel):
    video_id: str
    channel: str
    title: str
    url: str
    start: float
    score: float
    label: str
    timestamped_url: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    search_seconds: float
    generate_seconds: float


class TranscribeRequest(BaseModel):
    video_path: str


class ChapterOut(BaseModel):
    time: str
    title: str


class TranscribeResponse(BaseModel):
    srt_path: str
    titles: list[str]
    description: str
    chapters: list[ChapterOut]
    tags: list[str]
    warnings: list[str]
    cost_usd: float


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/videos")
def list_videos():
    """视频库列表，来自 data/videos.csv。"""
    return list(ingest_mod.load_videos().values())


@app.post("/ask", response_model=AskResponse)
def ask_question(req: AskRequest):
    """核心功能：问一个问题，拿到带时间戳出处的回答（原 VideoBusca）。"""
    if not req.question.strip():
        raise HTTPException(400, "问题不能为空")
    model, col = get_model_col()
    k = req.top_k or ask_mod.TOP_K
    answer, hits, t_search, t_llm = ask_mod.ask(model, col, req.question, k)
    citations = [
        Citation(
            video_id=h["video_id"], channel=h["channel"], title=h["title"],
            url=h.get("url", ""), start=h["start"], score=h["score"],
            label=search_mod.citation(h), timestamped_url=search_mod.timestamped_url(h),
        )
        for h in hits
    ]
    return AskResponse(answer=answer, citations=citations, search_seconds=t_search, generate_seconds=t_llm)


@app.post("/ingest/transcribe", response_model=TranscribeResponse)
def transcribe_video(req: TranscribeRequest):
    """收录一个新视频：本地 Whisper 转录 + 大模型生成简介/章节/标签（原 VideoListo）。

    只转录+生成，不会自动切块重建索引——新视频要进入 /ask 的检索范围，
    还需另外跑一次 `python -m clipes.chunk` 和 `python -m clipes.index`。
    """
    video_path = Path(req.video_path)
    if not video_path.exists():
        raise HTTPException(404, f"找不到文件：{video_path}")

    segments = transcribe_mod.transcribe(str(video_path))
    srt_path = video_path.with_suffix(".srt")
    transcribe_mod.generate_srt(segments, str(srt_path))

    try:
        video_meta, cost = meta_mod.generate_meta(segments)
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    return TranscribeResponse(
        srt_path=str(srt_path),
        titles=video_meta.titles,
        description=video_meta.description,
        chapters=[ChapterOut(time=c.time, title=c.title) for c in video_meta.chapters],
        tags=video_meta.tags,
        warnings=meta_mod.check_chapters(video_meta),
        cost_usd=cost,
    )


class AddVideoResponse(BaseModel):
    video_id: str
    title: str
    duration_min: float
    chunks_total: int


@app.post("/ingest/add_video", response_model=AddVideoResponse)
async def add_video(
    file: UploadFile = File(...),
    channel: str = Form(...),
    topic: str = Form(""),
):
    """用户自己导入一个视频：转录 + AI 生成标题 + 写入视频库 + 重新建索引。

    导入完成后这个视频立刻可以被 /ask 检索到。视频本身不会保留在仓库里，
    只保留转录出来的 .srt 字幕（和其它视频一样）。
    """
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    video_id = ingest_mod.next_video_id()
    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
    video_path = UPLOADS_DIR / f"{video_id}{suffix}"
    with open(video_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        segments = transcribe_mod.transcribe(str(video_path))
    finally:
        video_path.unlink(missing_ok=True)  # 原始视频文件不需要留着，字幕才是我们要的

    if not segments:
        raise HTTPException(422, "没有识别出任何内容，确认视频里有西语语音")

    srt_path = TRANSCRIPTS_DIR / f"{video_id}.srt"
    transcribe_mod.generate_srt(segments, str(srt_path))

    try:
        video_meta, _cost = meta_mod.generate_meta(segments)
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    duration_min = round(segments[-1]["end"] / 60, 1)
    ingest_mod.append_video_row(
        video_id, channel=channel, title=video_meta.titles[0],
        duration_min=duration_min, topic=topic, notes="用户导入",
    )

    chunk_mod.main()
    index_mod.main()
    invalidate_index_cache()

    with open(chunk_mod.CHUNKS_PATH, encoding="utf-8") as f:
        chunks_total = sum(1 for _ in f)

    return AddVideoResponse(
        video_id=video_id, title=video_meta.titles[0],
        duration_min=duration_min, chunks_total=chunks_total,
    )
