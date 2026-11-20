# Эксплуатация OpenCode Mini App

Схема: Telegram или Safari -> HTTPS на Caddy (отдельная машина
`caddy-host`) -> `http://<внутренний адрес>:8080` на сервере OpenCode ->
локальный OpenCode `127.0.0.1:49374` и общая база бота.

Обозначения ниже: `PANEL_HOST` - публичный домен панели, `APP_IP` -
внутренний адрес сервера OpenCode, `CADDY_IP` - адрес машины с Caddy.

## 1. Сборка и установка на сервере OpenCode

```bash
sudo install -d -o "$USER" -g "$USER" /opt/opencode-miniapp
git clone <репозиторий> /opt/opencode-miniapp
cd /opt/opencode-miniapp
scripts/build.sh --check
```

`build.sh` ставит зависимости frontend (`npm ci`), собирает
`frontend/dist` и создает `backend/.venv` (`uv sync --frozen`).

## 2. Окружение

```bash
install -m 600 deploy/miniapp.env.example ~/.config/opencode/miniapp.env
$EDITOR ~/.config/opencode/miniapp.env
```

Обязательно: `TELEGRAM_BOT_TOKEN` (тот же бот), `ALLOWED_USER_IDS`,
`OCBOT_DB_PATH` (база бота), `MINI_APP_HOST=APP_IP`,
`MINI_APP_URL=https://PANEL_HOST`. Пароль OpenCode читается из
`service.json`. Файл не коммитить, права только 600.

## 3. systemd

Пользовательский юнит, как у `opencode-telegram-bot`:

```bash
install -m 644 deploy/opencode-miniapp.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now opencode-miniapp
systemctl --user status opencode-miniapp
journalctl --user -u opencode-miniapp -f
curl http://APP_IP:8080/health
```

Чтобы юнит работал без входа в систему: `loginctl enable-linger "$USER"`
(у бота это уже должно быть включено).

## 4. Firewall

Порт 8080 доступен только Caddy. Пример для nftables:
`deploy/nftables-miniapp.example` (подставить `CADDY_IP`).

```bash
sudo nft -c -f deploy/nftables-miniapp.example   # проверка
sudo nft -f deploy/nftables-miniapp.example      # применение
```

Чтобы правило пережило перезагрузку, добавьте таблицу в
`/etc/nftables.conf`. Проверка с посторонней машины: `curl APP_IP:8080`
не отвечает; с `CADDY_IP` отвечает. OpenCode (`49374`) слушает только
`127.0.0.1` и снаружи недоступен.

## 5. DNS и Caddy

1. A-запись `PANEL_HOST` указывает на внешний адрес Caddy:
   `dig +short PANEL_HOST`.
2. На машине с Caddy сохранить копию Caddyfile и добавить маршрут из
   `deploy/Caddyfile.example` (`flush_interval -1` нужен для SSE).
3. `caddy validate --config /etc/caddy/Caddyfile`.
4. `systemctl reload caddy`.
5. `curl https://PANEL_HOST/health` -> `{"status": "ok", ...}`.

## 6. Telegram (BotFather)

1. `/mybots` -> бот -> «Bot Settings» -> «Configure Mini App» ->
   «Enable Mini App», URL `https://PANEL_HOST`.
2. `/newapp` (или «Configure Mini App») -> short name `panel`: ссылка
   `https://t.me/<bot>/panel`.
3. «Menu Button» -> URL `https://PANEL_HOST`, текст «Панель».
4. Код бота менять не обязательно. Ссылку для Safari выдает сама панель:
   «Настройки» -> «Открыть в Safari» (одноразовая, 5 минут).

## 7. Обновление

```bash
cd /opt/opencode-miniapp
git pull --ff-only
scripts/build.sh --check
systemctl --user restart opencode-miniapp
```

Если обновлялся бот и пакет `ocbot`, сначала обновите закрепленный коммит в
`backend/pyproject.toml` и `uv lock`.

## 8. Откат

- Остановить панель: `systemctl --user disable --now opencode-miniapp`.
- Убрать маршрут `PANEL_HOST` из Caddyfile, `caddy validate`, reload.
- В BotFather отключить Mini App и вернуть стандартную кнопку меню.
- Удалить правило nftables (`sudo nft delete table inet miniapp`).
- При необходимости удалить DNS-запись.
- Бот, уведомления и голосовые продолжают работать: панель только
  читает и пишет те же строки через `Store`, миграции выполняет бот.
- Откат версии: `git checkout <предыдущий тег>`, `scripts/build.sh`,
  перезапуск юнита. `mini_app.db` можно удалить: пропадут только
  сессии входа панели.

## 9. Диагностика

- `journalctl --user -u opencode-miniapp`: в логах нет initData, cookie,
  токенов и текста задач; при недоступном OpenCode видны попытки
  переподключения SSE с backoff.
- `503 unavailable` в API: OpenCode не отвечает, проверьте
  `opencode service status` или перезапустите из панели («Сервис»).
- `403` при входе: ID нет в `ALLOWED_USER_IDS`.
- `401` после долгого простоя: истек `MINI_APP_SESSION_TTL`, откройте
  панель из Telegram заново.
