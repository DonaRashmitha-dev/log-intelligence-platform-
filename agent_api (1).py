import json, logging, asyncpg, httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB = "postgresql://loguser:changeme_strong_password@localhost:5432/logdb"
OLLAMA = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = "tinyllama:latest"

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DB, min_size=1, max_size=5)
    return _pool

async def embed(text):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{OLLAMA}/api/embeddings", json={"model": EMBED_MODEL, "prompt": text})
        return r.json()["embedding"]

async def search(q, k=5):
    pool = await get_pool()
    vec = await embed(q)
    sql = (
        "SELECT id, source, event_type, severity, message, source_ts, "
        "1-(embedding<=>$1::vector) AS score "
        "FROM logs WHERE embedding IS NOT NULL "
        "ORDER BY embedding<=>$1::vector LIMIT $2"
    )
    rows = await pool.fetch(sql, json.dumps(vec), k)
    return [dict(r) for r in rows]

async def llm(sys_prompt, user_prompt):
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{OLLAMA}/api/chat", json={
            "model": LLM_MODEL, "stream": False,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ]
        })
        return r.json()["message"]["content"]

class Q(BaseModel):
    question: str

@app.post("/query")
async def query(req: Q):
    results = await search(req.question)
    ctx = "\n".join([
        f"[id={r['id']} src={r['source']} sev={r['severity']} score={r['score']:.2f}] {r['message']}"
        for r in results
    ])
    answer = await llm(f"SRE agent. Today: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. Logs:\n{ctx}", req.question)
    return {"answer": answer, "sources": results}

@app.get("/health")
async def health():
    return {"status": "ok"}
