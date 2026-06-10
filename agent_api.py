import json, logging, asyncpg, httpx
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")

app = FastAPI()
DB = "postgresql://loguser:changeme_strong_password@localhost:5432/logdb"
OLLAMA = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = "llama3.2:3b"

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DB, min_size=1, max_size=5)
    return _pool

async def embed(text: str) -> list:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{OLLAMA}/api/embeddings", json={"model": EMBED_MODEL, "prompt": text})
        return r.json()["embedding"]

async def semantic_search(query: str, k: int = 5) -> list:
    pool = await get_pool()
    vec = await embed(query)
    rows = await pool.fetch(
        "SELECT id, source, event_type, severity, message, source_ts, "
        "1 - (embedding <=> $1::vector) AS score "
        "FROM logs WHERE embedding IS NOT NULL "
        "ORDER BY embedding <=> $1::vector LIMIT $2",
        json.dumps(vec), k
    )
    return [dict(r) for r in rows]

async def call_llm(system: str, user: str) -> str:
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{OLLAMA}/api/chat", json={
            "model": LLM_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ]
        })
        return r.json()["message"]["content"]

class QueryRequest(BaseModel):
    question: str

@app.post("/query")
async def query(req: QueryRequest):
    results = await semantic_search(req.question)
    context = "\n".join([
        f"[id={r['id']} src={r['source']} sev={r['severity']} score={r['score']:.2f}] {r['message']}"
        for r in results
    ])
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    system = (
        f"You are an SRE intelligence agent. Today: {now}.\n"
        "Answer questions about system health using the log context below. "
        "Be concise and cite log IDs.\n"
        f"LOGS:\n{context}"
    )
    answer = await call_llm(system, req.question)
    return {"answer": answer, "sources": results}

@app.get("/health")
async def health():
    return {"status": "ok"}
