from __future__ import annotations

import hmac
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from typing import Any, Dict

from app.config import CRON_SECRET, UNIVERSE
from app.bot import tick_once
from app.data_client import fetch_pairs, fetch_server_time
from app.dashboard import dashboard_payload
from app.storage import append_event, read_events, set_kill_switch

MAX_BODY_BYTES = 16_384
LOG_TYPES = ("calls", "candles", "controls", "equity", "errors", "orders", "signals", "snapshots", "trades")


class handler(BaseHTTPRequestHandler):
    def _respond(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not CRON_SECRET:
            self._respond(503, {"error": "CRON_SECRET is not configured"})
            return False
        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {CRON_SECRET}"
        if not hmac.compare_digest(supplied, expected):
            self._respond(401, {"error": "unauthorized"})
            return False
        return True

    def _read_json(self) -> Dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("invalid Content-Length") from error
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("request body must be between 1 byte and 16 KiB")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON request body must be an object")
        return payload

    def do_GET(self) -> None:
        if self.path == "/api/health":
            try:
                server_time = fetch_server_time()
                pairs = fetch_pairs()
                missing = [symbol for symbol in UNIVERSE if symbol not in pairs]
                if missing:
                    self._respond(503, {"status": "error", "missing_pairs": missing})
                    return
                self._respond(
                    200,
                    {
                        "status": "ok",
                        "indodax_public_api": "reachable",
                        "server_time_utc": server_time,
                        "universe_pairs_available": len(UNIVERSE),
                    },
                )
            except Exception as error:
                self._respond(
                    502,
                    {
                        "status": "error",
                        "error_type": type(error).__name__,
                        "message": str(error),
                    },
                )
            return
        if self.path == "/api/metrics":
            try:
                logs = {name: read_events(name) for name in LOG_TYPES}
                self._respond(200, dashboard_payload(logs))
            except Exception as error:
                self._respond(503, {"error": type(error).__name__, "message": str(error)})
            return
        self._respond(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path == "/api/tick":
            if not self._authorized():
                return
            try:
                result = tick_once()
                self._respond(200, result)
            except Exception as error:
                self._respond(
                    502,
                    {"status": "error", "error_type": type(error).__name__, "message": str(error)},
                )
            return
        if self.path == "/api/control":
            if not self._authorized():
                return
            try:
                payload = self._read_json()
                if not isinstance(payload.get("kill_switch"), bool):
                    raise ValueError("kill_switch must be a boolean")
                timestamp = datetime.now(timezone.utc).isoformat()
                set_kill_switch(payload["kill_switch"], timestamp)
                self._respond(200, {"status": "ok", "kill_switch": payload["kill_switch"]})
            except (ValueError, json.JSONDecodeError) as error:
                self._respond(400, {"error": str(error)})
            except Exception as error:
                self._respond(503, {"error": type(error).__name__, "message": str(error)})
            return
        if self.path == "/api/export":
            if not self._authorized():
                return
            try:
                logs = {name: read_events(name) for name in LOG_TYPES}
                append_event(
                    "controls",
                    {
                        "type": "log_export",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
                self._respond(200, logs)
            except Exception as error:
                self._respond(503, {"error": type(error).__name__, "message": str(error)})
            return
        self._respond(404, {"error": "not_found"})

    def log_message(self, format: str, *args: Any) -> None:
        return
