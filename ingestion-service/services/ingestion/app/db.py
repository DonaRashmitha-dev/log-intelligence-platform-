"""
asyncpg connection pool + insert helpers.
All DB writes go through here.
"""
import asyncpg
import json
import logging
from datetime import datetime
from typing import Any
from app.models import LogEvent

logger = logging.getLogger(__name__)
_pool: asyncpg.Pool | None = None

async def init_pool(dsn: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    logger.info("DB pool initialised")

async def close_pool() -> None:
    if _pool:
        await _pool.close()

async def insert_log(event: LogEvent) -> int:
    """Insert into logs table, return new id."""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO logs
                (source, event_type, severity, message, raw_payload,
                 source_ts, ingested_at, process_id, host)
            VALUES ($1,$2,$3,$4,$5::jsonb,$6,NOW(),$7,$8)
            RETURNING id
        """,
            event.source, event.event_type, event.severity, event.message,
            json.dumps(event.raw_payload), event.source_ts,
            event.process_id, event.host,
        )
        return row["id"]

async def insert_fault_event(
    log_id: int, fault_type: str, injected_at: datetime,
    crash_count: int = 0, recovery_count: int = 0,
    mttr_seconds: float = 0.0, parameters: dict[str, Any] | None = None,
) -> None:
    async with _pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO fault_events
                (log_id, fault_type, injected_at, crash_count,
                 recovery_count, mttr_seconds, parameters)
            VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb)
        """,
            log_id, fault_type, injected_at, crash_count,
            recovery_count, mttr_seconds,
            json.dumps(parameters or {}),
        )

async def insert_metric(
    log_id: int, host: str,
    cpu_pct: float, mem_pct: float, latency_ms: float,
    is_anomaly: bool, recorded_at: datetime,
    ewma_cpu: float = 0.0, ewma_mem: float = 0.0,
) -> None:
    async with _pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO system_metrics
                (log_id, host, cpu_pct, mem_pct, latency_ms,
                 ewma_cpu, ewma_mem, is_anomaly, recorded_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        """,
            log_id, host, cpu_pct, mem_pct, latency_ms,
            ewma_cpu, ewma_mem, is_anomaly, recorded_at,
        )

async def get_recent_logs(limit: int = 50) -> list[dict]:
    async with _pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, source, event_type, severity, message,
                   source_ts, ingested_at, host
            FROM logs
            ORDER BY ingested_at DESC
            LIMIT $1
        """, limit)
        return [dict(r) for r in rows]
