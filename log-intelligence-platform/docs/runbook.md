# Demo Runbook — for recruiter demos

## Setup (5 min)
```bash
cp .env.example .env
docker compose up postgres redis ollama -d
# wait ~5min for ollama-init to pull models
docker compose up ollama-init
```

## Verify
```bash
bash infra/scripts/health_check.sh
```

## Seed demo data (if real systems not connected)
```bash
pip install asyncpg
python infra/scripts/seed_demo_data.py
```

## Demo flow
1. Open dashboard: http://localhost:3000
2. Show live metrics chart (C++ binary feeding data)
3. Inject a crash fault via fault injector UI (http://localhost:5001)
4. Watch alert appear in dashboard within 2 seconds
5. Type in NL query box: "What caused the last crash?"
6. Agent reasons → cites log IDs → shows MTTR

## Good demo questions
- "How many crashes happened in the last hour?"
- "What was the average MTTR after memory faults?"
- "Did CPU anomalies correlate with crashes today?"
- "Show me all critical events from the monitoring system"
- "When was the last time latency exceeded 300ms?"
