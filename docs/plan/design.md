# Дизайн OpenCode Mini App

Дата: 2026-11-20
Статус: на согласовании

## 1. Зачем

Telegram-бот хорошо работает для быстрых действий: отправить голосовое,
подтвердить права, получить уведомление. Для просмотра нескольких задач,
чтения длинных ответов и настройки сессий не хватает полноценного экрана.

Mini App дает:

- список активных и последних сессий;
- карточку сессии с прогрессом и ответом;
- создание задачи с выбором проекта, модели и агента;
- управление подписками и уведомлениями;
- статус и перезапуск OpenCode;
- работу с iPhone как PWA.

## 2. Границы

Входит:

- Telegram Mini App;
- PWA для Safari на iPhone;
- backend API для панели;
- авторизация через Telegram и одноразовую ссылку;
- SSE для обновлений;
- управление сессиями, проектами, моделями, агентами;
- запросы прав;
- настройки уведомлений;
- перезапуск OpenCode с подтверждением;
- раздача frontend;
- документация и тесты.

Не входит:

- замена Telegram-бота;
- отправка голосовых из Mini App;
- терминал и произвольные команды;
- управление хостом и systemd;
- несколько владельцев;
- диаризация и запись аудио;
- биллинг;
- мобильное нативное приложение на Swift.

## 3. Топология

```text
Telegram client / Safari
        |
        | HTTPS panel.example.com
        v
Caddy (caddy-host, 192.0.2.20)
        |
        | HTTP 192.0.2.10:8080 (внутренняя сеть)
        v
opencode-miniapp (aiohttp, bss)
        |
        +-- OpenCode API 127.0.0.1:49374
        +-- SQLite бота
        +-- SQLite Mini App (сессии авторизации)
```

Публично открыт только Caddy на `caddy-host`. Порт `8080` текущего
сервера доступен только с `192.0.2.20`.

DNS:

```text
panel.example.com A <публичный IP caddy-host>
```

## 4. Компоненты

### 4.1. Backend `opencode-miniapp`

Отдельный процесс на aiohttp. Использует пакет `ocbot` как библиотеку:

- `ocbot.opencode.client.OpencodeClient` - OpenCode API;
- `ocbot.store.Store` - общая база бота;
- `ocbot.taskflow.create_bot_session` - создание задачи с профилем прав;
- `ocbot.permissions_profile.BOT_SESSION_PERMISSIONS` - строгие права;
- `ocbot.config.Settings` - общие настройки;
- `ocbot.formatting` - при необходимости.

Что backend не делает:

- не запускает Telegram polling;
- не отправляет сообщения в Telegram;
- не дублирует уведомления;
- не перезаписывает progress-состояние бота;
- не меняет systemd и Caddy.

### 4.2. Хранилище

Общая база бота:

- `chats`, `subscriptions`, `permission_messages`, `progress`, `meta`.

Mini App не удаляет и не изменяет строки `permission_messages`: ими
владеет бот.

Отдельная база Mini App `mini_app.db`:

- `auth_sessions` - серверные сессии;
- `login_tokens` - одноразовые ссылки для PWA.

Обе базы SQLite в режиме WAL. Запись в общую базу идет через методы
`Store`.

### 4.3. Frontend

Vite, TypeScript, React. Сборка в статические файлы, которые раздает
backend. Отдельного frontend-сервера нет.

Экраны:

- вход и ошибка доступа;
- главная;
- новая задача;
- сессия;
- сервис;
- запросы прав;
- настройки уведомлений.

### 4.4. Caddy

На `caddy-host` добавляется только маршрут:

```caddy
panel.example.com {
    reverse_proxy 192.0.2.10:8080
}
```

TLS и сертификат остаются на Caddy. OpenCode и backend наружу не
публикуются.

## 5. Авторизация

### 5.1. Telegram Mini App

Frontend передает `Telegram.WebApp.initData`:

```http
POST /api/auth/telegram
{"init_data": "..."}
```

Backend:

1. Разбирает query string.
2. Считает HMAC-SHA256 от `data_check_string` с ключом
   `HMAC_SHA256("WebAppData", bot_token)`.
3. Сравнивает подпись за постоянное время.
4. Проверяет `auth_date` не старше `MINI_APP_INIT_DATA_MAX_AGE`.
5. Извлекает `user.id`.
6. Проверяет ID в `ALLOWED_USER_IDS`.
7. Создает серверную сессию и ставит HttpOnly cookie.

Telegram ID из тела запроса не принимается.

### 5.2. PWA и Safari

Одноразовая ссылка:

1. Пользователь нажимает в боте «Открыть в Safari».
2. Бот создает токен: 32 случайных байта, TTL 5 минут, одно использование.
3. Ссылка: `https://panel.example.com/login?t=<token>`.
4. Backend проверяет хеш токена, гасит его и создает сессию.
5. Cookie: `HttpOnly`, `Secure`, `SameSite=Lax`.

В первой версии кнопку в боте можно заменить ручной ссылкой из
BotFather. Кодовое изменение бота не обязательно.

### 5.3. Сессия

- Cookie `oc_panel_session`.
- TTL `MINI_APP_SESSION_TTL`, по умолчанию 24 часа.
- При каждом запросе проверяется срок и пользователь.
- `POST /api/auth/logout` удаляет сессию.
- `GET /api/auth/me` возвращает профиль.

## 6. API

```text
GET    /health
POST   /api/auth/telegram
GET    /api/auth/me
POST   /api/auth/logout

GET    /api/sessions?page&limit&search&status
GET    /api/sessions/{id}
POST   /api/sessions
POST   /api/sessions/{id}/prompt
POST   /api/sessions/{id}/interrupt
DELETE /api/sessions/{id}

GET    /api/projects
GET    /api/models
GET    /api/agents

POST   /api/sessions/{id}/subscribe
DELETE /api/sessions/{id}/subscribe
GET    /api/settings/notifications
POST   /api/settings/notifications

GET    /api/permissions
POST   /api/permissions/{id}/reply

GET    /api/service/status
POST   /api/service/restart

GET    /api/events
```

Формат ошибок:

```json
{
  "error": {
    "code": "not_found",
    "message": "Сессия не найдена"
  }
}
```

Коды: `unauthorized`, `forbidden`, `not_found`, `conflict`, `unavailable`,
`validation`, `internal`.

## 7. SSE

`GET /api/events` после авторизации.

События:

```text
session.execution.started
session.text.delta
session.reasoning.delta
session.tool.input.started
session.tool.success
session.tool.failed
session.execution.succeeded
session.execution.failed
session.execution.interrupted
session.idle
permission.asked
permission.replied
```

Фильтрация:

- события подписанных сессий;
- события всех сессий при `notify_all`;
- события сессий, созданных этим пользователем;
- запросы прав, адресованные этому пользователю.

Heartbeat каждые 20 секунд. При разрыве frontend переподключается с
backoff. Backend удаляет соединение из реестра при отключении.

## 8. Безопасность

- Проверка подписи Telegram и `auth_date`.
- Allowlist по числовому ID.
- HttpOnly cookie, без токенов в localStorage.
- Одноразовые ссылки: TTL, одно использование, хеш в базе.
- Ограничение доступа к порту 8080 по IP.
- CSRF: SameSite cookie + проверка `Origin` для изменяющих методов.
- Никаких секретов в логах, ответах и Git.
- Опасные действия только после явного подтверждения.
- Перезапуск только сервиса OpenCode, не хоста.
- Никакого выполнения произвольных команд из API.
- Размер запросов ограничен, JSON валидируется схемами.

## 9. PWA

- `manifest.webmanifest`.
- `apple-touch-icon`.
- `display: standalone`.
- Service worker кэширует только статику.
- API и SSE не кэшируются.
- При возврате из фона список сессий обновляется.
- SSE переподключается после пробуждения iPhone.
- Safe area для iPhone.

## 10. Деплой

Новый systemd-юнит:

```text
opencode-miniapp.service
```

Параметры:

```text
WorkingDirectory=/opt/opencode-miniapp
EnvironmentFile=%h/.config/opencode/miniapp.env
ExecStart=/opt/opencode-miniapp/.venv/bin/python -m ocbot_web.main
```

Переменные:

```env
TELEGRAM_BOT_TOKEN=...
ALLOWED_USER_IDS=...
OPENCODE_URL=http://127.0.0.1:49374
OPENCODE_SERVICE_JSON=~/.config/opencode/service.json
OCBOT_DB_PATH=/var/lib/opencode-telegram-bot/bot.db
MINI_APP_HOST=192.0.2.10
MINI_APP_PORT=8080
MINI_APP_URL=https://panel.example.com
MINI_APP_DB_PATH=/var/lib/opencode-telegram-bot/mini_app.db
MINI_APP_INIT_DATA_MAX_AGE=86400
MINI_APP_SESSION_TTL=86400
```

## 11. Откат

- Остановить `opencode-miniapp`.
- Убрать маршрут из Caddyfile и перезагрузить Caddy.
- Удалить DNS-запись при необходимости.
- Telegram-бот и голосовые остаются рабочими.

## 12. Риски

- Два процесса к одной SQLite: WAL смягчает, но запись сериализуется.
  Решение: короткие транзакции, без долгих блокировок.
- Дублирование SSE-подключений к OpenCode: допустимо, нагрузка мала.
- Изменение схемы бота: Mini App должен переживать отсутствие новых
  таблиц, миграции выполняет бот.
- Caddy на другой машине: сетевой доступ и DNS должны быть проверены до
  включения маршрута.
- iPhone усыпляет вкладки: SSE и таймеры могут останавливаться, нужен
  reconnect и refresh при `visibilitychange`.

## 13. Фактические решения

- Зависимости приложения (`AuthStore`, `Store`, `OpencodeClient`,
  `ServiceController`, `EventHub`) создаются при старте, в тестах
  подставляются фейки.
- Ссылку для Safari выдает сама панель (`POST /api/auth/login-token`,
  «Настройки» -> «Открыть в Safari»), а также служебный вызов с
  `127.0.0.1`; изменение бота не требуется.
- Видимость сессий одна для API прав и SSE: подписка на сессию или ее
  корень, активная сессия, `notify_all`, только что созданные; запросы
  прав, отправленные ботом пользователю, видны ему всегда.
- `POST /api/sessions/{id}/prompt` без `delivery` в занятую сессию
  возвращает 409 с `draft_id`; черновик живет 10 минут в памяти.
- Удаление сессии и перезапуск OpenCode требуют явного подтверждения и
  на frontend (диалог), и в API (`confirm=true`).
- SSE: одно подключение к OpenCode, очередь на клиента ограничена 500
  событиями (старые отбрасываются), heartbeat 20 секунд с повторной
  проверкой сессии входа, подписки перечитываются раз в 5 секунд.
- Frontend без роутера и стейт-менеджера: маршруты по hash, состояние в
  компонентах; backend раздает `frontend/dist` с fallback на `index.html`.
- Service worker кэширует только статику; `/api/*`, `/login`, `/health`
  и SSE идут мимо него.
