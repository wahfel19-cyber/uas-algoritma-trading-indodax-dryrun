from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.config import (
    FORWARD_END_UTC,
    FORWARD_START_UTC,
    MAX_OPEN_POSITIONS,
    MIN_ORDER_IDR,
    TIMEFRAME_SECONDS,
    UNIVERSE,
)
from app.data_client import (
    IndodaxError,
    fetch_candles,
    fetch_order_book,
    fetch_pairs,
    fetch_server_time,
    validate_candles,
)
from app.execution import (
    best_prices,
    daily_loss_reached,
    fee_rate_for_pair,
    fill_market_order,
    floor_quantity,
    portfolio_equity,
    position_notional_limit,
    should_open_position,
    spread_fraction,
)
from app.storage import (
    acquire_lock,
    append_event,
    load_state,
    release_lock,
    save_state,
)
from app.strategy import entry_score, signal_for_pair, strategy_fingerprint, strategy_values

WIB = timezone(timedelta(hours=7))
SNAPSHOT_IMPACT_IDR = 15_000_000.0


def _iso_utc(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _new_event(timestamp: str, symbol: str, event_type: str, **fields: Any) -> Dict[str, Any]:
    return {"timestamp": timestamp, "symbol": symbol, "type": event_type, **fields}


def _record_order(
    symbol: str,
    side: str,
    fill: Dict[str, float],
    signal_candle: Dict[str, float],
    strategy_signal: str,
) -> Dict[str, Any]:
    average = fill["average_price"]
    signal_price = float(signal_candle["close"])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "side": side,
        "quantity": fill["filled_quantity"],
        "best_bid": fill["best_bid"],
        "best_ask": fill["best_ask"],
        "average_fill_price": average,
        "notional_idr": fill["notional"],
        "fee_idr": fill["fee"],
        "fee_rate": fill["fee_rate"],
        "spread_cost_estimate_idr": fill["spread_cost_estimate"],
        "slippage_cost_estimate_idr": fill["slippage_cost_estimate"],
        "signal_candle_time": _iso_utc(int(signal_candle["time"])),
        "signal_close": signal_price,
        "fill_vs_signal_idr": average - signal_price if side == "BUY" else signal_price - average,
        "unfilled_quantity": fill["unfilled_quantity"],
        "strategy_signal": strategy_signal,
    }


def tick_once() -> Dict[str, Any]:
    lock_token = acquire_lock()
    call_started = datetime.now(timezone.utc)
    call_event: Dict[str, Any] = {
        "type": "tick",
        "started_at": call_started.isoformat(),
        "status": "started",
        "processed_candles": [],
        "errors": 0,
    }
    state: Dict[str, Any] | None = None
    try:
        state = load_state()
        fingerprint = strategy_fingerprint()
        stored_fingerprint = state.get("strategy_fingerprint")
        if stored_fingerprint and stored_fingerprint != fingerprint:
            raise RuntimeError(
                "strategy configuration differs from the configuration saved in Redis; "
                "stop the bot and do not reset state during the forward test"
            )
        state["strategy_fingerprint"] = fingerprint
        env_kill = os.getenv("KILL_SWITCH", "").strip().lower() in {"1", "true", "yes", "on"}
        kill_switch = bool(state.get("kill_switch")) or env_kill
        server_time = fetch_server_time()
        call_event["exchange_server_time"] = _iso_utc(server_time)
        now = datetime.fromtimestamp(server_time, timezone.utc)
        forward_start = datetime.fromisoformat(FORWARD_START_UTC)
        forward_end = datetime.fromisoformat(FORWARD_END_UTC)
        pre_forward = now < forward_start
        if now >= forward_end:
            call_event.update(status="forward_complete", detail="forward test window has ended")
            return call_event

        pairs = fetch_pairs()
        books: Dict[str, Dict[str, Any]] = {}
        fee_rates: Dict[str, Dict[str, float]] = {}
        pair_metadata: Dict[str, Dict[str, Any]] = {}
        closed_by_symbol: Dict[str, List[Dict[str, float]]] = {}
        signals: Dict[str, str] = {}
        valid_candles: Dict[str, Dict[str, float]] = {}
        snapshot_at = datetime.now(timezone.utc).isoformat()
        candle_from = server_time - 210 * TIMEFRAME_SECONDS

        for symbol in UNIVERSE:
            try:
                pair = pairs[symbol]
                pair_metadata[symbol] = pair
                fee_rates[symbol] = {
                    "BUY": fee_rate_for_pair(pair, "BUY"),
                    "SELL": fee_rate_for_pair(pair, "SELL"),
                }
                book, raw_book = fetch_order_book(symbol)
                bid, ask = best_prices(book)
                spread = spread_fraction(book)
                books[symbol] = book
                snapshot = {
                    "timestamp": snapshot_at,
                    "symbol": symbol,
                    "best_bid": bid,
                    "best_ask": ask,
                    "spread_fraction": spread,
                    "raw_order_book": raw_book,
                    "buy_fee_rate": fee_rates[symbol]["BUY"],
                    "sell_fee_rate": fee_rates[symbol]["SELL"],
                }
                increment = float(pairs[symbol].get("quantity_increment", 0.0))
                buy_sample = fill_market_order(
                    book,
                    "BUY",
                    SNAPSHOT_IMPACT_IDR / ask,
                    increment,
                    0.0,
                )
                sell_sample = fill_market_order(
                    book,
                    "SELL",
                    SNAPSHOT_IMPACT_IDR / bid,
                    increment,
                    0.0,
                )
                snapshot["reference_notional_idr"] = SNAPSHOT_IMPACT_IDR
                snapshot["buy_impact_fraction"] = (
                    buy_sample["slippage_cost_estimate"] / buy_sample["notional"]
                    if buy_sample["notional"]
                    else None
                )
                snapshot["buy_fill_fraction"] = (
                    buy_sample["filled_quantity"] / buy_sample["requested_quantity"]
                    if buy_sample["requested_quantity"]
                    else 0.0
                )
                snapshot["sell_impact_fraction"] = (
                    sell_sample["slippage_cost_estimate"] / sell_sample["notional"]
                    if sell_sample["notional"]
                    else None
                )
                snapshot["sell_fill_fraction"] = (
                    sell_sample["filled_quantity"] / sell_sample["requested_quantity"]
                    if sell_sample["requested_quantity"]
                    else 0.0
                )
                append_event("snapshots", snapshot)
                if spread > 0.02:
                    raise ValueError(f"spread_over_2_percent:{spread:.8f}")

                candles = fetch_candles(symbol, candle_from, server_time)
                error = validate_candles(candles, server_time)
                if error:
                    raise ValueError(error)
                closed = [
                    candle
                    for candle in candles
                    if int(candle["time"]) + TIMEFRAME_SECONDS <= server_time
                ]
                closed_by_symbol[symbol] = closed
                last = closed[-1]
                valid_candles[symbol] = last
                candle_time = int(last["time"])
                previous = state.setdefault("processed_candles", {}).get(symbol)
                if previous == candle_time:
                    continue
                state["processed_candles"][symbol] = candle_time
                call_event["processed_candles"].append(
                    {"symbol": symbol, "candle_time": _iso_utc(candle_time)}
                )
                append_event(
                    "candles",
                    {
                        "timestamp": snapshot_at,
                        "symbol": symbol,
                        "candle_time": _iso_utc(candle_time),
                        "open": last["open"],
                        "high": last["high"],
                        "low": last["low"],
                        "close": last["close"],
                        "volume": last["volume"],
                    },
                )
                signal = signal_for_pair(closed)
                if signal is None:
                    continue
                signals[symbol] = signal
                values = strategy_values(closed)
                append_event(
                    "signals",
                    _new_event(
                        snapshot_at,
                        symbol,
                        "signal",
                        candle_time=_iso_utc(candle_time),
                        signal=signal,
                        **values,
                    ),
                )
            except (KeyError, IndodaxError, ValueError) as error:
                call_event["errors"] += 1
                append_event(
                    "errors",
                    _new_event(snapshot_at, symbol, "market_data_error", reason=str(error)),
                )

        if not valid_candles:
            call_event["status"] = "no_valid_market_data"
            save_state(state)
            return call_event

        wib_day = now.astimezone(WIB).date().isoformat()
        daily_baselines = state.setdefault("daily_baselines", {})
        if wib_day not in daily_baselines:
            daily_baselines[wib_day] = portfolio_equity(state, books, fee_rates)
            state.setdefault("daily_halt", {}).pop(wib_day, None)

        equity_before = portfolio_equity(state, books, fee_rates)
        if daily_loss_reached(equity_before, float(daily_baselines[wib_day])):
            state.setdefault("daily_halt", {})[wib_day] = True
            append_event(
                "errors",
                {
                    "timestamp": snapshot_at,
                    "type": "daily_loss_limit",
                    "wib_day": wib_day,
                    "baseline_equity": daily_baselines[wib_day],
                    "current_equity": equity_before,
                    "limit_fraction": 0.02,
                },
            )
        daily_halt = bool(state.setdefault("daily_halt", {}).get(wib_day, False))

        orders_disabled = kill_switch or pre_forward
        if not orders_disabled:
            for symbol, position in list(state.get("positions", {}).items()):
                if signals.get(symbol) != "SELL" or symbol not in valid_candles:
                    continue
                pair = pair_metadata[symbol]
                increment = float(pair.get("quantity_increment", 0.0))
                fill = fill_market_order(
                    books[symbol],
                    "SELL",
                    float(position["quantity"]),
                    increment,
                    fee_rates[symbol]["SELL"],
                )
                if fill["filled_quantity"] * fill["average_price"] < MIN_ORDER_IDR:
                    append_event(
                        "errors",
                        _new_event(snapshot_at, symbol, "sell_below_minimum", notional=fill["notional"]),
                    )
                    continue
                order = _record_order(symbol, "SELL", fill, valid_candles[symbol], "SELL")
                append_event("orders", order)
                sold_quantity = fill["filled_quantity"]
                sold_fraction = sold_quantity / float(position["quantity"])
                entry_fee_share = float(position["entry_fee"]) * sold_fraction
                entry_spread_share = float(position["entry_spread_cost"]) * sold_fraction
                entry_slippage_share = float(position["entry_slippage_cost"]) * sold_fraction
                gross_signal_pnl = sold_quantity * (
                    float(valid_candles[symbol]["close"]) - float(position["signal_entry_price"])
                )
                actual_price_pnl = sold_quantity * (
                    fill["average_price"] - float(position["entry_fill_price"])
                )
                net_pnl = actual_price_pnl - entry_fee_share - fill["fee"]
                trade = {
                    "timestamp": snapshot_at,
                    "symbol": symbol,
                    "entry_time": position["entry_time"],
                    "exit_time": snapshot_at,
                    "quantity": sold_quantity,
                    "signal_entry_price": position["signal_entry_price"],
                    "signal_exit_price": valid_candles[symbol]["close"],
                    "entry_fill_price": position["entry_fill_price"],
                    "exit_fill_price": fill["average_price"],
                    "gross_signal_pnl_idr": gross_signal_pnl,
                    "net_pnl_idr": net_pnl,
                    "fees_idr": entry_fee_share + fill["fee"],
                    "spread_cost_estimate_idr": (
                        entry_spread_share + fill["spread_cost_estimate"]
                    ),
                    "slippage_cost_estimate_idr": (
                        entry_slippage_share + fill["slippage_cost_estimate"]
                    ),
                }
                append_event("trades", trade)
                state["cash_idr"] += fill["notional"] - fill["fee"]
                remaining = float(position["quantity"]) - sold_quantity
                if remaining < increment:
                    del state["positions"][symbol]
                else:
                    position["quantity"] = remaining
                    position["entry_fee"] -= entry_fee_share
                    position["entry_spread_cost"] -= entry_spread_share
                    position["entry_slippage_cost"] -= entry_slippage_share

        equity = portfolio_equity(state, books, fee_rates)
        if daily_loss_reached(equity, float(daily_baselines[wib_day])):
            state.setdefault("daily_halt", {})[wib_day] = True
            daily_halt = True

        eligible = [
            symbol
            for symbol, signal in signals.items()
            if signal == "BUY" and symbol in valid_candles and symbol in books
        ]
        eligible.sort(key=lambda symbol: (-entry_score(closed_by_symbol[symbol]), symbol))
        for symbol in eligible:
            if not should_open_position(
                symbol,
                state["positions"],
                MAX_OPEN_POSITIONS,
                daily_halt,
                orders_disabled,
            ):
                continue
            pair = pair_metadata[symbol]
            increment = float(pair.get("quantity_increment", 0.0))
            ask = best_prices(books[symbol])[1]
            buy_fee_rate = fee_rates[symbol]["BUY"]
            allocation = min(
                position_notional_limit(equity),
                state["cash_idr"] / (1 + buy_fee_rate),
            )
            quantity = floor_quantity(allocation / ask, increment)
            fill = fill_market_order(books[symbol], "BUY", quantity, increment, buy_fee_rate)
            for _ in range(3):
                actual_cost = fill["notional"] + fill["fee"]
                if fill["filled_quantity"] <= 0 or actual_cost <= allocation:
                    break
                corrected_quantity = floor_quantity(
                    fill["filled_quantity"] * allocation / actual_cost,
                    increment,
                )
                if corrected_quantity >= fill["filled_quantity"]:
                    corrected_quantity = floor_quantity(
                        fill["filled_quantity"] - increment, increment
                    )
                quantity = corrected_quantity
                fill = fill_market_order(
                    books[symbol], "BUY", quantity, increment, buy_fee_rate
                )
            if fill["notional"] + fill["fee"] > allocation:
                append_event(
                    "errors",
                    _new_event(
                        snapshot_at,
                        symbol,
                        "buy_exceeds_position_allocation",
                        allocation_idr=allocation,
                        actual_cost_idr=fill["notional"] + fill["fee"],
                    ),
                )
                continue
            if fill["filled_quantity"] <= 0 or fill["notional"] < MIN_ORDER_IDR:
                append_event(
                    "errors",
                    _new_event(
                        snapshot_at,
                        symbol,
                        "buy_below_minimum_or_no_liquidity",
                        requested_quantity=quantity,
                        filled_quantity=fill["filled_quantity"],
                        notional=fill["notional"],
                    ),
                )
                continue
            if fill["notional"] + fill["fee"] > state["cash_idr"]:
                append_event(
                    "errors",
                    _new_event(snapshot_at, symbol, "buy_exceeds_available_cash"),
                )
                continue
            order = _record_order(symbol, "BUY", fill, valid_candles[symbol], "BUY")
            append_event("orders", order)
            state["cash_idr"] -= fill["notional"] + fill["fee"]
            state["positions"][symbol] = {
                "quantity": fill["filled_quantity"],
                "entry_time": snapshot_at,
                "entry_fill_price": fill["average_price"],
                "signal_entry_price": float(valid_candles[symbol]["close"]),
                "entry_fee": fill["fee"],
                "entry_spread_cost": fill["spread_cost_estimate"],
                "entry_slippage_cost": fill["slippage_cost_estimate"],
                "signal_candle_time": int(valid_candles[symbol]["time"]),
            }
            equity = portfolio_equity(state, books, fee_rates)

        if wib_day not in {row["wib_day"] for row in state.get("daily_equity", [])}:
            state.setdefault("daily_equity", []).append(
                {
                    "timestamp": snapshot_at,
                    "wib_day": wib_day,
                    "equity_idr": portfolio_equity(state, books, fee_rates),
                    "cash_idr": state["cash_idr"],
                }
            )
            append_event("equity", state["daily_equity"][-1])

        if kill_switch or pre_forward:
            append_event(
                "controls",
                {
                    "timestamp": snapshot_at,
                    "type": "kill_switch_active" if kill_switch else "pre_forward_dry_run",
                    "orders_disabled": True,
                },
            )
        state["last_call_at"] = snapshot_at
        save_state(state)
        call_event["status"] = "pre_forward_snapshot" if pre_forward else "processed"
        call_event["kill_switch"] = kill_switch
        call_event["orders_disabled"] = orders_disabled
        call_event["daily_loss_halt"] = daily_halt
        call_event["equity_idr"] = portfolio_equity(state, books, fee_rates)
        return call_event
    except Exception as error:
        call_event.update(
            status="error",
            error_type=type(error).__name__,
            error=str(error),
        )
        append_event(
            "errors",
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "tick_error",
                "error_type": type(error).__name__,
                "message": str(error),
            },
        )
        raise
    finally:
        call_event["finished_at"] = datetime.now(timezone.utc).isoformat()
        append_event("calls", call_event)
        release_lock(lock_token)
