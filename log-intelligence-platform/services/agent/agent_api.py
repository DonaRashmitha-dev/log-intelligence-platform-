import json, logging, asyncpg, httpx, re, anthropic
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO)
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB = "postgresql://loguser:changeme_strong_password@localhost:5432/logdb"
OLLAMA = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = "tinyllama"
_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DB, min_size=1, max_size=5)
    return _pool

async def embed(text):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(OLLAMA + "/api/embeddings", json={"model": EMBED_MODEL, "prompt": text})
        return r.json()["embedding"]

def parse_time_filter(question):
    q = question.lower()
    now = datetime.now(timezone.utc)
    if any(x in q for x in ["last hour", "past hour"]):
        return now - timedelta(hours=1)
    if any(x in q for x in ["last 6 hours", "6 hours"]):
        return now - timedelta(hours=6)
    if "today" in q:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    return now - timedelta(hours=24)

async def search(q, k=8):
    pool = await get_pool()
    vec = await embed(q)
    since = parse_time_filter(q)
    rows = await pool.fetch(
        "SELECT id, source, event_type, severity, message, source_ts, 1-(embedding<=>$1::vector) AS score FROM logs WHERE embedding IS NOT NULL AND ingested_at >= $3 ORDER BY embedding<=>$1::vector LIMIT $2",
        json.dumps(vec), k, since
    )
    return [dict(r) for r in rows]

async def get_stats(since):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE severity IN ('error','critical')) as errors, COUNT(*) FILTER (WHERE source = 'ewma_detector') as anomalies, MAX(ingested_at) FILTER (WHERE severity = 'critical') as last_critical FROM logs WHERE ingested_at >= $1",
        since
    )
    return dict(rows[0]) if rows else {}

async def llm(system_prompt, user_prompt):
    async with __import__("httpx").AsyncClient(timeout=180) as c:
        r = await c.post("http://localhost:11434/api/chat", json={
            "model": "tinyllama", "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        })
        return r.json()["message"]["content"]

class Q(BaseModel):
    question: str

@app.post("/query")
async def query(req: Q):
    try:
        since = parse_time_filter(req.question)
        hits = await search(req.question)
        stats = await get_stats(since)
        context = "\n".join(f"[id={r['id']} src={r['source']} sev={r['severity']}] {r['message']}" for r in hits)
        answer = await llm(
            "You are a log analysis assistant. Answer specifically using the log data provided. Reference IDs and timestamps.",
            f"Stats: {json.dumps(stats, default=str)}\n\nLogs:\n{context}\n\nQuestion: {req.question}"
        )
        sources = [{"id": r["id"], "source": r["source"], "severity": r["severity"], "message": r["message"], "source_ts": str(r["source_ts"]), "score": float(r["score"])} for r in hits]
        return {"answer": answer, "sources": sources}
    except Exception as e:
        logging.exception("query error")
        return {"answer": f"Error: {e}", "sources": []}

@app.get("/stats")
async def stats_endpoint():
    try:
        pool = await get_pool()
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        rows = await pool.fetch(
            "SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE severity IN ('error','critical')) as errors, COUNT(*) FILTER (WHERE source = 'ewma_detector') as anomalies, MAX(ingested_at) FILTER (WHERE severity = 'critical') as last_critical FROM logs WHERE ingested_at >= $1",
            since
        )
        r = dict(rows[0]) if rows else {}
        return {"total": int(r.get("total",0)), "errors": int(r.get("errors",0)), "anomalies": int(r.get("anomalies",0)), "last_critical": str(r.get("last_critical","")) if r.get("last_critical") else None}
    except Exception as e:
        return {"total": 0, "errors": 0, "anomalies": 0, "last_critical": None}

@app.get("/health")
async def health():
    return {"status": "ok"}

