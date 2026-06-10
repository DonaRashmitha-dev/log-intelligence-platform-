# LOG.INTEL — Real-Time Log Intelligence Platform

> Ingest system logs → detect anomalies statistically → query everything in plain English via RAG-powered AI agent.

---

## What This Is

A production-grade observability platform built from scratch. It continuously ingests fault-injection logs, runs EWMA-based anomaly detection, embeds log data into a vector database, and exposes a natural language query interface powered by a local LLM with retrieval-augmented generation.

No cloud dependency. No managed services. Fully self-hosted.

---

## Screenshots

### Critical Anomaly Detection
![Critical Anomalies](screenshots/dashboardhtml_1.png)

### System Health Summary
![System Health](screenshots/dashboardhtml_2.png)

### Error Query — Last 6 Hours
![Errors Last 6 Hours](screenshots/dashboardhtml_3.png)

---

## Architecture
Fault Injector (Flask)
│
▼
Ingestion Service (FastAPI) ──► PostgreSQL + pgvector
│                              │
▼                              ▼
Embedding Worker              EWMA Anomaly Detector
(nomic-embed-text)                     │
▼
Redis Alert Channel
│
▼
Agent API (FastAPI + RAG)
│
▼
Dashboard (Vanilla JS)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Fault Simulation | Python / Flask |
| Ingestion API | FastAPI + asyncpg |
| Database | PostgreSQL 16 + pgvector |
| Cache / Alerts | Redis 7 |
| Embeddings | Ollama — nomic-embed-text |
| Anomaly Detection | EWMA (Exponentially Weighted Moving Average) |
| AI Agent | Ollama — TinyLlama (local LLM) |
| RAG Pipeline | Vector similarity search → LLM context injection |
| Dashboard | Vanilla JS, HTML, CSS |
| Containers | Docker (Postgres + Redis) |

---

## Key Features

**Real-time ingestion** — fault simulator generates CPU/memory/crash logs every few seconds; ingestion service writes to Postgres with embeddings via pgvector.

**EWMA anomaly detection** — statistical threshold model detects CPU spikes using exponentially weighted moving averages. Fires CRITICAL alerts to Redis when threshold breached. Adaptive — threshold adjusts to baseline over time.

**RAG query pipeline** — natural language question → embed query → vector similarity search → top-k relevant logs injected as context → LLM generates specific answer with log IDs and timestamps.

**Live dashboard** — real-time metrics (total logs, error rate, anomaly count, latest critical timestamp), filterable log stream (ALL/ERROR/WARN/INFO/DEBUG), AI query panel.

---

## Live Metrics (From Real Run)

| Metric | Value |
|---|---|
| Total logs ingested | 2,735 |
| Error rate | 75.4% |
| EWMA anomalies detected | 431 |
| Latest anomaly | CPU spike 87.6% (threshold 84.3%, σ=18.60) |

---

## Running Locally

### Prerequisites
- Docker Desktop
- Python 3.11+
- Ollama

### Setup

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/log-intelligence-platform.git
cd log-intelligence-platform

# 2. Pull Ollama models
ollama pull nomic-embed-text
ollama pull tinyllama

# 3. Start Postgres + Redis
docker compose up -d

# 4. Install dependencies
pip install -r requirements.txt
```

### Start Services (4 terminals)

```powershell
# Terminal 1 — Ingestion
$env:DATABASE_URL="postgresql://loguser:changeme_strong_password@localhost:5432/logdb"
$env:REDIS_URL="redis://localhost:6379"
cd services/ingestion
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2 — Agent
cd services/agent
uvicorn agent_api:app --host 0.0.0.0 --port 8002 --reload

# Terminal 3 — Dashboard
python -m http.server 8080

# Terminal 4 — Fault Injector
cd services/fault_injector
python app.py
```

Open http://localhost:8080/dashboard.html

---

## Project Structure
log-intelligence-platform/
├── services/
│   ├── ingestion/          # FastAPI log ingestion + embedding pipeline
│   ├── agent/              # RAG agent API (vector search + LLM)
│   ├── fault_injector/     # Synthetic fault log generator
│   ├── embedding_worker/   # Async embedding processor
│   └── ewma_detector/      # Statistical anomaly detection
├── screenshots/            # Dashboard screenshots
├── dashboard.html          # Live monitoring dashboard
├── start.ps1               # One-command startup script
└── docker-compose.yml      # Postgres + Redis containers

---

## What I Built vs What I Used

Built from scratch: ingestion pipeline, EWMA detector, RAG agent, embedding worker, dashboard UI, fault simulator.

Used as infrastructure: PostgreSQL, pgvector, Redis, Docker, Ollama (model serving only).

---

## Why This Project

Most observability tools are black boxes. This project is an exercise in building the full stack — from raw log ingestion to vector search to LLM reasoning — with every layer visible and modifiable. The goal was to understand how production monitoring systems actually work, not just use them.
