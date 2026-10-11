import logging
import sys
import time
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("customer_journey_api")


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for production and development."""
    log_format = "%(asctime)s [%(levelname)s] [req_id=%(request_id)s] %(name)s: %(message)s"

    # Context filter to ensure request_id is always present in log records
    class RequestContextFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if not hasattr(record, "request_id"):
                record.request_id = "-"
            return True

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(log_format))
    handler.addFilter(RequestContextFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())
    # Remove existing default handlers to prevent duplicate output
    root_logger.handlers = [handler]

    # Silence verbose third-party loggers
    logging.getLogger("google.cloud").setLevel(logging.WARNING)
    logging.getLogger("google.auth").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that records execution timing, status codes, and sets correlation ID.
    Never logs sensitive payloads, credentials, or API keys.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.perf_counter()

        # Inject request_id into state so downstream components can use it
        request.state.request_id = request_id

        response: Response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Include request ID in response header for client tracking
        response.headers["X-Request-ID"] = request_id

        # Skip noisy logging for repeated health checks if desired, or log cleanly
        logger.info(
            f"method={request.method} path={request.url.path} "
            f"status={response.status_code} duration={duration_ms:.2f}ms "
            f"ip={request.client.host if request.client else 'unknown'}",
            extra={"request_id": request_id},
        )

        return response
