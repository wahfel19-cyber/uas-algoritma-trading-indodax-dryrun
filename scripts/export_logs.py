from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.storage import read_events

EVENT_TYPES = ("calls", "candles", "controls", "equity", "errors", "orders", "signals", "snapshots", "trades")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export all raw dry-run bot logs from Upstash Redis to JSONL.")
    parser.add_argument("--output", default=str(ROOT / "logs" / "raw"))
    args = parser.parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    totals = {}
    for event_type in EVENT_TYPES:
        events = read_events(event_type)
        path = output_dir / f"{event_type}.jsonl"
        with path.open("w", encoding="utf-8") as file:
            for event in events:
                file.write(json.dumps(event, separators=(",", ":"), allow_nan=False) + "\n")
        totals[event_type] = len(events)
    print(json.dumps({"output": str(output_dir), "events": totals}, indent=2))


if __name__ == "__main__":
    main()
