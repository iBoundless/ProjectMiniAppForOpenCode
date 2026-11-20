# План реализации OpenCode Mini App

> Для агентных исполнителей: выполнять задачи по порядку, каждую задачу
> завершать тестами и коммитом. Не переходить к следующей задаче, пока
> текущая не зеленая.

**Цель:** веб-панель OpenCode в Telegram и Safari.

**Архитектура:** отдельный aiohttp-процесс `opencode-miniapp`, который
использует пакет `ocbot` как библиотеку и общую SQLite-базу бота. Caddy на
другой машине проксирует `panel.example.com` на внутренний порт `8080`.

**Стек:** Python 3.12, aiohttp, pydantic, pytest, aiohttp test utils; Vite,
TypeScript, React, Vitest; SQLite; Caddy.

**Дизайн:** `docs/plan/design.md`.

## Глобальные ограничения

- Python 3.12.
- Только локальный OpenCode `127.0.0.1:49374`.
- API слушает только `192.0.2.10:8080`.
- Доступ только для `ALLOWED_USER_IDS`.
- OpenCode не публикуется наружу.
- Секреты только в env с правами 600, не в Git и не в логах.
- Опасные действия требуют подтверждения.
- Только короткое тире.
- Публичный репозиторий не содержит домашних путей и названий проектов.
- Перед публикацией: все тесты и сборка frontend.

## Структура

```text
backend/
    pyproject.toml
    src/ocbot_web/
        __init__.py
        main.py
        app.py
        config.py
        auth.py
        sessions.py
        events.py
        errors.py
        static.py
        routes/
            __init__.py
            auth.py
            sessions.py
            catalog.py
            permissions.py
            service.py
            settings.py
    tests/
frontend/
    package.json
    vite.config.ts
    index.html
    src/
        main.tsx
        app/
        api/
        auth/
        components/
        pages/
        stores/
        styles/
        types/
    public/
        manifest.webmanifest
        icons/
deploy/
    opencode-miniapp.service
    Caddyfile.example
    miniapp.env.example
scripts/
    dev.sh
    build.sh
docs/
    plan/
```

---

## Этап 0. Каркас репозитория

Выполнено:

- [x] каталог `/opt/opencode-miniapp`;
- [x] `git init -b main`;
- [x] `.gitignore`;
- [x] `README.md`;
- [x] `docs/plan/design.md`;
- [x] этот план;
- [x] пустые каталоги `backend`, `frontend`, `deploy`, `tests`, `scripts`.

Критерий: `git status` чистый после первого коммита.

---

## Этап 1. Зависимость от `ocbot`

**Файлы:** `backend/pyproject.toml`, `backend/src/ocbot_web/__init__.py`.

1. Создать `backend/pyproject.toml`:

```toml
[project]
name = "ocbot-web"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
    "aiohttp>=3.9",
    "pydantic>=2.7",
    "ocbot @ git+https://github.com/iBoundless/opencode-telegram-bot",
]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ocbot_web"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

2. Зафиксировать коммит бота, на который опирается Mini App. Если нужен
   локальный код бота без push, использовать `PYTHONPATH` в dev-окружении,
   но не коммитить локальный путь в `pyproject.toml`.

3. Проверить импорт:

```bash
cd backend
uv sync
uv run python -c "import ocbot, ocbot_web; print(ocbot.__file__)"
```

Критерий: импорт работает, `uv.lock` создан.

Выполнено:

- [x] `backend/pyproject.toml`, зависимость `ocbot` закреплена на коммите
  `cbec8b9` (`tool.hatch.metadata.allow-direct-references`);
- [x] `backend/src/ocbot_web/__init__.py` с `__version__`;
- [x] `backend/tests/test_package.py`: импорт `ocbot_web` и модулей `ocbot`,
  которые использует дизайн;
- [x] `uv.lock` создан, `uv run pytest -q` зеленый.

---

## Этап 2. Конфигурация backend

**Файлы:** `backend/src/ocbot_web/config.py`, `backend/tests/test_config.py`.

Поля:

```python
class WebSettings(BaseModel):
    telegram_bot_token: str
    allowed_user_ids: list[int]
    opencode_url: str
    opencode_password: str
    opencode_service_json: Path
    ocbot_db_path: Path
    mini_app_db_path: Path
    mini_app_host: str = "127.0.0.1"
    mini_app_port: int = 8080
    mini_app_url: str = ""
    init_data_max_age: int = 86400
    session_ttl: int = 86400
```

Требования:

- `allowed_user_ids` минимум один;
- `init_data_max_age > 0`;
- `session_ttl > 0`;
- порт 1-65535;
- пароль OpenCode берется из `OPENCODE_PASSWORD` или `service.json`;
- значения не логируются.

Тесты:

- значения по умолчанию;
- переопределение env;
- пустой allowlist отвергается;
- отрицательный TTL отвергается.

Критерий: `uv run pytest tests/test_config.py -q` зеленый.

Выполнено:

- [x] `config.py`: `WebSettings.from_env`, секреты с `repr=False`,
  OpenCode только на локальном адресе, пароль из env или `service.json`;
- [x] `errors.py`: единый формат ошибок и разбор JSON по схеме;
- [x] `keys.py`: ключи зависимостей приложения;
- [x] `aiosqlite` для `mini_app.db`;
- [x] `tests/test_config.py` зеленый.

---

## Этап 3. Приложение aiohttp и `/health`

**Файлы:** `backend/src/ocbot_web/app.py`,
`backend/src/ocbot_web/main.py`, `backend/tests/test_health.py`.

1. `create_app(settings) -> web.Application`.
2. Middlewares:
   - JSON-ошибки;
   - ограничение размера тела;
   - проверка `Origin` для небезопасных методов;
   - логирование без секретов.
3. `GET /health` возвращает:

```json
{"status": "ok", "service": "opencode-miniapp", "version": "0.1.0"}
```

4. `main.py` запускает `web.run_app` на `settings.mini_app_host` и
   `mini_app_port`.

Тесты через `aiohttp.test_utils.TestClient`:

- `/health` 200 и JSON;
- неизвестный маршрут 404 в общем формате ошибки;
- тело больше лимита 413.

Критерий: тесты зеленые, ручной `curl /health` работает.

Выполнено:

- [x] `create_app` с middleware: журнал без query string, JSON-ошибки,
  лимит тела (64 КБ), проверка `Origin` для изменяющих методов;
- [x] `GET /health` (и `/api/health`);
- [x] `main.py`: `web.run_app` без access log aiohttp, логи с вычисткой
  секретов;
- [x] `tests/test_health.py` зеленый, ручной `curl /health` отвечает.

---

## Этап 4. Авторизация Telegram

**Файлы:** `backend/src/ocbot_web/auth.py`,
`backend/src/ocbot_web/routes/auth.py`, `backend/tests/test_auth.py`.

1. Функция `validate_init_data(init_data, bot_token, max_age) -> TelegramUser`.
2. Проверка:
   - обязательные поля `hash`, `auth_date`, `user`;
   - HMAC-SHA256;
   - `auth_date` не старше max_age;
   - `user.id` в allowlist.
3. Серверная сессия:
   - случайный ID 32 байта;
   - хранение хеша в `mini_app.db`;
   - cookie `oc_panel_session`, HttpOnly, Secure, SameSite=Lax;
   - TTL.
4. Endpoints:
   - `POST /api/auth/telegram`;
   - `GET /api/auth/me`;
   - `POST /api/auth/logout`.
5. Декоратор `login_required`.

Тесты:

- валидная подпись проходит;
- неверная подпись 401;
- просроченный `auth_date` 401;
- чужой ID 403;
- cookie выставляется с HttpOnly;
- `me` без cookie 401;
- logout удаляет сессию.

Критерий: тесты зеленые, в логах нет `init_data`.

Выполнено:

- [x] `validate_init_data`: HMAC-SHA256, сравнение за постоянное время,
  `auth_date` с допуском 60 секунд на часы, allowlist;
- [x] `AuthStore` (`mini_app.db`, WAL, права 600): только SHA-256 хеши;
- [x] cookie `oc_panel_session`: HttpOnly, Secure, SameSite=Lax, TTL;
- [x] `POST /api/auth/telegram`, `GET /api/auth/me`, `POST /api/auth/logout`,
  `login_required`; пользователь, убранный из allowlist, получает 403;
- [x] `tests/test_auth.py` зеленый, `init_data` в логи не попадает.

---

## Этап 5. Одноразовые ссылки для PWA

**Файлы:** `backend/src/ocbot_web/auth.py`,
`backend/src/ocbot_web/routes/auth.py`, `backend/tests/test_login_tokens.py`.

1. `create_login_token(user_id, ttl=300) -> str`:
   - 32 случайных байта;
   - в базе только SHA-256 хеш;
   - TTL и `used_at`.
2. `POST /api/auth/login-token` создает токен (только для авторизованного
   пользователя или для служебного вызова с локального адреса).
3. `GET /login?t=...` проверяет токен, гасит его, ставит cookie и
   редиректит на `/`.
4. Повторное использование токена 401.
5. Просроченный токен 401.

Тесты:

- токен одноразовый;
- просроченный отвергается;
- в базе нет открытого токена;
- редирект на `/`.

Критерий: тесты зеленые.

Выполнено:

- [x] `AuthStore.create_login_token` / `consume_login_token`: хеш SHA-256,
  TTL 5 минут, атомарное гашение через `used_at`;
- [x] `POST /api/auth/login-token`: для вошедшего пользователя или для
  служебного вызова с `127.0.0.1` без `Origin` и `X-Forwarded-For`;
- [x] `GET /login?t=...`: cookie и редирект 302 на `/`, иначе HTML 401;
- [x] `tests/test_login_tokens.py` зеленый, токен не попадает в логи.

---

## Этап 6. API сессий

**Файлы:** `backend/src/ocbot_web/sessions.py`,
`backend/src/ocbot_web/routes/sessions.py`,
`backend/tests/test_sessions_api.py`.

1. `GET /api/sessions`:
   - page, limit (макс. 50), search, status;
   - только корневые сессии;
   - проект, модель, статус, стоимость;
   - подписка текущего пользователя.
2. `GET /api/sessions/{id}`:
   - карточка;
   - последний текст ассистента;
   - дочерние сессии не отдельным списком.
3. `POST /api/sessions`:
   - directory, model, agent, prompt;
   - проверка абсолютного пути и существования каталога;
   - `create_bot_session` с `BOT_SESSION_PERMISSIONS`;
   - активная сессия и подписка для chat_id = Telegram ID.
4. `POST /api/sessions/{id}/prompt`:
   - busy -> 409 с `draft_id`;
   - свободна -> `prompt` queue;
   - `delivery` только `queue` или `steer`.
5. `POST /api/sessions/{id}/interrupt`.
6. `DELETE /api/sessions/{id}`:
   - удалить в OpenCode;
   - `store.remove_session`.

Тесты:

- список и пагинация;
- создание задачи;
- busy-ответ;
- prompt;
- interrupt;
- delete;
- недоступный OpenCode -> 503;
- отсутствующая сессия -> 404.

Критерий: тесты зеленые.

Выполнено:

- [x] `sessions.py`: сериализация, список корневых сессий с фильтром,
  пагинацией и подпиской, карточка с последним текстом, создание задачи
  через `create_bot_session` (или те же шаги с `agent`), `DraftStore`
  для черновиков занятой сессии;
- [x] `routes/sessions.py`: список, карточка, создание, prompt (409 с
  `draft_id`, `queue`/`steer`), interrupt, удаление с `confirm=true`;
- [x] `tests/fakes.py`: фейковый OpenCode; `tests/test_sessions_api.py`
  зеленый.

---

## Этап 7. Проекты, модели, агенты

**Файлы:** `backend/src/ocbot_web/routes/catalog.py`,
`backend/tests/test_catalog.py`.

1. `GET /api/projects`:
   - сортировка по `time.active`;
   - поля id, canonical, title.
2. `GET /api/models?directory=`:
   - дедупликация;
   - сортировка;
   - provider, model, label.
3. `GET /api/agents?directory=`:
   - id, label, mode.

Тесты:

- сортировка проектов;
- дедупликация моделей;
- недоступный OpenCode -> 503.

Критерий: тесты зеленые.

Выполнено:

- [x] `routes/catalog.py`: `GET /api/projects` (по `time.active`),
  `GET /api/models?directory=` (без выключенных, дедупликация по
  provider/model, сортировка), `GET /api/agents?directory=` (без скрытых);
- [x] `tests/test_catalog.py` зеленый.

---

## Этап 8. Уведомления и подписки

**Файлы:** `backend/src/ocbot_web/routes/settings.py`,
`backend/tests/test_settings_api.py`.

1. `POST /api/sessions/{id}/subscribe`.
2. `DELETE /api/sessions/{id}/subscribe`.
3. `GET /api/settings/notifications`:
   - notify_all;
   - subscribed_sessions.
4. `POST /api/settings/notifications`:
   - только `notify_all`.

Тесты:

- подписка и отписка;
- notify_all;
- изменения видны через `Store`.

Критерий: тесты зеленые, бот использует те же строки.

Выполнено:

- [x] `routes/settings.py`: подписка и отписка через `Store.subscribe` /
  `unsubscribe`, `GET`/`POST /api/settings/notifications` (только
  `notify_all`, список подписок читается из таблицы бота только SELECT);
- [x] `tests/test_settings_api.py` зеленый, изменения видны через `Store`.

---

## Этап 9. Запросы прав

**Файлы:** `backend/src/ocbot_web/routes/permissions.py`,
`backend/tests/test_permissions_api.py`.

1. `GET /api/permissions`:
   - список pending из OpenCode;
   - только сессии, доступные пользователю.
2. `POST /api/permissions/{id}/reply`:
   - decision `once | always | reject`;
   - вызов `client.reply_permission`;
   - 404, если уже решено.
3. Не менять `permission_messages` бота.

Тесты:

- список;
- решение;
- повторное решение 404;
- чужая сессия не видна.

Критерий: тесты зеленые.

Выполнено:

- [x] `sessions.Visibility`: сессия видна при подписке на нее или на
  корень, активной сессии или `notify_all`;
- [x] `routes/permissions.py`: список pending (видимые сессии и запросы,
  которые бот отправил этому пользователю), ответ `once | always | reject`,
  404 для решенного или чужого запроса, `permission_messages` только читаются;
- [x] `tests/test_permissions_api.py` зеленый.

---

## Этап 10. API сервиса

**Файлы:** `backend/src/ocbot_web/routes/service.py`,
`backend/tests/test_service_api.py`.

1. `GET /api/service/status`:
   - running, version, url, busy_count.
2. `POST /api/service/restart`:
   - обязательное поле `confirm: true`;
   - вернуть busy_count перед перезапуском;
   - вызвать `ServiceController.restart`;
   - не перезапускать хост.

Тесты:

- статус;
- без confirm 400;
- перезапуск с confirm;
- таймаут -> 503.

Критерий: тесты зеленые.

Выполнено:

- [x] `routes/service.py`: `GET /api/service/status` (running, version,
  url, busy_count, restarting), `POST /api/service/restart` только с
  `confirm: true`, один перезапуск за раз (409), таймаут подъема 503;
- [x] `ServiceController` бота создается при старте (`WebSettings`
  совместим по `opencode_bin` и `opencode_url`), хост не перезапускается;
- [x] `tests/test_service_api.py` зеленый.

---

## Этап 11. SSE

**Файлы:** `backend/src/ocbot_web/events.py`,
`backend/src/ocbot_web/routes/events.py`,
`backend/tests/test_sse.py`.

1. Один фоновый потребитель OpenCode SSE.
2. Реестр подключений: session cookies, набор сессий, очередь.
3. `GET /api/events`:
   - `text/event-stream`;
   - heartbeat 20 секунд;
   - фильтрация по сессиям пользователя и notify_all;
   - `permission.asked` только владельцу.
4. Очистка при отключении.
5. Backoff при разрыве OpenCode SSE.

Тесты:

- подключение требует авторизации;
- событие подписанной сессии приходит;
- чужая сессия не приходит;
- notify_all пропускает все;
- отключение удаляет подписку;
- heartbeat.

Критерий: тесты зеленые, ручная проверка `curl -N /api/events`.

Выполнено:

- [x] `events.py`: `EventHub` - один фоновый потребитель `client.events()`
  с backoff, реестр подключений с ограниченной очередью (старое
  отбрасывается), фильтр по `Visibility` (подписка, корень, активная,
  `notify_all`, только что созданные), перечитывание подписок раз в 5 секунд;
- [x] `GET /api/events`: `text/event-stream`, `retry`, heartbeat 20 секунд
  с повторной проверкой сессии (logout закрывает поток), очистка при
  отключении и при остановке сервера;
- [x] `tests/test_sse.py` зеленый; ручной `curl` без cookie дает 401,
  backoff при отказе OpenCode виден в логе.

---

## Этап 12. Frontend: каркас

**Файлы:** `frontend/package.json`, `frontend/vite.config.ts`,
`frontend/index.html`, `frontend/src/main.tsx`.

1. Vite + React + TypeScript.
2. `vite.config.ts`: proxy `/api` на `http://127.0.0.1:8080` в dev.
3. Скрипты:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "lint": "eslint ."
  }
}
```

4. Базовая тема, safe area, Telegram SDK.
5. `Telegram.WebApp.ready()` и `expand()`.

Критерий: `npm run build` и `npm test` проходят.

---

## Этап 13. Frontend: экраны

**Файлы:** `frontend/src/pages/*`, `frontend/src/components/*`,
`frontend/src/api/*`, `frontend/src/stores/*`.

1. Вход:
   - `initData` -> `/api/auth/telegram`;
   - ошибка доступа;
   - PWA: ссылка с токеном.
2. Главная:
   - активные и последние сессии;
   - статус сервиса;
   - кнопка новой задачи.
3. Новая задача:
   - проект, модель, агент, текст;
   - запуск;
   - busy-состояние.
4. Сессия:
   - прогресс;
   - поток ответа;
   - отправка текста;
   - queue/steer;
   - стоп, удаление, подписка.
5. Сервис:
   - статус;
   - перезапуск с подтверждением.
6. Права:
   - список;
   - три решения.
7. Общие компоненты:
   - кнопки;
   - диалог подтверждения;
   - тосты;
   - скелетоны.

Критерий: все экраны собираются, базовые тесты компонентов зеленые.

---

## Этап 14. PWA

**Файлы:** `frontend/public/manifest.webmanifest`,
`frontend/public/sw.js`, `frontend/public/icons/*`.

1. Manifest: name, short_name, display standalone, start_url, theme.
2. Service worker: кэш только статики.
3. API и SSE не кэшировать.
4. Обновление при `visibilitychange`.
5. Safe area для iPhone.
6. `apple-touch-icon`.

Критерий: Lighthouse PWA без критических ошибок, приложение
открывается с домашнего экрана.

---

## Этап 15. Сборка и раздача

**Файлы:** `backend/src/ocbot_web/static.py`,
`backend/src/ocbot_web/app.py`, `scripts/build.sh`.

1. `npm run build` кладет файлы в `frontend/dist`.
2. Backend раздает `frontend/dist`:
   - `/` -> `index.html`;
   - `/assets/*` -> статика;
   - неизвестный путь -> `index.html` (SPA).
3. `/api/*` не перехватывается статикой.
4. Кэш-заголовки для assets, no-cache для index.

Тесты:

- `/` отдает index;
- `/assets/app.js` отдает файл;
- `/api/health` не перехвачен;
- 404 для отсутствующего asset.

Критерий: собранный frontend открывается локально.

---

## Этап 16. Интеграция с ботом

**Файлы:** внешний репозиторий `opencode-telegram-bot` (опционально).

1. В BotFather настроить Mini App:
   - URL `https://panel.example.com`;
   - short name `panel`;
   - menu button.
2. Получить ссылку `https://t.me/<bot>/panel`.
3. Опционально добавить в бота кнопку «Открыть панель»:
   - inline `web_app`;
   - и «Открыть в Safari» с одноразовой ссылкой.
4. Голосовые и уведомления не менять.

Критерий: Mini App открывается из Telegram, бот продолжает работать.

---

## Этап 17. Caddy и сеть

**Файлы:** `deploy/Caddyfile.example`, `deploy/opencode-miniapp.service`,
`deploy/miniapp.env.example`.

1. Проверить DNS `panel.example.com`.
2. На `caddy-host` сохранить Caddyfile.
3. Добавить:

```caddy
panel.example.com {
    reverse_proxy 192.0.2.10:8080
}
```

4. `caddy validate`.
5. Перезагрузить Caddy.
6. Проверить HTTPS и `/health`.
7. На текущем сервере разрешить `8080` только с `192.0.2.20`.
8. Установить systemd-юнит `opencode-miniapp`.

Критерий: `https://panel.example.com/health` отвечает, OpenCode наружу
недоступен.

---

## Этап 18. Тесты и качество

1. Backend:

```bash
cd backend
uv run pytest -q
```

2. Frontend:

```bash
cd frontend
npm test
npm run build
```

3. Проверить отсутствие секретов:

```bash
git grep -nE 'bot[0-9]+:|password|token' -- . ':!package-lock.json' ':!uv.lock'
```

4. Проверить, что в репозитории нет домашних путей и названий проектов.

5. Проверить логи на отсутствие `init_data`, cookie, токенов.

Критерий: все тесты зеленые, сборка проходит, секретов нет.

---

## Этап 19. Живое тестирование

1. Открыть `https://panel.example.com` в Telegram.
2. Проверить отказ постороннему пользователю.
3. Создать задачу.
4. Увидеть прогресс и ответ.
5. Отправить дополнительный текст.
6. Остановить сессию.
7. Удалить сессию.
8. Ответить на запрос прав.
9. Проверить уведомление в Telegram.
10. Отправить голосовое в бота.
11. Открыть приложение в Safari по одноразовой ссылке.
12. Добавить на домашний экран iPhone.
13. Свернуть и вернуть приложение: SSE восстановился.
14. Перезапустить OpenCode с подтверждением.

Критерий: все пункты проходят.

---

## Этап 20. Документация и релиз

1. Обновить `README.md`: запуск, env, тесты.
2. Обновить `docs/plan/design.md` по фактическим решениям.
3. Добавить `docs/operations.md`: DNS, Caddy, systemd, откат.
4. Добавить `scripts/dev.sh` и `scripts/build.sh`.
5. Коммиты по этапам.
6. Публикация в GitHub только после отдельного подтверждения.
7. Не делать force-push без отдельного разрешения.

Критерий: новый человек может развернуть проект по документации.

---

## Порядок коммитов

```text
chore: scaffold mini app repository
feat: add web settings and health endpoint
feat: validate Telegram Mini App authentication
feat: add session API
feat: add catalog API
feat: add permissions and settings API
feat: add service API
feat: stream OpenCode events over SSE
feat: add Mini App frontend
feat: add PWA support
feat: serve built frontend
test: cover Mini App API and auth
docs: describe deployment and operations
```
