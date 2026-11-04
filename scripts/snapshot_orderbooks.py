from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import CANDIDATE_UNIVERSE
from app.data_client import fetch_order_book, fetch_pairs, fetch_server_time
from app.execution import best_prices, fee_rate_for_pair, fill_market_order, spread_fraction

OUT_FILE = ROOT / "logs" / "raw" / "orderbook_snapshots.jsonl"
REFERENCE_NOTIONAL_IDR = 15_000_000.0


def _sample(symbol: str, pair: Dict[str, Any], book: Dict[str, Any], raw: Any, timestamp: str) -> Dict[str, Any]:
    bid, ask = best_prices(book)
    increment = float(pair.get("quantity_increment", 0.0))
    buy_fee_rate = fee_rate_for_pair(pair, "BUY")
    sell_fee_rate = fee_rate_for_pair(pair, "SELL")
    buy = fill_market_order(book, "BUY", REFERENCE_NOTIONAL_IDR / ask, increment, 0.0)
    sell = fill_market_order(book, "SELL", REFERENCE_NOTIONAL_IDR / bid, increment, 0.0)
    return {
        "timestamp": timestamp,
        "symbol": symbol,
        "best_bid": bid,
        "best_ask": ask,
        "spread_fraction": spread_fraction(book),
        "reference_notional_idr": REFERENCE_NOTIONAL_IDR,
        "buy_impact_fraction": (
            buy["slippage_cost_estimate"] / buy["notional"] if buy["notional"] else None
        ),
        "sell_impact_fraction": (
            sell["slippage_cost_estimate"] / sell["notional"] if sell["notional"] else None
        ),
        "buy_fill_fraction": buy["filled_quantity"] / buy["requested_quantity"] if buy["requested_quantity"] else 0.0,
        "sell_fill_fraction": sell["filled_quantity"] / sell["requested_quantity"] if sell["requested_quantity"] else 0.0,
        "buy_fee_rate": buy_fee_rate,
        "sell_fee_rate": sell_fee_rate,
        "raw_order_book": raw,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append real Indodax order-book snapshots and measured spread/market-impact observations."
    )
    parser.add_argument("--symbols", default=",".join(CANDIDATE_UNIVERSE))
    args = parser.parse_args()
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]
    pairs = fetch_pairs()
    exchange_time = datetime.fromtimestamp(fetch_server_time(), timezone.utc).isoformat()
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with OUT_FILE.open("a", encoding="utf-8") as file:
        for symbol in symbols:
            if symbol not in pairs:
                raise ValueError(f"Indodax pair is unavailable: {symbol}")
            book, raw = fetch_order_book(symbol)
            sample = _sample(symbol, pairs[symbol], book, raw, exchange_time)
            file.write(json.dumps(sample, separators=(",", ":"), allow_nan=False) + "\n")
            count += 1
    print(json.dumps({"timestamp": exchange_time, "snapshots_written": count, "file": str(OUT_FILE)}))


if __name__ == "__main__":
    main()
