#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"

cd "$root/backend"
uv sync

cd "$root/frontend"
npm install

echo "dev environment ready"
