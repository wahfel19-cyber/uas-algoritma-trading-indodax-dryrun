import os
import json
from pathlib import Path

TIMEFRAME = "60"
TIMEFRAME_SECONDS = 60 * 60
CANDIDATE_UNIVERSE = (
    "BTCIDR",
    "ETHIDR",
    "BNBIDR",
    "SOLIDR",
    "XRPIDR",
    "ADAIDR",
    "DOGEIDR",
    "LINKIDR",
)
UNIVERSE_SELECTION_SIZE = 5
UNIVERSE_SELECTION_DAYS = 30


def _configured_universe() -> tuple[str, ...]:
    environment_value = os.getenv("BOT_UNIVERSE", "").strip()
    if environment_value:
        return tuple(symbol.strip().upper() for symbol in environment_value.split(",") if symbol.strip())
    manifest_path = Path(__file__).resolve().parents[1] / "data" / "universe.json"
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)
        symbols = manifest.get("symbols")
        if isinstance(symbols, list) and symbols:
            return tuple(str(symbol).upper() for symbol in symbols)
    return CANDIDATE_UNIVERSE


UNIVERSE = _configured_universe()
CAPITAL_IDR = 100_000_000.0
MAX_OPEN_POSITIONS = 3
MAX_POSITION_WEIGHT = 0.15
DAILY_LOSS_LIMIT = 0.02
MIN_ORDER_IDR = 25_000.0
BUY_TAKER_FEE_FLOOR = float(os.getenv("BUY_TAKER_FEE_FLOOR", "0.0020555"))
SELL_TAKER_FEE_FLOOR = float(os.getenv("SELL_TAKER_FEE_FLOOR", "0.0041555"))
INDODAX_BASE_URL = os.getenv("INDODAX_BASE_URL", "https://indodax.com").rstrip("/")
CRON_SECRET = os.getenv("CRON_SECRET", "")
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
BOT_NAME = "indodax-dry-run"
BOT_VERSION = "1.0.0"
FORWARD_START_UTC = "2026-11-04T05:00:00+00:00"
FORWARD_END_UTC = "2026-11-14T05:00:00+00:00"
FORWARD_FIRST_CANDLE_UTC = "2026-11-04T04:00:00+00:00"
FORWARD_CANDLE_END_UTC = "2026-11-14T04:00:00+00:00"

if not 3 <= len(UNIVERSE) <= 10:
    raise ValueError("BOT_UNIVERSE must contain between 3 and 10 IDR pairs")
if len(set(UNIVERSE)) != len(UNIVERSE):
    raise ValueError("BOT_UNIVERSE cannot contain duplicates")
