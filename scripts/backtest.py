from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import (
    BUY_TAKER_FEE_FLOOR,
    FORWARD_START_UTC,
    INDODAX_BASE_URL,
    SELL_TAKER_FEE_FLOOR,
    UNIVERSE,
)
from app.data_client import fetch_pairs, fetch_server_time
from app.execution import fee_rate_for_pair
from app.simulation import buy_and_hold_btc, simulate

DATA_DIR = ROOT / "data"
HISTORY_DIR = DATA_DIR / "historical"
RAW_LOG_DIR = ROOT / "logs" / "raw"


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Datetime must have a timezone: {value}")
    return parsed.astimezone(timezone.utc)


def load_candles(symbol: str) -> List[Dict[str, float]]:
    path = HISTORY_DIR / f"{symbol}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing historical file: {path}")
    rows: Dict[int, Dict[str, float]] = {}
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            timestamp = int(row.get("time", row.get("timestamp", "0")))
            if timestamp <= 0:
                continue
            rows[timestamp] = {
                "time": timestamp,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
    return [rows[timestamp] for timestamp in sorted(rows)]


def load_json_lines(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number} is not a JSON object")
                records.append(value)
    return records


def estimate_calibration(
    symbols: List[str],
    snapshots: List[Dict[str, Any]],
    pair_metadata: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    by_symbol: Dict[str, List[Dict[str, Any]]] = {symbol: [] for symbol in symbols}
    for snapshot in snapshots:
        symbol = snapshot.get("symbol")
        if symbol in by_symbol and snapshot.get("spread_fraction") is not None:
            by_symbol[symbol].append(snapshot)
    calibration: Dict[str, Dict[str, float]] = {}
    for symbol in symbols:
        rows = [
            row
            for row in by_symbol[symbol]
            if float(row.get("buy_fill_fraction", 0.0)) >= 0.999
            and float(row.get("sell_fill_fraction", 0.0)) >= 0.999
        ]
        if not rows:
            raise ValueError(
                f"No full 15-million-IDR order-book snapshots for {symbol}; "
                "collect deeper-book snapshots before backtesting"
            )
        spreads = [float(row["spread_fraction"]) for row in rows]
        impacts = [
            (float(row.get("buy_impact_fraction", 0.0)) + float(row.get("sell_impact_fraction", 0.0))) / 2.0
            for row in rows
        ]
        calibration[symbol] = {
            "spread_fraction": median(spreads),
            "slippage_fraction": median(impacts),
            "fee_buy": fee_rate_for_pair(pair_metadata[symbol], "BUY"),
            "fee_sell": fee_rate_for_pair(pair_metadata[symbol], "SELL"),
            "snapshot_count": float(len(rows)),
        }
    return calibration


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")


def _resolve_pairs(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    path = DATA_DIR / "pairs.json"
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            value = json.load(file)
        pairs = value.get("pairs", {})
        if all(symbol in pairs for symbol in symbols):
            return pairs
    live = fetch_pairs()
    missing = [symbol for symbol in symbols if symbol not in live]
    if missing:
        raise ValueError(f"Indodax no longer lists configured pairs: {', '.join(missing)}")
    return live


def _default_start() -> datetime:
    manifest_path = DATA_DIR / "download_manifest.json"
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)
        if manifest.get("backtest_start_utc"):
            return parse_datetime(manifest["backtest_start_utc"])
    return parse_datetime("2023-11-03T00:00:00Z")


def run(
    start: datetime,
    end: datetime,
    symbols: List[str],
    allow_short_window: bool = False,
    forward_start: datetime | None = None,
    forward_end: datetime | None = None,
    calibration_cutoff: datetime | None = None,
    allow_late_calibration: bool = False,
) -> Dict[str, Any]:
    if end <= start:
        raise ValueError("end must be later than start")
    if not allow_short_window and end - start < timedelta(days=365 * 3):
        raise ValueError("Backtest must span at least 3 years; use --short-window only for forward comparison")
    candles = {symbol: load_candles(symbol) for symbol in symbols}
    pairs = _resolve_pairs(symbols)
    calibration_cutoff = calibration_cutoff or parse_datetime(FORWARD_START_UTC)
    forward_cutoff = parse_datetime(FORWARD_START_UTC)
    late_calibration = calibration_cutoff > forward_cutoff
    if late_calibration and not allow_late_calibration:
        raise ValueError(
            "Calibration cutoff is after the scheduled forward start; "
            "pass --allow-late-calibration to explicitly mark this result non-compliant"
        )
    snapshots = [
        row
        for row in load_json_lines(RAW_LOG_DIR / "orderbook_snapshots.jsonl")
        if row.get("timestamp") and parse_datetime(row["timestamp"]) < calibration_cutoff
    ]
    calibration = estimate_calibration(symbols, snapshots, pairs)
    result = simulate(candles, calibration, pairs, start, end)
    btc_benchmark = buy_and_hold_btc(candles["BTCIDR"], calibration["BTCIDR"], start, end) if "BTCIDR" in candles else None
    result["metrics"]["window_start"] = start.isoformat()
    result["metrics"]["window_end"] = end.isoformat()
    result["metrics"]["universe"] = symbols
    result["metrics"]["fee_source"] = {
        "pairs_api": f"{INDODAX_BASE_URL}/api/pairs",
        "official_all_in": "https://help.indodax.com/hc/id/articles/4416646599705-Rincian-Biaya-Transaksi-di-INDODAX",
        "accessed_date": "2026-11-03",
        "buy_taker_fee_floor": BUY_TAKER_FEE_FLOOR,
        "sell_taker_fee_floor": SELL_TAKER_FEE_FLOOR,
    }
    result["metrics"]["calibration"] = calibration
    result["metrics"]["calibration_snapshot_cutoff_utc"] = calibration_cutoff.isoformat()
    result["metrics"]["calibration_timing"] = (
        "late_after_forward_start_non_compliant" if late_calibration else "before_forward_start"
    )
    result["metrics"]["benchmark_btc_buy_hold"] = btc_benchmark
    result["metrics"]["source_data"] = "Indodax history_v2 candles and measured order-book snapshots"
    result["metrics"]["uses_synthetic_data"] = False
    if (forward_start is None) != (forward_end is None):
        raise ValueError("Provide both --forward-start and --forward-end")
    if forward_start is not None and forward_end is not None:
        if forward_end <= forward_start:
            raise ValueError("forward end must be later than forward start")
        forward_result = simulate(candles, calibration, pairs, forward_start, forward_end)
        forward_result["metrics"]["benchmark_btc_buy_hold"] = (
            buy_and_hold_btc(
                candles["BTCIDR"],
                calibration["BTCIDR"],
                forward_start,
                forward_end,
            )
            if "BTCIDR" in candles
            else None
        )
        result["metrics"]["forward_window"] = forward_result["metrics"]
        _write_jsonl(DATA_DIR / "forward_backtest_equity.jsonl", forward_result["equity_curve"])
        _write_jsonl(DATA_DIR / "forward_backtest_trades.jsonl", forward_result["trades"])
        _write_jsonl(DATA_DIR / "forward_backtest_signals.jsonl", forward_result["signals"])

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / "backtest_summary.json").open("w", encoding="utf-8") as file:
        json.dump(result["metrics"], file, indent=2, allow_nan=False)
    _write_jsonl(DATA_DIR / "backtest_equity.jsonl", result["equity_curve"])
    _write_jsonl(DATA_DIR / "backtest_trades.jsonl", result["trades"])
    _write_jsonl(DATA_DIR / "backtest_signals.jsonl", result["signals"])
    return result["metrics"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backtest the frozen strategy on authentic Indodax candles with measured book costs."
    )
    parser.add_argument("--start", help="ISO-8601 UTC; defaults to end of the 30-day selection window")
    parser.add_argument("--end", help="ISO-8601 UTC end time; defaults to Indodax server time")
    parser.add_argument("--symbols", default=",".join(UNIVERSE))
    parser.add_argument("--short-window", action="store_true", help="Allow a window shorter than three years")
    parser.add_argument("--forward-start", help="Optional forward-comparison candle-window start in UTC")
    parser.add_argument("--forward-end", help="Optional forward-comparison candle-window end in UTC")
    parser.add_argument(
        "--calibration-cutoff",
        help=(
            "Maximum UTC timestamp of order-book snapshots used for friction calibration; "
            "defaults to the scheduled forward start"
        ),
    )
    parser.add_argument(
        "--allow-late-calibration",
        action="store_true",
        help="Permit and label calibration after the scheduled forward start as non-compliant",
    )
    args = parser.parse_args()
    end_timestamp = (
        int(parse_datetime(args.end).timestamp())
        if args.end
        else fetch_server_time()
    )
    end_timestamp -= end_timestamp % 3600
    end = datetime.fromtimestamp(end_timestamp, timezone.utc)
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]
    manifest_path = DATA_DIR / "download_manifest.json"
    if args.symbols == ",".join(UNIVERSE) and manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)
        selected = manifest.get("selected_symbols")
        if isinstance(selected, list) and 3 <= len(selected) <= 10:
            symbols = [str(symbol).upper() for symbol in selected]
    if not 3 <= len(symbols) <= 10:
        raise ValueError("Choose 3 to 10 symbols")
    metrics = run(
        parse_datetime(args.start) if args.start else _default_start(),
        end,
        symbols,
        args.short_window,
        parse_datetime(args.forward_start) if args.forward_start else None,
        parse_datetime(args.forward_end) if args.forward_end else None,
        parse_datetime(args.calibration_cutoff) if args.calibration_cutoff else None,
        args.allow_late_calibration,
    )
    print(json.dumps(metrics, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
