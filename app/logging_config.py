"""Stderr logging plus optional Grafana Loki via tb-loki-central-logger."""
import logging
import os
import sys
from pathlib import Path

from tb_loki_central_logger import LokiHandler, basic_auth_from_env, load_dotenv

from . import __version__
from .request_context import get_request_id, get_session_id

logger = logging.getLogger("layer_gateway.embed")


class _RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        rid = get_request_id()
        sid = get_session_id()
        # Outside RequestContextMiddleware (startup/shutdown), context defaults to "-".
        # During a request, middleware always sets request_id; session stays "-" if no header.
        if rid == "-":
            record.request_id = "-"
            record.session_id = "-"
        else:
            record.request_id = rid
            record.session_id = sid
        return True


_LOG_FMT = (
    "%(asctime)s %(levelname)s %(name)s "
    "request_id=%(request_id)s session_id=%(session_id)s %(message)s"
)

_loki_handler: LokiHandler | None = None


def setup_logging() -> None:
    global _loki_handler
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.filters.clear()
    logger.propagate = False
    logger.addFilter(_RequestContextFilter())

    stderr = logging.StreamHandler(sys.stderr)
    stderr.setLevel(logging.INFO)
    stderr.setFormatter(logging.Formatter(_LOG_FMT))
    logger.addHandler(stderr)

    auth = basic_auth_from_env()
    if auth is not None:
        _loki_handler = LokiHandler(
            labels={
                "service": "layer-gateway",
                "component": "embed",
                "env": os.getenv("ENV", "dev"),  # dev / staging / prod
                "version": __version__,
            },
            basic_auth=auth,
        )
        _loki_handler.setLevel(logging.INFO)
        _loki_handler.setFormatter(logging.Formatter(_LOG_FMT))
        logger.addHandler(_loki_handler)
        logger.info("centralized Loki logging enabled")
    else:
        logger.info("Loki disabled (set GRAFANA_CLOUD_WRITE_API_KEY to ship logs to Grafana)")


def shutdown_logging() -> None:
    global _loki_handler
    if _loki_handler is not None:
        logger.removeHandler(_loki_handler)
        _loki_handler.close()
        _loki_handler = None
