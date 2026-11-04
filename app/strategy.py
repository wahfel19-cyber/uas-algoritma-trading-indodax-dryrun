from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional

from app.config import (
    DAILY_LOSS_LIMIT,
    BUY_TAKER_FEE_FLOOR,
    MAX_OPEN_POSITIONS,
    MAX_POSITION_WEIGHT,
    MIN_ORDER_IDR,
    SELL_TAKER_FEE_FLOOR,
    TIMEFRAME,
    UNIVERSE,
)

LOOKBACK_24H = 24
LOOKBACK_7D = 24 * 7
SMA_FAST = 20
SMA_SLOW = 50
MIN_HISTORY = LOOKBACK_7D + 1
MIN_MOMENTUM_24H = 0.015
MIN_MOMENTUM_7D = 0.04


def _closes(candles: List[Dict[str, float]]) -> List[float]:
    return [float(candle["close"]) for candle in candles]


def _momentum(values: List[float], lookback: int) -> float:
    if len(values) <= lookback or values[-lookback - 1] <= 0:
        return 0.0
    return values[-1] / values[-lookback - 1] - 1.0


def strategy_values(candles: List[Dict[str, float]]) -> Dict[str, float]:
    values = _closes(candles[-MIN_HISTORY:])
    if len(values) < MIN_HISTORY:
        raise ValueError(f"at least {MIN_HISTORY} closed candles are required")
    return {
        "close": values[-1],
        "momentum_24h": _momentum(values, LOOKBACK_24H),
        "momentum_7d": _momentum(values, LOOKBACK_7D),
        "sma_20": sum(values[-SMA_FAST:]) / SMA_FAST,
        "sma_50": sum(values[-SMA_SLOW:]) / SMA_SLOW,
    }


def signal_for_pair(candles: List[Dict[str, float]]) -> Optional[str]:
    if len(candles) < MIN_HISTORY:
        return None
    values = strategy_values(candles)
    if values["close"] <= 0 or values["sma_20"] <= 0 or values["sma_50"] <= 0:
        return None
    if (
        values["momentum_24h"] > MIN_MOMENTUM_24H
        and values["momentum_7d"] > MIN_MOMENTUM_7D
        and values["close"] > values["sma_20"]
        and values["sma_20"] > values["sma_50"]
    ):
        return "BUY"
    if values["close"] < values["sma_20"] or values["momentum_24h"] < 0:
        return "SELL"
    return "HOLD"


def entry_score(candles: List[Dict[str, float]]) -> float:
    values = strategy_values(candles)
    return values["momentum_24h"] + values["momentum_7d"]


def strategy_fingerprint() -> str:
    manifest = {
        "timeframe": TIMEFRAME,
        "universe": UNIVERSE,
        "lookback_24h": LOOKBACK_24H,
        "lookback_7d": LOOKBACK_7D,
        "sma_fast": SMA_FAST,
        "sma_slow": SMA_SLOW,
        "minimum_momentum_24h": MIN_MOMENTUM_24H,
        "minimum_momentum_7d": MIN_MOMENTUM_7D,
        "max_open_positions": MAX_OPEN_POSITIONS,
        "max_position_weight": MAX_POSITION_WEIGHT,
        "daily_loss_limit": DAILY_LOSS_LIMIT,
        "minimum_order_idr": MIN_ORDER_IDR,
        "buy_taker_fee_floor": BUY_TAKER_FEE_FLOOR,
        "sell_taker_fee_floor": SELL_TAKER_FEE_FLOOR,
    }
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
