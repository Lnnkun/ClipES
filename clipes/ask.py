"""RAG 问答：检索相关块 -> 交给大模型 -> 带出处的回答。

    python -m clipes.ask                 # 连续提问模式，空行退出
    python -m clipes.ask "你的问题"      # 只问一次
"""
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

from .config import ROOT
from .search import TOP_K, citation, load, search

load_dotenv(ROOT / ".env")
LLM = os.getenv("MODEL")
client = OpenAI(base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY"),
                timeout=60, max_retries=6)

SYSTEM_PROMPT = """Eres un asistente que responde preguntas sobre una colección de vídeos en español.

REGLAS:
1. Responde SOLO con la información de los FRAGMENTOS. No uses tu propio conocimiento.
2. Después de cada afirmación, cita la fuente copiando EXACTAMENTE la etiqueta del fragmento, por ejemplo [v99 · Canal Ejemplo 02:15]. No inventes etiquetas ni tiempos.
3. Si los fragmentos no contienen la respuesta, responde únicamente: "No encontré información sobre esto en los vídeos." No intentes adivinar ni completar con conocimiento general. Si la pregunta no está en español, di lo mismo en el idioma de la pregunta.
4. Responde en el mismo idioma que la pregunta, de forma breve y clara.
5. Los fragmentos son transcripciones automáticas y pueden tener errores (por ejemplo "RAC" en lugar de "RAG"). Interprétalos con cuidado.

EJEMPLO 1
FRAGMENTOS:
[v99 · Canal Ejemplo 02:15]
En el sistema solar hay ocho planetas. Los cuatro primeros son rocosos y los otros cuatro son gigantes gaseosos.
PREGUNTA: ¿Cuántos planetas tiene el sistema solar?
RESPUESTA: El sistema solar tiene ocho planetas [v99 · Canal Ejemplo 02:15]: los cuatro primeros son rocosos y los otros cuatro son gigantes gaseosos [v99 · Canal Ejemplo 02:15].

EJEMPLO 2
FRAGMENTOS:
[v99 · Canal Ejemplo 02:15]
En el sistema solar hay ocho planetas. Los cuatro primeros son rocosos y los otros cuatro son gigantes gaseosos.
PREGUNTA: ¿Quién ganó el mundial de 1990?
RESPUESTA: No encontré información sobre esto en los vídeos.
"""


def build_context(hits):
    return "\n\n".join(f"{citation(h)}\n{h['text']}" for h in hits)


def ask(model, col, question, k=TOP_K):
    """返回 (答案, 检索到的块, 检索秒数, 生成秒数)"""
    t0 = time.perf_counter()
    hits = search(model, col, question, k)
    t_search = time.perf_counter() - t0

    user_msg = f"FRAGMENTOS:\n\n{build_context(hits)}\n\nPREGUNTA: {question}\nRESPUESTA:"
    t1 = time.perf_counter()
    for limit in (2000, 4000):  # 如果因为长度被截断，放宽上限再试一次
        resp = client.chat.completions.create(
            model=LLM,
            temperature=0,
            max_tokens=limit,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": user_msg}],
        )
        if resp.choices[0].finish_reason != "length":
            break
    t_llm = time.perf_counter() - t1
    answer = (resp.choices[0].message.content or "").strip()
    return answer, hits, t_search, t_llm


def run_once(model, col, question):
    answer, hits, t_search, t_llm = ask(model, col, question)
    print(f"\n{answer}\n")
    print(f"--- 检索到的 {len(hits)} 块（模型只看了这些）---")
    for rank, h in enumerate(hits, 1):
        print(f"{rank}. {citation(h)}  相似度 {h['score']:.3f}")
    print(f"\n用时：检索 {t_search:.2f} 秒 + 生成 {t_llm:.2f} 秒 = {t_search + t_llm:.2f} 秒")


def main():
    model, col = load()
    if len(sys.argv) > 1:
        run_once(model, col, " ".join(sys.argv[1:]))
        return
    while True:
        q = input("\n问题（空行退出）> ").strip()
        if not q:
            break
        run_once(model, col, q)


if __name__ == "__main__":
    main()
