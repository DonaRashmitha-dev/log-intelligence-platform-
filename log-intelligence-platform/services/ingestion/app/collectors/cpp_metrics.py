import asyncio, logging, httpx
from datetime import datetime, timezone
from app.models import LogEvent
from app.db import insert_log, insert_metric

logger = logging.getLogger(__name__)

def _anomaly(cpu,mem,lat): return cpu>85 or mem>85 or lat>300

async def poll_node_webhook(url="http://localhost:3001"):
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            try:
                r = await client.get(f"{url}/metrics")
                if r.status_code == 200:
                    data=r.json(); items=data if isinstance(data,list) else [data]
                    for item in items[-5:]:
                        cpu=float(item.get("cpu",0)); mem=float(item.get("memory",item.get("mem",0)))
                        lat=float(item.get("latency_ms",item.get("latency",0)))
                        anom=_anomaly(cpu,mem,lat)
                        ev=LogEvent(source="cpp_metrics",event_type="metric",
                            severity="error" if anom else "info",
                            message=f"Metrics: cpu={cpu}% mem={mem}% latency={lat}ms",
                            raw_payload=item,source_ts=datetime.now(timezone.utc),
                            host=item.get("host","cpp-metrics"))
                        lid=await insert_log(ev)
                        await insert_metric(lid,ev.host,cpu,mem,lat,anom,datetime.now(timezone.utc))
            except httpx.ConnectError: logger.debug(f"node-webhook not reachable at {url}")
            except Exception as e: logger.error(f"cpp_metrics error: {e}")
            await asyncio.sleep(2)
