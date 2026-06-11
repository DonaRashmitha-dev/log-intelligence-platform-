import asyncio, asyncpg, httpx, json, logging, os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("embedder")

DB     = os.environ.get("DATABASE_URL", "postgresql://loguser:changeme@localhost:5432/logdb")
OLLAMA = os.environ.get("OLLAMA_URL",   "http://localhost:11434")
EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")

async def embed(text: str) -> list:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{OLLAMA}/api/embeddings", json={"model": EMBED_MODEL, "prompt": text})
        return r.json()["embedding"]

async def run():
    pool = await asyncpg.create_pool(DB, min_size=1, max_size=5)
    logger.info("Embedding worker started")

    while True:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, message, raw_payload, source FROM logs WHERE embedding IS NULL LIMIT 20"
            )

        if not rows:
            await asyncio.sleep(3)
            continue

        logger.info(f"Embedding {len(rows)} rows...")
        for row in rows:
            try:
                payload_str = json.dumps(row["raw_payload"]) if row["raw_payload"] else ""
                text = f"[{row['source']}] {row['message']} {payload_str}".strip()
                vec = await embed(text)
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE logs SET embedding = $1 WHERE id = $2",
                        json.dumps(vec), row["id"]
                    )
                logger.info(f"Embedded log id={row['id']} source={row['source']}")
            except Exception as e:
                logger.error(f"Embed failed id={row['id']}: {e}")

        await asyncio.sleep(1)

asyncio.run(run())
