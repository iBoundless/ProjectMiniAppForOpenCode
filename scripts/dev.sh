#!/usr/bin/env bash
# Локальная разработка: backend на 127.0.0.1:8080 и Vite с proxy на него.
# Переменные окружения backend берутся из файла $MINI_APP_ENV
# (по умолчанию ~/.config/opencode/miniapp.env), см. deploy/miniapp.env.example.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
env_file="${MINI_APP_ENV:-$HOME/.config/opencode/miniapp.env}"

cd "$root/backend"
uv sync
cd "$root/frontend"
[[ -d node_modules ]] || npm install --no-fund --no-audit

if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
fi
export MINI_APP_HOST=127.0.0.1
export MINI_APP_PORT="${MINI_APP_PORT:-8080}"

(cd "$root/backend" && exec uv run python -m ocbot_web.main) &
backend_pid=$!
trap 'kill "$backend_pid" 2>/dev/null || true' EXIT

cd "$root/frontend"
MINI_APP_BACKEND="http://127.0.0.1:${MINI_APP_PORT}" npm run dev
