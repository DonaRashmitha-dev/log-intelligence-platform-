import asyncio, httpx, logging
from datetime import datetime, timezone
from app.models import LogEvent
from app.db import insert_log, insert_fault_event, insert_metric

logger = logging.getLogger(__name__)
_last_seen_ids: set = set()

def _severity(crashes, cpu):
    if crashes > 5 or cpu > 90: return "critical"
    if crashes > 2 or cpu > 75: return "error"
    if cpu > 60: return "warn"
    return "info"

async def poll_fault_api(url="http://localhost:5000"):
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            try:
                mr = await client.get(f"{url}/metrics")
                sr = await client.get(f"{url}/status")
                hr = await client.get(f"{url}/history")
                if mr.status_code == 200:
                    m = mr.json(); s = sr.json() if sr.status_code == 200 else {}
                    cpu=float(m.get("cpu",0)); mem=float(m.get("memory",0))
                    crashes=int(m.get("crash_count",0)); mttr=float(s.get("mttr",0) or 0)
                    ev = LogEvent(source="flask_fault",event_type="metric",
                        severity=_severity(crashes,cpu),
                        message=f"Fault system: cpu={cpu}% mem={mem}% crashes={crashes} mttr={mttr}s",
                        raw_payload={**m,"mttr":mttr},source_ts=datetime.now(timezone.utc),host="fault-api")
                    lid = await insert_log(ev)
                    await insert_metric(lid,"fault-api",cpu,mem,0.0,False,datetime.now(timezone.utc))
                if hr.status_code == 200:
                    for item in (hr.json() or []):
                        iid = str(item.get("id") or item.get("timestamp",""))
                        if iid in _last_seen_ids: continue
                        _last_seen_ids.add(iid)
                        ft=item.get("fault_type","unknown"); ts_str=item.get("timestamp","")
                        try:
                            ts=datetime.fromisoformat(ts_str) if ts_str else datetime.now(timezone.utc)
                            if ts.tzinfo is None: ts=ts.replace(tzinfo=timezone.utc)
                        except: ts=datetime.now(timezone.utc)
                        ev2=LogEvent(source="flask_fault",event_type="fault_injected",
                            severity="error" if ft=="crash" else "warn",
                            message=f"Fault injected: {ft}",raw_payload=item,source_ts=ts,host="fault-api")
                        lid2=await insert_log(ev2)
                        await insert_fault_event(lid2,ft,ts,int(m.get("crash_count",0)),
                            int(m.get("recovery_count",0)),mttr,item)
            except httpx.ConnectError: logger.debug(f"fault_api not reachable at {url}")
            except Exception as e: logger.error(f"fault_api error: {e}")
            await asyncio.sleep(5)

