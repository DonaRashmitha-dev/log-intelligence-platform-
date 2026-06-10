import asyncio, asyncpg, json, logging, math
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("anomaly_detector")

DB = "postgresql://loguser:changeme_strong_password@localhost:5432/logdb"

# EWMA state (same algorithm as monitoring system)
ALPHA = 0.3
SIGMA = 2.0

class EWMAState:
    def __init__(self):
        self.mean = None
        self.var = 0.0

    def update(self, value):
        if self.mean is None:
            self.mean = float(value)
            self.var = 0.0
        else:
            diff = value - self.mean
            self.mean += ALPHA * diff
            self.var = (1 - ALPHA) * (self.var + ALPHA * diff * diff)
        std = math.sqrt(self.var) if self.var > 0 else 0.0
        return self.mean, std

    @property
    def threshold(self):
        std = math.sqrt(self.var) if self.var > 0 else 0.0
        return (self.mean or 0.0) + SIGMA * std

cpu_state = EWMAState()
mem_state = EWMAState()

async def run():
    pool = await asyncpg.create_pool(DB, min_size=1, max_size=3)
    logger.info("Anomaly detector started")

    # Add is_anomaly column if not exists
    async with pool.acquire() as conn:
        await conn.execute("""
            ALTER TABLE logs ADD COLUMN IF NOT EXISTS is_anomaly BOOLEAN DEFAULT FALSE
        """)
    logger.info("Schema ready")

    last_id = 0

    while True:
        async with pool.acquire() as conn:
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
            last_id = row['id']
            try:
                payload = row['raw_payload']
                if isinstance(payload, str):
                    payload = json.loads(payload)

                cpu = float(payload.get('cpu', 0))
                mem = float(payload.get('memory', payload.get('mem', 0)))

                cpu_mean, cpu_std = cpu_state.update(cpu)
                mem_mean, mem_std = mem_state.update(mem)

                cpu_anomaly = cpu_std > 1.0 and cpu > cpu_state.threshold
                mem_anomaly = mem_std > 1.0 and mem > mem_state.threshold

                if cpu_anomaly or mem_anomaly:
                    parts = []
                    if cpu_anomaly:
                        parts.append(f"CPU spike {cpu:.1f}% (threshold {cpu_state.threshold:.1f}%, σ={cpu_std:.2f})")
                    if mem_anomaly:
                        parts.append(f"MEM spike {mem:.1f}% (threshold {mem_state.threshold:.1f}%, σ={mem_std:.2f})")

                    msg = "EWMA anomaly detected: " + ", ".join(parts)
                    meta = {
                        "cpu": cpu, "memory": mem,
                        "cpu_threshold": round(cpu_state.threshold, 2),
                        "mem_threshold": round(mem_state.threshold, 2),
                        "cpu_std": round(cpu_std, 2),
                        "mem_std": round(mem_std, 2),
                        "source_log_id": row['id']
                    }

                    async with pool.acquire() as conn:
                        new_id = await conn.fetchval("""
                            INSERT INTO logs (source, event_type, severity, message, raw_payload, source_ts, host, is_anomaly)
                            VALUES ('ewma_detector', 'anomaly', 'critical', $1, $2, $3, 'anomaly-detector', TRUE)
                            RETURNING id
                        """, msg, json.dumps(meta), datetime.now(timezone.utc))
                        logger.info(f"Anomaly logged id={new_id}: {msg}")

            except Exception as e:
                logger.error(f"Error processing row {row['id']}: {e}")

        if not rows:
            await asyncio.sleep(5)
        else:
            await asyncio.sleep(1)

asyncio.run(run())
