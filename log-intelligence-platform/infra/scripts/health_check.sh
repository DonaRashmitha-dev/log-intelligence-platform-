#!/bin/bash
echo "=== Log Intelligence Platform Health Check ==="

check() {
  NAME=$1; CMD=$2
  if eval "$CMD" &>/dev/null; then
    echo "  ✓ $NAME"
  else
    echo "  ✗ $NAME — NOT OK"
  fi
}

check "PostgreSQL"  "docker exec logdb pg_isready -U loguser -d logdb"
check "pgvector"    "docker exec logdb psql -U loguser -d logdb -c 'SELECT 1 FROM pg_extension WHERE extname=\'vector\';' | grep -q 1"
check "Redis"       "docker exec logredis redis-cli ping | grep -q PONG"
check "Ollama"      "curl -sf http://localhost:11434/api/tags"

echo ""
echo "=== Log row count ==="
docker exec logdb psql -U loguser -d logdb -c "SELECT count(*) FROM logs;" 2>/dev/null || echo "  (no rows yet)"
