#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT/docker-compose.test.yml"

run() {
  local service="$1"
  echo "==> docker compose -f ${COMPOSE_FILE} run --rm ${service}"
  docker compose -f "$COMPOSE_FILE" run --rm "$service"
}

run backend-tests
run frontend-tests
