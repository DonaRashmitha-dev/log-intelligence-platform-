"""Shared Pydantic models for the ingestion service."""
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

class LogEvent(BaseModel):
    source: str                          # cpp_metrics | flask_fault | node_alerts
    event_type: str                      # metric | fault_injected | anomaly | recovery
    severity: str = "info"              # info | warn | error | critical
    message: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    source_ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    process_id: str | None = None
    host: str | None = None

class IngestResponse(BaseModel):
    log_id: int
    status: str = "ok"
