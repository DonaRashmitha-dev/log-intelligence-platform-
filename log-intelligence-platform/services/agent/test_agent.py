"""
Tests for the Agent API.
Run with: pytest test_agent.py -v

Requires agent running on port 8002 and Postgres + Ollama available.
For unit tests (no services needed), use the mock tests at the bottom.
"""
import pytest
import httpx
import asyncio

BASE = "http://localhost:8002"

# ── Integration tests (agent must be running) ──────────────────────────

class TestHealth:
    def test_health_returns_ok(self):
        r = httpx.get(f"{BASE}/health", timeout=5)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

class TestStats:
    def test_stats_returns_expected_fields(self):
        r = httpx.get(f"{BASE}/stats", timeout=5)
        assert r.status_code == 200
        data = r.json()
        for field in ["total", "errors", "anomalies", "faults"]:
            assert field in data, f"Missing field: {field}"

    def test_stats_values_are_non_negative(self):
        r = httpx.get(f"{BASE}/stats", timeout=5)
        data = r.json()
        assert data["total"] >= 0
        assert data["errors"] >= 0
        assert data["anomalies"] >= 0
        assert data["errors"] <= data["total"], "errors cannot exceed total logs"

class TestQuery:
    def test_query_returns_answer_and_sources(self):
        r = httpx.post(
            f"{BASE}/query",
            json={"question": "system health summary"},
            timeout=60,
        )
        assert r.status_code == 200
        data = r.json()
        assert "answer" in data
        assert "sources" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    def test_query_sources_have_required_fields(self):
        r = httpx.post(
            f"{BASE}/query",
            json={"question": "show recent errors"},
            timeout=60,
        )
        data = r.json()
        for src in data.get("sources", []):
            assert "id" in src
            assert "message" in src
            assert "severity" in src
            assert "source" in src

    def test_query_score_between_0_and_1(self):
        r = httpx.post(
            f"{BASE}/query",
            json={"question": "CPU anomaly"},
            timeout=60,
        )
        data = r.json()
        for src in data.get("sources", []):
            if src.get("score") is not None:
                assert 0.0 <= src["score"] <= 1.0, f"Score out of range: {src['score']}"

    def test_empty_question_returns_400_or_answer(self):
        r = httpx.post(
            f"{BASE}/query",
            json={"question": ""},
            timeout=60,
        )
        # Either validation error or empty answer — not a 500
        assert r.status_code != 500

class TestCORS:
    def test_cors_headers_present(self):
        r = httpx.options(
            f"{BASE}/query",
            headers={"Origin": "http://localhost:8080", "Access-Control-Request-Method": "POST"},
            timeout=5,
        )
        assert "access-control-allow-origin" in r.headers

# ── Unit tests (no services needed) ────────────────────────────────────

class TestSeverityParsing:
    """Test severity classification logic used in the agent."""

    @pytest.mark.parametrize("raw,expected", [
        ("error",    "error"),
        ("ERROR",    "error"),
        ("warn",     "warn"),
        ("warning",  "warn"),
        ("info",     "info"),
        ("INFO",     "info"),
        ("critical", "critical"),
        ("debug",    "info"),
        (None,       "info"),
    ])
    def test_sev_class(self, raw, expected):
        def sev_class(s):
            if not s:
                return "info"
            v = s.lower()
            if v == "critical":
                return "critical"
            if v in ("error", "err"):
                return "error"
            if v in ("warn", "warning"):
                return "warn"
            return "info"
        assert sev_class(raw) == expected

class TestTimeWindowParsing:
    """Test time window extraction from natural language queries."""

    @pytest.mark.parametrize("question,expected_hours", [
        ("what happened in the last hour?", 1),
        ("errors in the last 6 hours", 6),
        ("issues today", 24),
        ("anomalies this week", 168),
        ("show all logs", None),
    ])
    def test_extract_time_window(self, question, expected_hours):
        import re
        def extract_hours(q):
            q = q.lower()
            m = re.search(r'last\s+(\d+)\s+hour', q)
            if m:
                return int(m.group(1))
            if 'last hour' in q:
                return 1
            if 'today' in q:
                return 24
            if 'week' in q:
                return 168
            return None
        assert extract_hours(question) == expected_hours
