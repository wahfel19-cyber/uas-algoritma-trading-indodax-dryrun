from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, List, Tuple

from app.config import (
    CAPITAL_IDR,
    DAILY_LOSS_LIMIT,
    MAX_OPEN_POSITIONS,
    MAX_POSITION_WEIGHT,
    MIN_ORDER_IDR,
    BUY_TAKER_FEE_FLOOR,
    SELL_TAKER_FEE_FLOOR,
)


def fee_rate_for_pair(pair: Dict[str, Any], side: str) -> float:
    reported_percent = float(pair.get("trade_fee_percent_taker", 0.0))
    if side.upper() == "BUY":
        return max(BUY_TAKER_FEE_FLOOR, reported_percent / 100.0)
    if side.upper() == "SELL":
        return max(SELL_TAKER_FEE_FLOOR, reported_percent / 100.0)
    raise ValueError("side must be BUY or SELL")


def best_prices(book: Dict[str, List[Tuple[float, float]]]) -> Tuple[float, float]:
    bids, asks = book.get("bids", []), book.get("asks", [])
    if not bids or not asks:
        raise ValueError("empty_order_book")
    bid, ask = bids[0][0], asks[0][0]
    if bid <= 0 or ask <= 0 or ask < bid:
        raise ValueError("invalid_best_bid_ask")
    return bid, ask


def spread_fraction(book: Dict[str, List[Tuple[float, float]]]) -> float:
    bid, ask = best_prices(book)
    return (ask - bid) / ((ask + bid) / 2.0)


def floor_quantity(quantity: float, increment: float) -> float:
    if quantity <= 0 or increment <= 0:
        return 0.0
    units = (Decimal(str(quantity)) / Decimal(str(increment))).to_integral_value(rounding=ROUND_DOWN)
    return float(units * Decimal(str(increment)))


def fill_market_order(
    book: Dict[str, List[Tuple[float, float]]],
    side: str,
    requested_quantity: float,
    quantity_increment: float,
    fee_rate: float,
) -> Dict[str, float]:
    side = side.upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    levels = book["asks"] if side == "BUY" else book["bids"]
    if not levels:
        raise ValueError("empty_order_book")
    remaining = floor_quantity(requested_quantity, quantity_increment)
    requested = remaining
    notional = 0.0
    filled_quantity = 0.0
    best_price = levels[0][0]
    for price, available in levels:
        take = min(remaining, available)
        take = floor_quantity(take, quantity_increment)
        if take <= 0:
            continue
        notional += take * price
        filled_quantity += take
        remaining = max(0.0, remaining - take)
        if remaining < quantity_increment:
            break
    average_price = notional / filled_quantity if filled_quantity else 0.0
    fee = notional * fee_rate
    impact_cost = (
        max(0.0, average_price - best_price) * filled_quantity
        if side == "BUY"
        else max(0.0, best_price - average_price) * filled_quantity
    )
    bid, ask = best_prices(book)
    half_spread_cost = filled_quantity * (ask - bid) / 2.0
    return {
        "requested_quantity": requested,
        "filled_quantity": filled_quantity,
        "unfilled_quantity": max(0.0, requested - filled_quantity),
        "average_price": average_price,
        "best_bid": bid,
        "best_ask": ask,
        "notional": notional,
        "fee": fee,
        "spread_cost_estimate": half_spread_cost,
        "slippage_cost_estimate": impact_cost,
        "fee_rate": fee_rate,
    }


def initial_state() -> Dict[str, Any]:
    return {
        "cash_idr": CAPITAL_IDR,
        "positions": {},
        "processed_candles": {},
        "daily_equity": [],
        "daily_baselines": {},
        "daily_halt": {},
        "kill_switch": False,
        "created_at": None,
    }


def portfolio_equity(
    state: Dict[str, Any],
    books: Dict[str, Dict[str, List[Tuple[float, float]]]],
    fee_rates: Dict[str, Any],
) -> float:
    value = float(state["cash_idr"])
    for symbol, position in state["positions"].items():
        book = books.get(symbol)
        if not book or not book.get("bids"):
            continue
        symbol_fees = fee_rates.get(symbol)
        liquidation_fee = (
            symbol_fees.get("SELL", SELL_TAKER_FEE_FLOOR)
            if isinstance(symbol_fees, dict)
            else float(symbol_fees or SELL_TAKER_FEE_FLOOR)
        )
        value += float(position["quantity"]) * book["bids"][0][0] * (1.0 - liquidation_fee)
    return value


def daily_loss_reached(equity: float, baseline: float) -> bool:
    return baseline > 0 and equity <= baseline * (1.0 - DAILY_LOSS_LIMIT)


def position_notional_limit(equity: float) -> float:
    return max(0.0, equity * MAX_POSITION_WEIGHT)


def should_open_position(
    symbol: str,
    positions: Dict[str, Any],
    max_positions: int,
    daily_halt: bool,
    kill_switch: bool,
) -> bool:
    return (
        not kill_switch
        and not daily_halt
        and symbol not in positions
        and len(positions) < max_positions
    )
