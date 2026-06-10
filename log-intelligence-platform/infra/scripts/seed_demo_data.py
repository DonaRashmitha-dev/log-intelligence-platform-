"""
Run this to seed demo log data for testing the agent before real systems connect.
Usage: python infra/scripts/seed_demo_data.py
"""
import asyncio, asyncpg, random, datetime, json, os

DB_URL = os.getenv("DATABASE_URL", "postgresql://loguser:changeme_strong_password@localhost:5432/logdb")

FAULT_TYPES = ["crash", "delay", "memory", "random"]
SEVERITIES  = ["info", "info", "info", "warn", "warn", "error", "critical"]
SOURCES     = ["cpp_metrics", "flask_fault", "node_alerts"]

SAMPLE_MESSAGES = [
    "CPU spike detected: 94.2% utilization",
    "Memory usage crossed EWMA threshold: 87.1%",
    "Fault injected: crash on pid 1234",
    "Process recovered after crash. MTTR: 3.2s",
    "Latency anomaly: 342ms (threshold: 150ms)",
    "EWMA alert: cpu=91.3 mean=45.2 stddev=12.1",
    "Fault injected: memory spike 512MB",
    "Scheduler triggered: delay fault every 30s",
    "Process restart detected. crash_count=5",
    "System healthy. cpu=32% mem=41% latency=45ms",
]

async def seed():
    conn = await asyncpg.connect(DB_URL)
    now = datetime.datetime.utcnow()

    for i in range(100):
        ts = now - datetime.timedelta(minutes=random.randint(0, 120))
        source = random.choice(SOURCES)
        severity = random.choice(SEVERITIES)
        message = random.choice(SAMPLE_MESSAGES)
        fault_type = random.choice(FAULT_TYPES) if source == "flask_fault" else None
        payload = {
            "cpu": round(random.uniform(20, 95), 1),
            "memory": round(random.uniform(30, 90), 1),
            "latency_ms": round(random.uniform(20, 400), 1),
            "fault_type": fault_type,
            "pid": random.randint(1000, 9999),
        }

        await conn.execute("""
            INSERT INTO logs (source, event_type, severity, message, raw_payload, source_ts, host)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, source, fault_type or "metric", severity, message,
            json.dumps(payload), ts, "demo-host-1")

    print("Seeded 100 demo log rows.")
    await conn.close()

asyncio.run(seed())
