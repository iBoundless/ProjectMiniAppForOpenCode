#!/usr/bin/env bash
# Сборка: frontend в frontend/dist, окружение backend; с --check еще тесты.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"

cd "$root/frontend"
npm ci --no-fund --no-audit
if [[ "${1:-}" == "--check" ]]; then
    npm run lint
    npm test
fi
npm run build

cd "$root/backend"
uv sync --frozen
if [[ "${1:-}" == "--check" ]]; then
    uv run pytest -q
fi

echo "build ready: frontend/dist (backend раздает ее сам)"
