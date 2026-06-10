# Log Intelligence Platform — API Reference

Base URLs:
- Agent API: `http://localhost:8002`
- Ingestion Service: `http://localhost:8001`
- Fault Injection API: `http://localhost:5000`

All endpoints return JSON. All POST bodies are JSON with `Content-Type: application/json`. CORS is open (`*`) on all services.

---

## Agent API (`localhost:8002`)

### `GET /health`

Returns service status.

**Response**
```json
{ "status": "ok" }
```

---

### `GET /stats`

Returns aggregate metrics from the log database.

**Response**
```json
{
  "total": 499,
  "errors": 220,
  "anomalies": 47,
  "faults": 5,
  "last_critical": "2026-06-10T06:48:48.123456+00:00"
}
```

| Field | Type | Description |
|---|---|---|
| total | int | Total log count |
| errors | int | Logs with severity error or critical |
| anomalies | int | Logs from ewma_detector source |
| faults | int | Logs from fault injection with fault event type |
| last_critical | string or null | ISO timestamp of most recent critical log |

---

### `POST /query`

Ask a natural language question about your logs. Uses semantic vector search to retrieve relevant logs, then passes them as context to a local LLM (TinyLlama) for answer generation.

**Request**
```json
{ "question": "what caused the CPU spikes in the last hour?" }
```

**Response**
```json
{
  "answer": "Based on the logs, CPU spikes were detected at 06:48 UTC...",
  "sources": [
    {
      "id": 340,
      "source": "ewma_detector",
      "event_type": "anomaly",
      "severity": "critical",
      "message": "EWMA anomaly detected: CPU spike 91.2% (threshold 85.3%)",
      "source_ts": "2026-06-10T06:48:22.123456+00:00",
      "score": 0.94
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| answer | string | LLM-generated answer using retrieved logs as context |
| sources | array | Top-5 semantically similar logs, sorted by relevance |
| sources[].score | float 0-1 | Cosine similarity score (1.0 = exact match) |

**Time-aware queries** — the agent extracts time windows from natural language:
- "last hour" → filters to last 60 minutes
- "today" → filters to last 24 hours
- "this week" → filters to last 7 days

---

## Ingestion Service (`localhost:8001`)

### `GET /health`

Returns service status and per-collector running state.

**Response**
```json
{
  "status": "ok",
  "collectors": {
    "fault_api": true,
    "redis_alerts": true,
    "cpp_metrics": true
  }
}
```

---

### `GET /latest`

Returns the most recent ingested logs.

**Query parameters**

| Param | Type | Default | Description |
|---|---|---|---|
| limit | int | 50 | Number of logs to return (max 500) |

**Response**
```json
{
  "logs": [
    {
      "id": 499,
      "source": "flask_fault",
      "event_type": "metric",
      "severity": "info",
      "message": "Fault system: cpu=21.1% mem=80.7% crashes=0 mttr=0.0s",
      "source_ts": "2026-06-10T06:54:37.654798+00:00",
      "ingested_at": "2026-06-10T06:54:37.654798+00:00"
    }
  ],
  "count": 1
}
```

---

## Fault Injection API (`localhost:5000`)

### `GET /metrics`

Returns current system metrics from the monitored process.

**Response**
```json
{
  "cpu": 21.4,
  "memory": 80.7,
  "latency": 12.3,
  "crashes": 0,
  "mttr": 0.0
}
```

---

### `GET /status`

Returns current fault injection state.

**Response**
```json
{
  "fault": "none",
  "active": false
}
```

---

### `POST /inject`

Injects a fault into the monitored system.

**Request**
```json
{ "fault": "memory" }
```

| Fault type | Effect |
|---|---|
| `crash` | Simulates process crash, increments crash counter |
| `memory` | Allocates memory to spike memory usage |
| `delay` | Introduces artificial latency |
| `random` | Randomly picks one of the above |
| `none` | Clears all active faults |

**Response**
```json
{
  "fault": "memory",
  "status": "ok"
}
```

---

### `GET /history`

Returns historical metrics for trend analysis.

**Response**
```json
[
  { "timestamp": "2026-06-10T06:00:00Z", "cpu": 45.2, "memory": 78.1, "latency": 120 },
  { "timestamp": "2026-06-10T06:05:00Z", "cpu": 91.7, "memory": 87.3, "latency": 450 }
]
```

---

## Data flow

```
POST /inject (fault_injection)
    → fault_injection exposes updated /metrics
    → ingestion polls /metrics every 5s
    → ingestion writes log to Postgres
    → embedding_worker embeds the log (Ollama)
    → anomaly_detector detects spike via EWMA
    → anomaly_detector writes critical log to Postgres
    → POST /query (agent) retrieves it via vector search
    → LLM generates answer with log as context
```

## Error responses

All services return standard HTTP status codes.

| Code | Meaning |
|---|---|
| 200 | Success |
| 422 | Validation error — check request body shape |
| 500 | Internal error — check service logs |
| 503 | Service unavailable — dependency (Ollama/Postgres) not reachable |
