"""Точка входа: python -m ocbot_web.main."""

from __future__ import annotations

import logging
import os
import sys

from aiohttp import web
from ocbot.app import RedactingFormatter, SecretRedactionFilter
from pydantic import ValidationError

from .app import create_app
from .config import WebSettings
from .errors import validation_message

log = logging.getLogger("ocbot_web")


def configure_logging(settings: WebSettings, stream=None) -> logging.Handler:
    """Логи в stderr с вычищенными токеном бота и паролем OpenCode."""
    secrets = [settings.telegram_bot_token, settings.opencode_password]
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s", secrets)
    )
    handler.addFilter(SecretRedactionFilter(secrets))
    root = logging.getLogger()
    root.setLevel(os.environ.get("MINI_APP_LOG_LEVEL", "INFO").upper())
    root.handlers[:] = [handler]
    return handler


def main() -> int:
    try:
        settings = WebSettings.from_env()
    except ValidationError as exc:
        # Только имена полей и правила, без значений: там могут быть секреты.
        print(f"invalid configuration: {validation_message(exc)}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"invalid configuration: {type(exc).__name__}", file=sys.stderr)
        return 2
    configure_logging(settings)
    log.info(
        "starting opencode-miniapp on %s:%s",
        settings.mini_app_host,
        settings.mini_app_port,
    )
    web.run_app(
        create_app(settings),
        host=settings.mini_app_host,
        port=settings.mini_app_port,
        access_log=None,
        print=None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
