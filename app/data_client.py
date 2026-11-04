from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Tuple

from app.config import INDODAX_BASE_URL, TIMEFRAME_SECONDS

MAX_ATTEMPTS = 3
HTTP_TIMEOUT_SECONDS = 8


class IndodaxError(RuntimeError):
    pass


def fetch_json(url: str) -> Any:
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "indodax-dry-run/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                body = response.read()
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, (dict, list)):
                raise IndodaxError("Indodax returned a non-object JSON response")
            return payload
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, IndodaxError) as error:
            last_error = error
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(0.25 * (2**attempt))
    raise IndodaxError(f"request failed after {MAX_ATTEMPTS} attempts: {last_error}")


def fetch_server_time() -> int:
    payload = fetch_json(f"{INDODAX_BASE_URL}/api/server_time")
    timestamp = int(payload["server_time"])
    return timestamp // 1000 if timestamp > 10_000_000_000 else timestamp


def fetch_pairs() -> Dict[str, Dict[str, Any]]:
    payload = fetch_json(f"{INDODAX_BASE_URL}/api/pairs")
    if not isinstance(payload, list):
        raise IndodaxError("Unexpected /api/pairs response")
    pairs: Dict[str, Dict[str, Any]] = {}
    for pair in payload:
        if not isinstance(pair, dict) or not pair.get("symbol"):
            continue
        symbol = str(pair["symbol"]).upper()
        pairs[symbol] = pair
    return pairs


def normalize_candles(payload: Any) -> List[Dict[str, float]]:
    rows = (
        payload.get("value", [])
        if isinstance(payload, dict)
        else payload
        if isinstance(payload, list)
        else []
    )
    if not isinstance(rows, list):
        raise IndodaxError("Unexpected history_v2 candle response")
    normalized: Dict[int, Dict[str, float]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            candle = {
                "time": int(row.get("Time", row.get("time"))),
                "open": float(row.get("Open", row.get("open"))),
                "high": float(row.get("High", row.get("high"))),
                "low": float(row.get("Low", row.get("low"))),
                "close": float(row.get("Close", row.get("close"))),
                "volume": float(row.get("Volume", row.get("volume"))),
            }
        except (TypeError, ValueError):
            continue
        normalized[candle["time"]] = candle
    return [normalized[timestamp] for timestamp in sorted(normalized)]


def fetch_candles(symbol: str, start: int, end: int) -> List[Dict[str, float]]:
    params = urllib.parse.urlencode(
        {"symbol": symbol, "tf": "60" if TIMEFRAME_SECONDS == 3600 else "240", "from": start, "to": end}
    )
    payload = fetch_json(f"{INDODAX_BASE_URL}/tradingview/history_v2?{params}")
    return normalize_candles(payload)


def closed_candles(candles: List[Dict[str, float]], server_time: int) -> List[Dict[str, float]]:
    return [
        candle
        for candle in candles
        if int(candle["time"]) + TIMEFRAME_SECONDS <= server_time
    ]


def _book_level(level: Any) -> Tuple[float, float]:
    if isinstance(level, dict):
        values = level.get("value")
        if not isinstance(values, (list, tuple)) or len(values) < 2:
            raise IndodaxError("Invalid order book level")
        return float(values[0]), float(values[1])
    if isinstance(level, (list, tuple)) and len(level) >= 2:
        return float(level[0]), float(level[1])
    raise IndodaxError("Invalid order book level")


def normalize_order_book(payload: Any) -> Dict[str, List[Tuple[float, float]]]:
    if not isinstance(payload, dict):
        raise IndodaxError("Unexpected depth response")
    bids = [_book_level(level) for level in payload.get("buy", payload.get("bids", []))]
    asks = [_book_level(level) for level in payload.get("sell", payload.get("asks", []))]
    bids = sorted((level for level in bids if level[0] > 0 and level[1] > 0), reverse=True)
    asks = sorted((level for level in asks if level[0] > 0 and level[1] > 0))
    return {"bids": bids, "asks": asks}


def fetch_order_book(symbol: str) -> Tuple[Dict[str, List[Tuple[float, float]]], Any]:
    raw = fetch_json(f"{INDODAX_BASE_URL}/api/depth/{symbol.lower()}")
    return normalize_order_book(raw), raw


def indicator_window_error(candles: List[Dict[str, float]]) -> str | None:
    required = candles[-169:]
    if len(required) < 169:
        return "insufficient_indicator_history"
    for previous, current in zip(required, required[1:]):
        if int(current["time"]) - int(previous["time"]) != TIMEFRAME_SECONDS:
            return "missing_candle_in_indicator_window"
    for candle in required:
        if any(candle[key] <= 0 for key in ("open", "high", "low", "close", "volume")):
            return "zero_or_negative_price_or_volume"
    return None


def validate_candles(candles: List[Dict[str, float]], server_time: int) -> str | None:
    closed = closed_candles(candles, server_time)
    if not closed:
        return "no_closed_candles"
    if server_time - (int(closed[-1]["time"]) + TIMEFRAME_SECONDS) > 2 * TIMEFRAME_SECONDS:
        return "stale_last_closed_candle"
    return indicator_window_error(closed)
