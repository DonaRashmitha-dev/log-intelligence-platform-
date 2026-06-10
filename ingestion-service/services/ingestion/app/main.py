"""
Ingestion service — FastAPI app.
Starts all 3 collectors as background tasks on startup.
Exposes /health and /latest endpoints.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_pool, close_pool, get_recent_logs
from app.collectors.fault_api import poll_fault_api
from app.collectors.redis_alerts import subscribe_alerts
from app.collectors.cpp_metrics import poll_node_webhook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DATABASE_URL  = os.getenv("DATABASE_URL", "postgresql://loguser:logpass@localhost:5432/logdb")
REDIS_URL     = os.getenv("REDIS_URL",    "redis://localhost:6379")
FAULT_API_URL = os.getenv("FAULT_API_URL","http://localhost:5001")
NODE_URL      = os.getenv("NODE_WEBHOOK_URL", "http://localhost:3001")

_bg_tasks: list[asyncio.Task] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool(DATABASE_URL)
    logger.info("Starting collectors...")
    _bg_tasks.append(asyncio.create_task(poll_fault_api(FAULT_API_URL),   name="fault_api"))
    _bg_tasks.append(asyncio.create_task(subscribe_alerts(REDIS_URL),      name="redis_alerts"))
    _bg_tasks.append(asyncio.create_task(poll_node_webhook(NODE_URL),      name="cpp_metrics"))
    logger.info("All 3 collectors running")
    yield
    for t in _bg_tasks:
        t.cancel()
    await close_pool()

app = FastAPI(title="Log Ingestion Service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health():
    tasks = {t.get_name(): not t.done() for t in _bg_tasks}
    return {"status": "ok", "collectors": tasks}

@app.get("/latest")
async def latest(limit: int = 50):
    rows = await get_recent_logs(limit)
    # Make datetime JSON-serialisable
    for r in rows:
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
    return {"logs": rows, "count": len(rows)}
