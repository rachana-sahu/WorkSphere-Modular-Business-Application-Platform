import json
import logging
import re
import sys
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "error_type",
        ):
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=True)


def configure_logging() -> None:
    logger = logging.getLogger("worksphere")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(
        isinstance(handler.formatter, JsonLogFormatter)
        for handler in logger.handlers
    ):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonLogFormatter())
        logger.addHandler(handler)


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger("worksphere.http")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        supplied_id = headers.get(b"x-request-id", b"").decode("ascii", "ignore")
        request_id = (
            supplied_id
            if _REQUEST_ID_PATTERN.fullmatch(supplied_id)
            else uuid4().hex
        )
        scope.setdefault("state", {})["request_id"] = request_id
        started = perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = list(message.get("headers", []))
                response_headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": response_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            self.logger.info(
                "HTTP request completed",
                extra={
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
