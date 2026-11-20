#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"

cd "$root/frontend"
npm ci
npm run build

cd "$root/backend"
uv sync

echo "build ready: frontend/dist"
