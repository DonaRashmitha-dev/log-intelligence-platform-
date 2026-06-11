import asyncio, asyncpg, json, logging, math, os
import redis.asyncio as aioredis
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("anomaly_detector")

DB        = os.environ.get("DATABASE_URL", "postgresql://loguser:changeme@localhost:5432/logdb")
REDIS_URL = os.environ.get("REDIS_URL",    "redis://localhost:6379")

ALPHA = 0.3
SIGMA = 1.2

REDIS_KEY_CPU     = "ewma:state:cpu"
REDIS_KEY_MEM     = "ewma:state:mem"
REDIS_KEY_LAST_ID = "ewma:last_id"

class EWMAState:
    def __init__(self, mean=None, var=0.0):
        self.mean = mean
        self.var  = float(var)

    def update(self, value):
        if self.mean is None:
            self.mean = float(value)
            self.var  = 0.0
        else:
            diff      = value - self.mean
            self.mean += ALPHA * diff
            self.var   = (1 - ALPHA) * (self.var + ALPHA * diff * diff)
        std = math.sqrt(self.var) if self.var > 0 else 0.0
        return self.mean, std

    @property
    def threshold(self):
        std = math.sqrt(self.var) if self.var > 0 else 0.0
        return (self.mean or 0.0) + SIGMA * std

    def to_dict(self):
        return {"mean": self.mean, "var": self.var}

    @classmethod
    def from_dict(cls, d):
        return cls(mean=d.get("mean"), var=d.get("var", 0.0))

async def load_state(redis, key):
    try:
        raw = await redis.get(key)
        if raw:
            return EWMAState.from_dict(json.loads(raw))
    except Exception as e:
        logger.warning(f"Could not load state for {key}: {e}")
    return EWMAState()

async def save_state(redis, key, state):
    try:
        await redis.set(key, json.dumps(state.to_dict()))
    except Exception as e:
        logger.warning(f"Could not save state for {key}: {e}")

async def run():
    pg_pool = await asyncpg.create_pool(DB, min_size=1, max_size=3)
    redis   = await aioredis.from_url(REDIS_URL, decode_responses=True)
    logger.info("Anomaly detector started")

    async with pg_pool.acquire() as conn:
        await conn.execute("ALTER TABLE logs ADD COLUMN IF NOT EXISTS is_anomaly BOOLEAN DEFAULT FALSE")
    logger.info("Schema ready")

    cpu_state = await load_state(redis, REDIS_KEY_CPU)
    mem_state = await load_state(redis, REDIS_KEY_MEM)
    logger.info(f"Restored CPU state: mean={cpu_state.mean}, var={cpu_state.var:.4f}")
    logger.info(f"Restored MEM state: mean={mem_state.mean}, var={mem_state.var:.4f}")

    try:
        raw_id = await redis.get(REDIS_KEY_LAST_ID)
        last_id = int(raw_id) if raw_id else 0
    except Exception:
        last_id = 0
    logger.info(f"Resuming from log id={last_id}")

    while True:
        async with pg_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, source, raw_payload, ingested_at
                FROM logs
                WHERE id > $1
                AND source = 'flask_fault'
                AND event_type = 'metric'
                ORDER BY id ASC
                LIMIT 50
            """, last_id)

        for row in rows:
            last_id = row["id"]
            try:
                payload = row["raw_payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)

                cpu = float(payload.get("cpu", 0))
                mem = float(payload.get("memory", payload.get("mem", 0)))

                cpu_mean, cpu_std = cpu_state.update(cpu)
                mem_mean, mem_std = mem_state.update(mem)

                cpu_anomaly = cpu_std > 1.0 and cpu > cpu_state.threshold
                mem_anomaly = mem_std > 1.0 and mem > mem_state.threshold

                if cpu_anomaly or mem_anomaly:
                    parts = []
                    if cpu_anomaly:
                        parts.append(f"CPU spike {cpu:.1f}% (threshold {cpu_state.threshold:.1f}%, sigma={cpu_std:.2f})")
                    if mem_anomaly:
                        parts.append(f"MEM spike {mem:.1f}% (threshold {mem_state.threshold:.1f}%, sigma={mem_std:.2f})")

                    msg  = "EWMA anomaly detected: " + ", ".join(parts)
                    meta = {
                        "cpu": cpu, "memory": mem,
                        "cpu_threshold": round(cpu_state.threshold, 2),
                        "mem_threshold": round(mem_state.threshold, 2),
                        "cpu_std": round(cpu_std, 2),
                        "mem_std": round(mem_std, 2),
                        "source_log_id": row["id"],
                    }

                    async with pg_pool.acquire() as conn:
                        new_id = await conn.fetchval("""
                            INSERT INTO logs (source, event_type, severity, message, raw_payload, source_ts, host, is_anomaly)
                            VALUES ('ewma_detector', 'anomaly', 'critical', $1, $2, $3, 'anomaly-detector', TRUE)
                            RETURNING id
                        """, msg, json.dumps(meta), datetime.now(timezone.utc))
                        logger.info(f"Anomaly logged id={new_id}: {msg}")

                    await redis.publish("anomaly_alerts", json.dumps({"id": new_id, "msg": msg, **meta}))

            except Exception as e:
                logger.error(f"Error processing row {row['id']}: {e}")

        await save_state(redis, REDIS_KEY_CPU, cpu_state)
        await save_state(redis, REDIS_KEY_MEM, mem_state)
        await redis.set(REDIS_KEY_LAST_ID, str(last_id))

        if not rows:
            await asyncio.sleep(5)
        else:
            await asyncio.sleep(1)

asyncio.run(run())
