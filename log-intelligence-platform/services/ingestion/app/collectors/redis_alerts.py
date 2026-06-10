import asyncio, json, logging
from datetime import datetime, timezone
import redis.asyncio as aioredis
from app.models import LogEvent
from app.db import insert_log, insert_metric

logger = logging.getLogger(__name__)

async def subscribe_alerts(url="redis://localhost:6379"):
    while True:
        try:
            r = aioredis.from_url(url, decode_responses=True)
            ps = r.pubsub()
            await ps.subscribe("alerts")
            logger.info("subscribed to alerts channel")
            async for msg in ps.listen():
                if msg["type"] != "message": continue
                try:
                    try: payload=json.loads(msg["data"])
                    except: payload={"raw":msg["data"]}
                    cpu=float(payload.get("cpu",0)); mem=float(payload.get("memory",payload.get("mem",0)))
                    lat=float(payload.get("latency_ms",payload.get("latency",0)))
                    text=payload.get("message") or f"EWMA anomaly: cpu={cpu}% mem={mem}% latency={lat}ms"
                    ev=LogEvent(source="node_alerts",event_type="anomaly",severity="error",message=text,raw_payload=payload,source_ts=datetime.now(timezone.utc),host=payload.get("host","monitoring"))
                    lid=await insert_log(ev)
                    await insert_metric(lid,ev.host,cpu,mem,lat,True,datetime.now(timezone.utc))
                except Exception as e: logger.error(f"redis_alerts parse: {e}")
        except Exception as e:
            logger.error(f"redis_alerts conn error: {e} - retry in 5s")
            await asyncio.sleep(5)
