# ClipES

> Convierte vídeos de divulgación de IA en español en una base de conocimiento consultable: pregunta y obtén respuesta, con fuente y minuto exacto, con enlace directo a ese momento del vídeo.

Español (actual) ｜ [中文](README.zh.md)

---

## Qué es

[VideoListo](https://github.com/Lnnkun/VideoListo) (transcripción local con Whisper + generación de metadatos con LLM) y [VideoBusca](https://github.com/Lnnkun/VideoBusca) (embeddings + base vectorial + RAG, 53% de precisión de respuesta, reportado con honestidad) son dos proyectos de aprendizaje independientes. ClipES los une en un solo producto:

- **Backend**: un servicio FastAPI que expone ambos flujos — `/ask` para preguntas, `/ingest/transcribe` para añadir un vídeo nuevo
- **Frontend**: una página Streamlit donde se escribe una pregunta y se recibe una respuesta con fuentes, con enlaces que saltan directamente al segundo exacto del vídeo en YouTube

## La decisión de producto detrás de esto

Antes de hacer esta integración, se pensó bien "a quién sirve esto realmente" — no a "creadores de vídeos en español" (la idea inicial, que no se sostenía), sino a:

> Cuando estoy construyendo un proyecto y me atasco en un concepto concreto, quiero una respuesta precisa y con fuente fiable, en vez de buscar a ciegas en YouTube y mover la barra de progreso esperando encontrar esos 30 segundos.

La forma actual de ClipES (preguntar algo concreto → recibir una respuesta con cita y minuto exacto) sirve exactamente a ese momento, ni más ni menos.

## Arquitectura
```
clipes/                paquete Python compartido
  config.py             rutas, nombre del modelo, colección
  ingest.py             lee data/transcripts/*.srt
  chunk.py              trocea en bloques de 30-60s
  index.py              genera embeddings, indexa en Chroma
  search.py             búsqueda semántica top-10
  ask.py                preguntas y respuestas RAG (antes VideoBusca)
  transcribe.py         transcripción local con Whisper (antes VideoListo)
  meta.py               LLM genera descripción/capítulos/etiquetas (antes VideoListo)

api.py                  backend FastAPI, envuelve ambos flujos
streamlit_app.py        frontend web, llama a api.py
```

## Instalación
- Windows + Python 3.10, RTX 4060 (8GB VRAM)

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
```

Copiar `.env.example` como `.env` y rellenar:
```
OPENROUTER_API_KEY=tu_clave
MODEL=deepseek/deepseek-v4.1-flash-1017
```

## Uso
```powershell
# 1. Construir el índice (data/transcripts/*.srt ya incluido; necesario antes del primer uso)
python -m clipes.chunk
python -m clipes.index

# 2. Arrancar el backend (terminal A)
uvicorn api:app --reload

# 3. Arrancar el frontend (terminal B)
streamlit run streamlit_app.py
```

Abrir la URL que indique Streamlit. La documentación de la API está en http://127.0.0.1:8000/docs.

## Escala de los datos
Reutiliza el corpus de VideoBusca: 19 vídeos de divulgación sobre IA en español, 336 minutos de audio, 658 bloques indexados. La metodología de evaluación completa y los números reales (53% de precisión, 88% de acierto al negarse a responder) están en el [repositorio de VideoBusca](https://github.com/Lnnkun/VideoBusca).

## Relación con los dos proyectos anteriores
- **VideoListo**: documenta cómo se hizo "transcribir + generar la descripción de YouTube"; repositorio independiente, se mantiene
- **VideoBusca**: documenta cómo se hizo "búsqueda + respuesta RAG + evaluación automática"; repositorio independiente, se mantiene
- **ClipES**: une ambos flujos en un producto que funciona de verdad; es el cierre actual de este camino de aprendizaje
