from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List

from app.config import UPSTASH_REDIS_REST_TOKEN, UPSTASH_REDIS_REST_URL
from app.execution import initial_state


class StorageError(RuntimeError):
    pass


def _command(*parts: Any) -> Any:
    if not UPSTASH_REDIS_REST_URL or not UPSTASH_REDIS_REST_TOKEN:
        raise StorageError("UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are required")
    request = urllib.request.Request(
        UPSTASH_REDIS_REST_URL,
        data=json.dumps(list(parts)).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise StorageError(f"Upstash command failed: {error}") from error
    if not isinstance(result, dict) or result.get("error"):
        raise StorageError(f"Upstash returned an error: {result}")
    return result.get("result")


def load_state() -> Dict[str, Any]:
    value = _command("GET", "indodax-dryrun:state")
    if value is None:
        return initial_state()
    state = json.loads(value)
    if not isinstance(state, dict):
        raise StorageError("Stored bot state is not a JSON object")
    return state


def save_state(state: Dict[str, Any]) -> None:
    _command("SET", "indodax-dryrun:state", json.dumps(state, separators=(",", ":"), allow_nan=False))


def append_event(event_type: str, event: Dict[str, Any]) -> None:
    encoded = json.dumps(event, separators=(",", ":"), allow_nan=False)
    _command("RPUSH", f"indodax-dryrun:log:{event_type}", encoded)


def read_events(event_type: str, start: int = 0, end: int = -1) -> List[Dict[str, Any]]:
    rows = _command("LRANGE", f"indodax-dryrun:log:{event_type}", start, end)
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise StorageError(f"Unexpected log response for {event_type}")
    return [json.loads(row) for row in rows]


def acquire_lock(timeout_seconds: int = 360) -> str:
    token = str(uuid.uuid4())
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        result = _command(
            "SET",
            "indodax-dryrun:tick-lock",
            token,
            "NX",
            "EX",
            timeout_seconds,
        )
        if result == "OK":
            return token
        time.sleep(0.25)
    raise StorageError("Another tick is active; lock acquisition timed out")


def release_lock(token: str) -> None:
    script = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('del', KEYS[1]) else return 0 end"
    )
    _command("EVAL", script, 1, "indodax-dryrun:tick-lock", token)


def set_kill_switch(enabled: bool, timestamp: str) -> None:
    token = acquire_lock()
    try:
        state = load_state()
        state["kill_switch"] = bool(enabled)
        save_state(state)
        append_event(
            "controls",
            {"type": "kill_switch", "enabled": bool(enabled), "timestamp": timestamp},
        )
    finally:
        release_lock(token)
