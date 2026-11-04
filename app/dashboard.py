from __future__ import annotations

import json
from statistics import median

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from app.config import (
    BUY_TAKER_FEE_FLOOR,
    CAPITAL_IDR,
    FORWARD_CANDLE_END_UTC,
    FORWARD_FIRST_CANDLE_UTC,
    SELL_TAKER_FEE_FLOOR,
)
from app.metrics import metrics_from_trades, series_metrics

ROOT = Path(__file__).resolve().parents[1]
BACKTEST_SUMMARY_PATH = ROOT / "data" / "backtest_summary.json"


def _read_backtest_summary() -> Dict[str, Any]:
    if not BACKTEST_SUMMARY_PATH.exists():
        return {}
    with BACKTEST_SUMMARY_PATH.open("r", encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError("backtest_summary.json must contain a JSON object")
    return value


def _in_forward_window(timestamp: str | None) -> bool:
    if not timestamp:
        return False
    value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return (
        datetime.fromisoformat(FORWARD_FIRST_CANDLE_UTC) <= value
        < datetime.fromisoformat(FORWARD_CANDLE_END_UTC)
    )


def _benchmark_return(
    candles: List[Dict[str, Any]], snapshots: List[Dict[str, Any]]
) -> float | None:
    btc = [
        row
        for row in candles
        if row.get("symbol") == "BTCIDR"
        and _in_forward_window(row.get("candle_time"))
        and float(row.get("close", 0.0)) > 0
    ]
    btc.sort(key=lambda row: row["candle_time"])
    if len(btc) < 2:
        return None
    first, last = float(btc[0]["close"]), float(btc[-1]["close"])
    btc_snapshots = [
        row
        for row in snapshots
        if row.get("symbol") == "BTCIDR"
        and float(row.get("buy_fill_fraction", 0.0)) >= 0.999
        and float(row.get("sell_fill_fraction", 0.0)) >= 0.999
    ]
    if not btc_snapshots:
        return None
    spread = median([float(row["spread_fraction"]) for row in btc_snapshots]) if btc_snapshots else 0.0
    buy_impact = (
        median([float(row["buy_impact_fraction"]) for row in btc_snapshots if row.get("buy_impact_fraction") is not None])
        if any(row.get("buy_impact_fraction") is not None for row in btc_snapshots)
        else 0.0
    )
    sell_impact = (
        median([float(row["sell_impact_fraction"]) for row in btc_snapshots if row.get("sell_impact_fraction") is not None])
        if any(row.get("sell_impact_fraction") is not None for row in btc_snapshots)
        else 0.0
    )
    buy_fee = max(
        BUY_TAKER_FEE_FLOOR,
        median([float(row["buy_fee_rate"]) for row in btc_snapshots if row.get("buy_fee_rate") is not None])
        if any(row.get("buy_fee_rate") is not None for row in btc_snapshots)
        else BUY_TAKER_FEE_FLOOR,
    )
    sell_fee = max(
        SELL_TAKER_FEE_FLOOR,
        median([float(row["sell_fee_rate"]) for row in btc_snapshots if row.get("sell_fee_rate") is not None])
        if any(row.get("sell_fee_rate") is not None for row in btc_snapshots)
        else SELL_TAKER_FEE_FLOOR,
    )
    buy_fill = first * (1.0 + spread / 2.0 + buy_impact)
    sell_fill = last * (1.0 - spread / 2.0 - sell_impact)
    return sell_fill * (1.0 - sell_fee) / (buy_fill * (1.0 + buy_fee)) - 1.0


def dashboard_payload(logs: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    forward_calls = [
        row for row in logs.get("calls", []) if _in_forward_window(row.get("exchange_server_time"))
    ]
    forward_trades = [
        row for row in logs.get("trades", []) if _in_forward_window(row.get("timestamp"))
    ]
    forward_equity_calls = [
        row
        for row in forward_calls
        if row.get("status") == "processed" and isinstance(row.get("equity_idr"), (int, float))
    ]
    forward_equity_calls.sort(key=lambda row: row.get("exchange_server_time", ""))
    if forward_equity_calls:
        equity_values = [CAPITAL_IDR]
        equity_values.extend(float(row["equity_idr"]) for row in forward_equity_calls)
        forward_metrics = series_metrics(equity_values, annualized=False)
        forward_metrics.update(metrics_from_trades(forward_trades))
    else:
        forward_metrics = {
            "initial_equity_idr": None,
            "final_equity_idr": None,
            "total_return": None,
            "max_drawdown": None,
            "cagr": None,
            "profit_factor": None,
            "win_rate": None,
            "average_win_idr": None,
            "average_loss_idr": None,
            "trade_count": None,
            "gross_profit_idr": None,
            "fees_idr": None,
            "spread_cost_estimate_idr": None,
            "slippage_cost_estimate_idr": None,
            "cost_share_of_gross_profit": None,
        }
    forward_candles = [
        row for row in logs.get("candles", []) if _in_forward_window(row.get("candle_time"))
    ]
    scheduled = 240
    processed_slots = {
        item.get("candle_time")
        for row in forward_calls
        if row.get("status") == "processed"
        for item in row.get("processed_candles", [])
        if _in_forward_window(item.get("candle_time"))
    }
    backtest = _read_backtest_summary()
    errors = [
        row
        for row in logs.get("errors", [])
        if _in_forward_window(row.get("timestamp"))
    ]
    controls = [
        row
        for row in logs.get("controls", [])
        if _in_forward_window(row.get("timestamp"))
    ]
    snapshots = [
        row
        for row in logs.get("snapshots", [])
        if _in_forward_window(row.get("timestamp"))
    ]
    spread_samples: Dict[str, List[float]] = {}
    for row in snapshots:
        if isinstance(row.get("spread_fraction"), (float, int)):
            spread_samples.setdefault(row["symbol"], []).append(float(row["spread_fraction"]))
    spread_medians = {symbol: median(samples) for symbol, samples in spread_samples.items() if samples}
    return {
        "backtest": backtest,
        "forward": forward_metrics,
        "benchmark_btc_return": _benchmark_return(forward_candles, snapshots),
        "gap_forward_vs_backtest_return": (
            forward_metrics["total_return"] - backtest["forward_window"].get("total_return")
            if backtest.get("forward_window")
            and forward_metrics.get("total_return") is not None
            else None
        ),
        "operations": {
            "scheduled_candles": scheduled,
            "processed_candles": len(processed_slots),
            "uptime_fraction": len(processed_slots) / scheduled if forward_calls else None,
            "api_errors": len(errors) if forward_calls else None,
            "kill_switch_uses": (
                sum(
                    1
                    for row in controls
                    if row.get("type") == "kill_switch" and row.get("enabled") is True
                )
                if forward_calls
                else None
            ),
            "calls": len(forward_calls),
        },
        "spread_medians": spread_medians,
        "forward_signal_count": len(forward_candles) if forward_calls else None,
        "data_available": bool(forward_calls or backtest),
    }
