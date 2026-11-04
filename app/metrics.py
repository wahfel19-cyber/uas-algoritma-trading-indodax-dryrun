from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


def total_return(values: List[float]) -> float | None:
    if len(values) < 2 or values[0] <= 0:
        return None
    return values[-1] / values[0] - 1.0


def max_drawdown(values: List[float]) -> float | None:
    if not values:
        return None
    peak = values[0]
    maximum = 0.0
    for value in values:
        if value > peak:
            peak = value
        if peak > 0:
            maximum = max(maximum, (peak - value) / peak)
    return maximum


def cagr(values: List[float], start: str, end: str) -> float | None:
    result = total_return(values)
    start_time = datetime.fromisoformat(start.replace("Z", "+00:00"))
    end_time = datetime.fromisoformat(end.replace("Z", "+00:00"))
    years = (end_time - start_time).total_seconds() / (365.25 * 24 * 3600)
    if result is None or years <= 0 or values[-1] <= 0:
        return None
    return (values[-1] / values[0]) ** (1.0 / years) - 1.0


def series_metrics(
    values: List[float],
    start: str | None = None,
    end: str | None = None,
    annualized: bool = True,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "initial_equity_idr": values[0] if values else None,
        "final_equity_idr": values[-1] if values else None,
        "total_return": total_return(values),
        "max_drawdown": max_drawdown(values),
    }
    result["cagr"] = cagr(values, start, end) if annualized and start and end else None
    return result


def metrics_from_trades(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    pnls = [float(trade.get("net_pnl_idr", 0.0)) for trade in trades]
    winners = [value for value in pnls if value > 0]
    losers = [value for value in pnls if value < 0]
    gross_profit = sum(
        max(0.0, float(trade.get("gross_signal_pnl_idr", 0.0))) for trade in trades
    )
    profit = sum(winners)
    loss = abs(sum(losers))
    fees = sum(float(trade.get("fees_idr", 0.0)) for trade in trades)
    spread = sum(float(trade.get("spread_cost_estimate_idr", 0.0)) for trade in trades)
    slippage = sum(float(trade.get("slippage_cost_estimate_idr", 0.0)) for trade in trades)
    return {
        "profit_factor": profit / loss if loss else (None if not profit else "infinite"),
        "win_rate": len(winners) / len(pnls) if pnls else None,
        "average_win_idr": sum(winners) / len(winners) if winners else None,
        "average_loss_idr": sum(losers) / len(losers) if losers else None,
        "trade_count": len(trades),
        "gross_profit_idr": gross_profit,
        "fees_idr": fees,
        "spread_cost_estimate_idr": spread,
        "slippage_cost_estimate_idr": slippage,
        "cost_share_of_gross_profit": (
            (fees + spread + slippage) / gross_profit if gross_profit > 0 else None
        ),
    }
