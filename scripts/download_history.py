from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import (
    CANDIDATE_UNIVERSE,
    TIMEFRAME_SECONDS,
    UNIVERSE_SELECTION_DAYS,
    UNIVERSE_SELECTION_SIZE,
)
from app.data_client import fetch_candles, fetch_pairs, fetch_server_time

DATA_DIR = ROOT / "data"
HISTORY_DIR = DATA_DIR / "historical"
PAGE_DELAY_SECONDS = 0.36


def _save_csv(symbol: str, candles: List[Dict[str, float]]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = HISTORY_DIR / f"{symbol}.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["time", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(candles)


def _get_full_history(symbol: str, start: int, end: int) -> List[Dict[str, float]]:
    cursor = end
    by_time: Dict[int, Dict[str, float]] = {}
    pages = 0
    while cursor > start:
        page = fetch_candles(symbol, start, cursor)
        pages += 1
        if not page:
            break
        for candle in page:
            timestamp = int(candle["time"])
            if start <= timestamp <= end:
                by_time[timestamp] = candle
        oldest = min(int(candle["time"]) for candle in page)
        if oldest >= cursor:
            raise RuntimeError(
                f"Pagination made no progress for {symbol}: cursor={cursor}, oldest={oldest}"
            )
        cursor = oldest - 1
        print(f"{symbol}: page {pages}, {len(by_time)} unique bars")
        time.sleep(PAGE_DELAY_SECONDS)
    result = [by_time[timestamp] for timestamp in sorted(by_time)]
    if not result:
        raise RuntimeError(f"No historical bars returned for {symbol}")
    expected_start = max(start, int(result[0]["time"]))
    expected_end = min(end, int(result[-1]["time"]))
    if expected_start > start + 2 * TIMEFRAME_SECONDS:
        raise RuntimeError(
            f"{symbol} history starts at {expected_start}, after requested start {start}"
        )
    if expected_end < end - 2 * TIMEFRAME_SECONDS:
        raise RuntimeError(
            f"{symbol} history ends at {expected_end}, before requested end {end}"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download complete 1-hour candle history by paging backwards through Indodax."
    )
    parser.add_argument("--start", help="ISO-8601 UTC; defaults to three years before Indodax server time")
    parser.add_argument("--end", help="ISO-8601 UTC; defaults to Indodax server time")
    parser.add_argument("--symbols", default=",".join(CANDIDATE_UNIVERSE))
    args = parser.parse_args()
    server_time = fetch_server_time()
    end = int(datetime.fromisoformat(args.end.replace("Z", "+00:00")).timestamp()) if args.end else server_time
    start = (
        int(datetime.fromisoformat(args.start.replace("Z", "+00:00")).timestamp())
        if args.start
        else end - (365 * 3 + UNIVERSE_SELECTION_DAYS) * 24 * 60 * 60
    )
    if end - start < (365 * 3 + UNIVERSE_SELECTION_DAYS) * 24 * 60 * 60:
        raise ValueError("Download must include 30 universe-selection days plus at least 3 test years")
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]
    if not 3 <= len(symbols) <= 10:
        raise ValueError("Choose 3 to 10 symbols")

    pairs = fetch_pairs()
    missing = [symbol for symbol in symbols if symbol not in pairs]
    if missing:
        raise ValueError(f"Indodax does not list configured pairs: {', '.join(missing)}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / "pairs.json").open("w", encoding="utf-8") as file:
        json.dump({"pairs": {symbol: pairs[symbol] for symbol in symbols}}, file, indent=2)

    manifest: Dict[str, Any] = {
        "source": "Indodax public tradingview/history_v2",
        "source_url": "https://indodax.com/tradingview/history_v2",
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "exchange_server_time_utc": datetime.fromtimestamp(server_time, timezone.utc).isoformat(),
        "timeframe_seconds": TIMEFRAME_SECONDS,
        "requested_start_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "requested_end_utc": datetime.fromtimestamp(end, timezone.utc).isoformat(),
        "selection_period_days": UNIVERSE_SELECTION_DAYS,
        "universe_selection_method": (
            f"top {UNIVERSE_SELECTION_SIZE} candidate pairs by total quote turnover "
            f"during the first {UNIVERSE_SELECTION_DAYS} days; selection period excluded from backtest"
        ),
        "symbols": {},
    }
    initial_turnovers: Dict[str, float] = {}
    for symbol in symbols:
        candles = _get_full_history(symbol, start, end)
        _save_csv(symbol, candles)
        first_month_end = start + 30 * 24 * TIMEFRAME_SECONDS
        initial_turnover = [
            float(row["close"]) * float(row["volume"])
            for row in candles
            if start <= int(row["time"]) < first_month_end
        ]
        if len(initial_turnover) < UNIVERSE_SELECTION_DAYS * 24 - 2:
            raise RuntimeError(
                f"{symbol} has insufficient bars in the initial liquidity-selection period"
            )
        initial_turnovers[symbol] = sum(initial_turnover)
        manifest["symbols"][symbol] = {
            "bars": len(candles),
            "first_bar_utc": datetime.fromtimestamp(int(candles[0]["time"]), timezone.utc).isoformat(),
            "last_bar_utc": datetime.fromtimestamp(int(candles[-1]["time"]), timezone.utc).isoformat(),
            "first_30d_quote_turnover_idr": sum(initial_turnover),
            "initial_30d_median_hourly_turnover_idr": (
                sorted(initial_turnover)[len(initial_turnover) // 2] if initial_turnover else None
            ),
        }
    selected_symbols = sorted(
        initial_turnovers,
        key=lambda symbol: (-initial_turnovers[symbol], symbol),
    )[:UNIVERSE_SELECTION_SIZE]
    selection_end = start + UNIVERSE_SELECTION_DAYS * 24 * TIMEFRAME_SECONDS
    test_end = end - end % TIMEFRAME_SECONDS
    manifest["selection_period_start_utc"] = datetime.fromtimestamp(start, timezone.utc).isoformat()
    manifest["selection_period_end_utc"] = datetime.fromtimestamp(selection_end, timezone.utc).isoformat()
    manifest["backtest_start_utc"] = datetime.fromtimestamp(selection_end, timezone.utc).isoformat()
    manifest["backtest_end_utc"] = datetime.fromtimestamp(test_end, timezone.utc).isoformat()
    manifest["selected_symbols"] = selected_symbols
    manifest["liquidity_ranking"] = [
        {"symbol": symbol, "first_30d_quote_turnover_idr": initial_turnovers[symbol]}
        for symbol in sorted(initial_turnovers, key=lambda symbol: (-initial_turnovers[symbol], symbol))
    ]
    with (DATA_DIR / "download_manifest.json").open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)
    with (DATA_DIR / "universe.json").open("w", encoding="utf-8") as file:
        json.dump(
            {
                "symbols": selected_symbols,
                "selection_period_start_utc": manifest["selection_period_start_utc"],
                "selection_period_end_utc": manifest["selection_period_end_utc"],
                "selection_method": manifest["universe_selection_method"],
            },
            file,
            indent=2,
        )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
