"""Application logging configuration.

Without this, the `app.*` loggers inherit the root logger's default WARNING level
and have no handler, so every `logger.info(...)` audit record — transaction
completions, messages sent, passkey verifications, scheduler runs — is silently
dropped. The logging rules in CLAUDE.md require those to be logged.

Call `configure_logging()` once at startup (main.py), before the app is created.
"""
import logging

from app.core.config import ENVIRONMENT

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging() -> None:
    level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        app_logger.addHandler(handler)
    # Own handler emits to stdout; don't also bubble to the root/uvicorn handlers
    # (which would double-log every record).
    app_logger.propagate = False
