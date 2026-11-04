from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.config import (
    CAPITAL_IDR,
    DAILY_LOSS_LIMIT,
    MAX_OPEN_POSITIONS,
    MAX_POSITION_WEIGHT,
    MIN_ORDER_IDR,
    TIMEFRAME_SECONDS,
)
from app.data_client import indicator_window_error
from app.execution import floor_quantity
from app.metrics import metrics_from_trades, series_metrics
from app.strategy import entry_score, signal_for_pair, strategy_values

WIB = timezone(timedelta(hours=7))


def simulate(
    candles_by_symbol: Dict[str, List[Dict[str, float]]],
    calibration: Dict[str, Dict[str, float]],
    pair_metadata: Dict[str, Dict[str, Any]],
    start: datetime,
    end: datetime,
) -> Dict[str, Any]:
    candles_by_time: Dict[int, Dict[str, Dict[str, float]]] = {}
    histories: Dict[str, List[Dict[str, float]]] = {}
    start_timestamp = int(start.timestamp())
    end_timestamp = int(end.timestamp())
    for symbol, candles in candles_by_symbol.items():
        histories[symbol] = []
        for candle in candles:
            timestamp = int(candle["time"])
            if timestamp < start_timestamp:
                histories[symbol].append(candle)
            elif timestamp <= end_timestamp:
                candles_by_time.setdefault(timestamp, {})[symbol] = candle
    signal_times = [timestamp for timestamp in candles_by_time if timestamp < end_timestamp]
    if not signal_times:
        raise ValueError("No candles fall within the requested backtest period")

    cash = CAPITAL_IDR
    positions: Dict[str, Dict[str, Any]] = {}
    trades: List[Dict[str, Any]] = []
    signals: List[Dict[str, Any]] = []
    pending: Dict[str, Dict[str, Any]] = {}
    equity_curve: List[Dict[str, Any]] = [
        {
            "timestamp": start.astimezone(timezone.utc).isoformat(),
            "equity_idr": CAPITAL_IDR,
            "cash_idr": CAPITAL_IDR,
            "open_positions": 0,
            "daily_loss_halt": False,
        }
    ]
    daily_baselines: Dict[str, float] = {}
    daily_halt: Dict[str, bool] = {}

    def estimated_fill(symbol: str, candle_price: float, side: str) -> float:
        assumptions = calibration[symbol]
        friction = assumptions["spread_fraction"] / 2.0 + assumptions["slippage_fraction"]
        return candle_price * (1.0 + friction if side == "BUY" else 1.0 - friction)

    def marked_equity(
        current: Dict[str, Dict[str, float]], price_field: str
    ) -> float:
        marked = cash
        for symbol, position in positions.items():
            candle = current.get(symbol)
            if candle is None:
                candle = histories[symbol][-1] if histories[symbol] else None
            if candle is not None:
                bid = estimated_fill(symbol, float(candle[price_field]), "SELL")
                marked += position["quantity"] * bid * (1.0 - calibration[symbol]["fee_sell"])
        return marked

    for timestamp in sorted(candles_by_time):
        current = candles_by_time[timestamp]
        dt = datetime.fromtimestamp(timestamp, timezone.utc)
        wib_day = dt.astimezone(WIB).date().isoformat()
        equity_before_orders = marked_equity(current, "open")
        if wib_day not in daily_baselines:
            daily_baselines[wib_day] = equity_before_orders
            daily_halt[wib_day] = False
        if equity_before_orders <= daily_baselines[wib_day] * (1.0 - DAILY_LOSS_LIMIT):
            daily_halt[wib_day] = True

        due_signals: Dict[str, Dict[str, Any]] = {}
        for symbol, signal in list(pending.items()):
            if signal["execute_at"] < timestamp:
                signals.append(
                    {
                        "timestamp": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                        "symbol": symbol,
                        "signal": signal["signal"],
                        "execution_skipped": "missing_next_candle",
                        "signal_candle_time": signal["signal_candle_time"],
                    }
                )
                del pending[symbol]
            elif signal["execute_at"] == timestamp:
                due_signals[symbol] = signal
                del pending[symbol]

        for symbol in list(positions):
            signal = due_signals.get(symbol)
            candle = current.get(symbol)
            if not signal or signal["signal"] != "SELL" or candle is None:
                continue
            position = positions[symbol]
            price = estimated_fill(symbol, float(candle["open"]), "SELL")
            quantity = position["quantity"]
            fee_rate = calibration[symbol]["fee_sell"]
            exit_notional = quantity * price
            exit_fee = exit_notional * fee_rate
            actual_gross = quantity * (price - position["entry_fill_price"])
            net_pnl = actual_gross - position["entry_fee"] - exit_fee
            signal_exit_price = float(signal["signal_close"])
            signal_gross = quantity * (signal_exit_price - position["signal_entry_price"])
            trades.append(
                {
                    "timestamp": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                    "symbol": symbol,
                    "entry_time": position["entry_time"],
                    "exit_time": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                    "quantity": quantity,
                    "entry_signal_price": position["signal_entry_price"],
                    "exit_signal_price": signal_exit_price,
                    "entry_fill_price": position["entry_fill_price"],
                    "exit_fill_price": price,
                    "gross_signal_pnl_idr": signal_gross,
                    "net_pnl_idr": net_pnl,
                    "fees_idr": position["entry_fee"] + exit_fee,
                    "spread_cost_estimate_idr": position["entry_spread_cost"]
                    + quantity * float(candle["open"]) * calibration[symbol]["spread_fraction"] / 2.0,
                    "slippage_cost_estimate_idr": position["entry_slippage_cost"]
                    + quantity * float(candle["open"]) * calibration[symbol]["slippage_fraction"],
                }
            )
            cash += exit_notional - exit_fee
            del positions[symbol]

        equity = marked_equity(current, "open")
        if equity <= daily_baselines[wib_day] * (1.0 - DAILY_LOSS_LIMIT):
            daily_halt[wib_day] = True

        candidates = [symbol for symbol, item in due_signals.items() if item["signal"] == "BUY"]
        candidates.sort(
            key=lambda symbol: (
                -due_signals[symbol]["momentum_24h"]
                - due_signals[symbol]["momentum_7d"],
                symbol,
            )
        )
        if not daily_halt[wib_day]:
            for symbol in candidates:
                if len(positions) >= MAX_OPEN_POSITIONS:
                    break
                candle = current.get(symbol)
                if candle is None or symbol in positions:
                    continue
                signal = due_signals[symbol]
                fee_rate = calibration[symbol]["fee_buy"]
                ask = estimated_fill(symbol, float(candle["open"]), "BUY")
                allocation = min(equity * MAX_POSITION_WEIGHT, cash / (1.0 + fee_rate))
                increment = float(pair_metadata[symbol]["quantity_increment"])
                quantity = floor_quantity(allocation / ask, increment)
                notional = quantity * ask
                for _ in range(3):
                    actual_cost = notional * (1.0 + fee_rate)
                    if quantity <= 0 or actual_cost <= min(allocation, cash):
                        break
                    corrected_quantity = floor_quantity(
                        quantity * min(allocation, cash) / actual_cost,
                        increment,
                    )
                    if corrected_quantity >= quantity:
                        corrected_quantity = floor_quantity(quantity - increment, increment)
                    quantity = corrected_quantity
                    notional = quantity * ask
                if (
                    notional < MIN_ORDER_IDR
                    or notional + notional * fee_rate > cash
                    or notional + notional * fee_rate > allocation
                ):
                    continue
                fee = notional * fee_rate
                spread_cost = quantity * float(candle["open"]) * calibration[symbol]["spread_fraction"] / 2.0
                slippage_cost = quantity * float(candle["open"]) * calibration[symbol]["slippage_fraction"]
                positions[symbol] = {
                    "quantity": quantity,
                    "entry_time": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                    "entry_fill_price": ask,
                    "signal_entry_price": float(signal["signal_close"]),
                    "entry_fee": fee,
                    "entry_spread_cost": spread_cost,
                    "entry_slippage_cost": slippage_cost,
                }
                cash -= notional + fee
                equity = marked_equity(current, "open")

        if timestamp < end_timestamp:
            for symbol, candle in current.items():
                histories[symbol].append(candle)
                history = histories[symbol]
                invalid_reason = indicator_window_error(history)
                candle_close_time = timestamp + TIMEFRAME_SECONDS
                if invalid_reason:
                    signals.append(
                        {
                            "timestamp": datetime.fromtimestamp(candle_close_time, timezone.utc).isoformat(),
                            "symbol": symbol,
                            "signal": None,
                            "reason": invalid_reason,
                            "signal_candle_time": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                        }
                    )
                    continue
                signal = signal_for_pair(history)
                if signal is None:
                    continue
                values = strategy_values(history)
                signal_time = datetime.fromtimestamp(candle_close_time, timezone.utc).isoformat()
                signal_candle_time = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
                signals.append(
                    {
                        "timestamp": signal_time,
                        "symbol": symbol,
                        "signal": signal,
                        "signal_candle_time": signal_candle_time,
                        **values,
                    }
                )
                pending[symbol] = {
                    "signal": signal,
                    "execute_at": candle_close_time,
                    "signal_close": float(candle["close"]),
                    "signal_candle_time": signal_candle_time,
                    **values,
                }

        final_price_field = "open" if timestamp == end_timestamp else "close"
        equity_value = marked_equity(current, final_price_field)
        equity_curve.append(
            {
                "timestamp": datetime.fromtimestamp(
                    end_timestamp if timestamp == end_timestamp else timestamp + TIMEFRAME_SECONDS,
                    timezone.utc,
                ).isoformat(),
                "equity_idr": equity_value,
                "cash_idr": cash,
                "open_positions": len(positions),
                "daily_loss_halt": daily_halt[wib_day],
            }
        )

    for symbol, signal in pending.items():
        signals.append(
            {
                "timestamp": end.astimezone(timezone.utc).isoformat(),
                "symbol": symbol,
                "signal": signal["signal"],
                "execution_skipped": "missing_next_candle_at_window_end",
                "signal_candle_time": signal["signal_candle_time"],
            }
        )

    values = [float(row["equity_idr"]) for row in equity_curve]
    metrics = series_metrics(
        values,
        start=datetime.fromtimestamp(int(start.timestamp()), timezone.utc).isoformat(),
        end=datetime.fromtimestamp(int(end.timestamp()), timezone.utc).isoformat(),
        annualized=True,
    )
    metrics.update(metrics_from_trades(trades))
    metrics["initial_capital_idr"] = CAPITAL_IDR
    metrics["final_equity_idr"] = values[-1]
    return {
        "metrics": metrics,
        "equity_curve": equity_curve,
        "trades": trades,
        "signals": signals,
    }


def buy_and_hold_btc(
    candles: List[Dict[str, float]],
    calibration: Dict[str, float],
    start: datetime,
    end: datetime,
) -> Dict[str, Any]:
    selected = [
        candle
        for candle in candles
        if int(start.timestamp()) <= int(candle["time"]) <= int(end.timestamp())
    ]
    if len(selected) < 2:
        return {"return": None, "start_price": None, "end_price": None}
    buy_price = float(selected[0]["open"]) * (
        1.0 + calibration["spread_fraction"] / 2.0 + calibration["slippage_fraction"]
    )
    exit_candle = selected[-1]
    exit_price = (
        float(exit_candle["open"])
        if int(exit_candle["time"]) == int(end.timestamp())
        else float(exit_candle["close"])
    )
    sell_price = exit_price * (
        1.0 - calibration["spread_fraction"] / 2.0 - calibration["slippage_fraction"]
    )
    buy_fee = calibration["fee_buy"]
    sell_fee = calibration["fee_sell"]
    return {
        "return": sell_price * (1 - sell_fee) / (buy_price * (1 + buy_fee)) - 1.0,
        "start_price": buy_price,
        "end_price": sell_price,
    }
