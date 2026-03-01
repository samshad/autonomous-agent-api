import logging
import logging.config
import sys
from pathlib import Path

import structlog
from logtail import LogtailHandler

from agent_api.core.config import settings

LOGS_DIR = Path(settings.log_dir)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging() -> None:
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    handlers_config = {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "console" if settings.debug else "json",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "app.log"),
            "maxBytes": settings.log_max_bytes,
            "backupCount": settings.log_backup_count,
            "formatter": "json",
        },
    }

    active_handlers = ["console", "file"]

    # Dynamically add Better Stack if the token exists
    if settings.betterstack_source_token:
        handlers_config["betterstack"] = {
            # Using "()" allows dictConfig to instantiate the custom class directly
            "()": LogtailHandler,
            "source_token": settings.betterstack_source_token,
            # Pass the JSON formatter to the Better Stack handler
            "formatter": "json",
        }
        active_handlers.append("betterstack")

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.processors.JSONRenderer(),
                "foreign_pre_chain": shared_processors,
            },
            "console": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.dev.ConsoleRenderer(colors=True),
                "foreign_pre_chain": shared_processors,
            },
        },
        "handlers": handlers_config,
        "loggers": {
            "": {
                "handlers": active_handlers,
                "level": settings.log_level,
            },
            "uvicorn.error": {
                "handlers": active_handlers,
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": active_handlers,
                "level": "INFO",
                "propagate": False,
            },
            "urllib3": {
                "handlers": active_handlers,
                "level": "WARNING",
                "propagate": False,
            },
            "logtail": {
                "handlers": active_handlers,
                "level": "WARNING",
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(logging_config)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
