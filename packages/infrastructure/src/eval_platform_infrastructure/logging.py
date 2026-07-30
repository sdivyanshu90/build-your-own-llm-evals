"""Structured logging configuration with safe context fields."""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any, cast

import structlog

from eval_platform_infrastructure.security import redact


def _redact_event(
    _logger: object,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> Mapping[str, Any]:
    return cast(dict[str, Any], redact(event_dict))


def configure_logging(level: str, *, json_output: bool = True) -> None:
    """Configure stdlib and structlog once for API and worker processes."""

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper(), force=True)
    renderer: structlog.types.Processor
    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _redact_event,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
