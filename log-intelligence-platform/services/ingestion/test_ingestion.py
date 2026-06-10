"""
Tests for the Ingestion Service.
Run with: pytest test_ingestion.py -v

Integration tests require ingestion running on port 8001.
"""
import pytest
import httpx

BASE = "http://localhost:8001"

class TestHealth:
    def test_health_returns_ok(self):
        r = httpx.get(f"{BASE}/health", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_health_shows_collectors(self):
        r = httpx.get(f"{BASE}/health", timeout=5)
        data = r.json()
        assert "collectors" in data
        collectors = data["collectors"]
        assert "fault_api" in collectors
        assert "redis_alerts" in collectors
        assert "cpp_metrics" in collectors

    def test_at_least_one_collector_running(self):
        r = httpx.get(f"{BASE}/health", timeout=5)
        data = r.json()
        running = [v for v in data["collectors"].values() if v is True]
        assert len(running) >= 1, "At least one collector should be running"

class TestLatest:
    def test_latest_returns_logs(self):
        r = httpx.get(f"{BASE}/latest", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert "logs" in data
        assert "count" in data

    def test_latest_log_has_required_fields(self):
        r = httpx.get(f"{BASE}/latest?limit=5", timeout=5)
        data = r.json()
        for log in data["logs"]:
            assert "source" in log
            assert "severity" in log
            assert "message" in log

    def test_latest_respects_limit(self):
        r = httpx.get(f"{BASE}/latest?limit=3", timeout=5)
        data = r.json()
        assert data["count"] <= 3

    def test_latest_count_matches_logs_length(self):
        r = httpx.get(f"{BASE}/latest", timeout=5)
        data = r.json()
        assert data["count"] == len(data["logs"])

class TestLogSchema:
    """Validate log field types and values."""

    VALID_SEVERITIES = {"info", "warn", "warning", "error", "critical", "debug"}

    def test_severity_values_are_known(self):
        r = httpx.get(f"{BASE}/latest?limit=20", timeout=5)
        data = r.json()
        for log in data["logs"]:
            sev = log.get("severity", "").lower()
            assert sev in self.VALID_SEVERITIES, f"Unknown severity: {sev}"

    def test_source_is_non_empty_string(self):
        r = httpx.get(f"{BASE}/latest?limit=10", timeout=5)
        data = r.json()
        for log in data["logs"]:
            assert isinstance(log["source"], str)
            assert len(log["source"]) > 0
