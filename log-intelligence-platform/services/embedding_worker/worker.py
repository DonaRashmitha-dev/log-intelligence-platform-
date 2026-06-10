import asyncio, asyncpg, httpx, json, logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('embedder')

DB = 'postgresql://loguser:changeme_strong_password@localhost:5432/logdb'
OLLAMA = 'http://localhost:11434'

async def embed(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f'{OLLAMA}/api/embeddings', json={'model':'nomic-embed-text','prompt':text})
        return r.json()['embedding']

async def run():
    pool = await asyncpg.create_pool(DB, min_size=1, max_size=5)
    logger.info('Embedding worker started')
    while True:
        async with pool.acquire() as conn:
            rows = await conn.fetch('SELECT id, message, raw_payload FROM logs WHERE embedding IS NULL LIMIT 20')
        if not rows:
            await asyncio.sleep(3); continue
        logger.info(f'Embedding {len(rows)} rows...')
        for row in rows:
            try:
                text = row['message'] + ' ' + json.dumps(row['raw_payload'])
                vec = await embed(text)
                async with pool.acquire() as conn:
                    await conn.execute('UPDATE logs SET embedding = $1 WHERE id = $2', json.dumps(vec), row['id'])
                logger.info(f'Embedded log id={row["id"]}')
            except Exception as e:
                logger.error(f'Embed failed id={row["id"]}: {e}')
        await asyncio.sleep(1)

asyncio.run(run())
