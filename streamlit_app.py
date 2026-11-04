"""ClipES 前端：Streamlit 网页，调用 api.py 提供的后端。

    streamlit run streamlit_app.py
需要先在另一个终端跑：uvicorn api:app --reload
"""
import os

import requests
import streamlit as st

API_BASE = os.getenv("CLIPES_API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="ClipES", page_icon="🎬")
st.title("🎬 ClipES")
st.caption("西语 AI 科普视频知识库 — 提问即答，带时间戳出处")

tab_ask, tab_videos, tab_import = st.tabs(["问答", "视频库", "导入视频"])

with tab_ask:
    question = st.text_input(
        "输入你的问题（西语或中文都可以）",
        placeholder="¿Qué es un embedding? / 什么是 embedding？",
    )
    ask_clicked = st.button("提问", type="primary")

    if ask_clicked and question.strip():
        with st.spinner("检索 + 生成中..."):
            try:
                resp = requests.post(f"{API_BASE}/ask", json={"question": question}, timeout=60)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                st.error(f"请求失败，确认后端是否已启动（uvicorn api:app --reload）：{e}")
                data = None

        if data:
            st.markdown(data["answer"] or "_没有拿到回答_")
            st.caption(
                f"检索 {data['search_seconds']:.2f}s + 生成 {data['generate_seconds']:.2f}s"
            )
            if data["citations"]:
                st.subheader("出处")
                for c in data["citations"]:
                    link = c["timestamped_url"] or c["url"]
                    if link:
                        st.markdown(f"- [{c['label']}]({link})　相似度 {c['score']:.3f}")
                    else:
                        st.markdown(f"- {c['label']}　相似度 {c['score']:.3f}")
    elif ask_clicked:
        st.warning("先输入一个问题")

with tab_videos:
    try:
        resp = requests.get(f"{API_BASE}/videos", timeout=10)
        resp.raise_for_status()
        videos = resp.json()
    except Exception as e:
        st.error(f"请求失败，确认后端是否已启动：{e}")
        videos = []

    st.caption(f"库里共 {len(videos)} 个视频")
    for v in videos:
        st.markdown(
            f"**{v.get('title', '')}** — {v.get('channel', '')} · "
            f"{v.get('duration_min', '?')} 分钟  \n[{v.get('url', '')}]({v.get('url', '')})"
        )

with tab_import:
    st.caption("上传一个西语视频，自动转录 + 生成标题 + 收录进知识库，完成后立刻可以在「问答」里搜到。")
    st.caption("视频可能比较长，转录 + AI 生成 + 重建索引这几步会花一两分钟，请耐心等待。")

    uploaded = st.file_uploader("选择视频文件", type=["mp4", "mov", "mkv", "mp3", "wav", "m4a"])
    channel = st.text_input("频道 / 来源名称", placeholder="比如你自己的频道名，或原视频的频道")
    topic = st.text_input("主题（可选）", placeholder="比如：大模型原理")
    import_clicked = st.button("开始导入", type="primary")

    if import_clicked:
        if not uploaded:
            st.warning("先选择一个视频文件")
        elif not channel.strip():
            st.warning("频道 / 来源名称不能为空")
        else:
            with st.spinner("转录中（Whisper）→ AI 生成标题中 → 重新建索引中..."):
                try:
                    files = {"file": (uploaded.name, uploaded.getvalue())}
                    data = {"channel": channel, "topic": topic}
                    resp = requests.post(
                        f"{API_BASE}/ingest/add_video", files=files, data=data, timeout=1800
                    )
                    resp.raise_for_status()
                    result = resp.json()
                except Exception as e:
                    st.error(f"导入失败：{e}")
                    result = None

            if result:
                st.success(
                    f"导入成功：{result['video_id']} 《{result['title']}》"
                    f"（{result['duration_min']} 分钟，库里现在共 {result['chunks_total']} 个检索块）"
                )
                st.info("去「问答」标签页试试问一个这个视频里的问题。")
