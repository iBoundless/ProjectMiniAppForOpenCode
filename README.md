# OpenCode Mini App

Веб-панель управления OpenCode: Telegram Mini App и PWA для iPhone.

Проект дополняет Telegram-бота
[opencode-telegram-bot](https://github.com/iBoundless/opencode-telegram-bot),
не заменяя его:
бот остается каналом голосовых сообщений, уведомлений и подтверждений,
а Mini App дает полноценный интерфейс для сессий, проектов, моделей и
управления сервисом.

## Статус

Backend (API, авторизация, SSE, раздача статики) и frontend (экраны,
PWA) готовы и покрыты тестами. Развертывание на сервере, маршрут в Caddy
и настройка Mini App в BotFather выполняются вручную по
`docs/operations.md`.

## Быстрый старт

Нужны Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 20+ и
работающий локальный OpenCode.

```bash
cp deploy/miniapp.env.example ~/.config/opencode/miniapp.env
chmod 600 ~/.config/opencode/miniapp.env
$EDITOR ~/.config/opencode/miniapp.env   # токен бота, ALLOWED_USER_IDS

scripts/build.sh --check   # npm ci, lint, тесты, сборка frontend, uv sync
scripts/dev.sh             # backend на 127.0.0.1:8080 + Vite с proxy
```

Без Vite backend сам раздает собранный `frontend/dist`:

```bash
cd backend
set -a; . ~/.config/opencode/miniapp.env; set +a
uv run python -m ocbot_web.main
curl http://127.0.0.1:8080/health
```

Вне Telegram войти можно только по одноразовой ссылке. Получить ее
локально (служебный вызов с `127.0.0.1` без `Origin`):

```bash
curl -s -X POST http://127.0.0.1:8080/api/auth/login-token \
    -H 'Content-Type: application/json' -d '{"user_id": <ID из allowlist>}'
```

## Переменные окружения

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | - | токен бота, проверка `initData` |
| `ALLOWED_USER_IDS` | - | ID Telegram через запятую |
| `OPENCODE_URL` | `http://127.0.0.1:49374` | только локальный адрес |
| `OPENCODE_SERVICE_JSON` | `~/.config/opencode/service.json` | пароль OpenCode |
| `OPENCODE_PASSWORD` | из `service.json` | если `service.json` недоступен |
| `OPENCODE_BIN` | `opencode` | для `opencode service restart` |
| `OCBOT_DB_PATH` | база бота | общая SQLite-база |
| `MINI_APP_HOST` / `MINI_APP_PORT` | `127.0.0.1` / `8080` | адрес API |
| `MINI_APP_URL` | пусто | публичный адрес: Origin и ссылки входа |
| `MINI_APP_DB_PATH` | рядом с базой бота | сессии панели и ссылки |
| `MINI_APP_INIT_DATA_MAX_AGE` | `86400` | срок `initData`, секунды |
| `MINI_APP_SESSION_TTL` | `86400` | срок сессии панели, секунды |
| `MINI_APP_STATIC_DIR` | `frontend/dist` | собранный frontend |
| `MINI_APP_LOG_LEVEL` | `INFO` | уровень логов |

## Тесты

```bash
cd backend && uv run pytest -q
cd frontend && npm test && npm run lint && npm run build
```

## Архитектура

```text
Telegram / Safari
        |
        | https://panel.example.com
        v
Caddy на caddy-host (192.0.2.20)
        |
        | http://192.0.2.10:8080
        v
opencode-miniapp (aiohttp)
        |
        +-- OpenCode API 127.0.0.1:49374
        |
        +-- общая SQLite-база бота
        |
        v
Telegram-бот (polling, голосовые, уведомления)
```

Backend использует пакет `ocbot` из репозитория бота как библиотеку:
клиент OpenCode, хранилище, профиль прав и создание задач. Отдельный
процесс Mini App не вмешивается в polling и не отправляет сообщения
в Telegram.

## Структура

```text
backend/        Python-сервис aiohttp и API
frontend/       Telegram Mini App и PWA
deploy/         systemd, Caddy, примеры конфигурации
docs/plan/      дизайн и план реализации
scripts/        сборка, dev-режим, генерация иконок
tests/          место для сквозных тестов (unit-тесты в backend и frontend)
```

## Документы

- `docs/plan/design.md` - архитектура, авторизация, безопасность.
- `docs/plan/implementation.md` - пошаговый план для реализации.
- `docs/operations.md` - DNS, Caddy, systemd, firewall, BotFather, откат.

## Ограничения

- OpenCode не публикуется в интернет.
- API Mini App слушает только внутренний интерфейс.
- Доступ только для `ALLOWED_USER_IDS`.
- Секреты хранятся только в env-файле с правами 600.
- Опасные действия требуют подтверждения.
- Длинное тире в текстах и коде не используется.
