import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.simulation import simulate


class SimulationExecutionTests(unittest.TestCase):
    def test_orders_execute_on_the_next_candle_open(self):
        symbol = "BTCIDR"
        start_timestamp = 169 * 3600
        candles = [
            {
                "time": index * 3600,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 1.0,
            }
            for index in range(173)
        ]
        candles[170]["open"] = 110.0
        candles[171]["open"] = 120.0
        candles[171]["close"] = 120.0
        candles[172]["open"] = 130.0
        start = datetime.fromtimestamp(start_timestamp, timezone.utc)
        end = datetime.fromtimestamp(start_timestamp + 3 * 3600, timezone.utc)

        def fake_signal(history):
            candle_time = int(history[-1]["time"])
            if candle_time == start_timestamp:
                return "BUY"
            if candle_time == start_timestamp + 2 * 3600:
                return "SELL"
            return None

        with patch("app.simulation.signal_for_pair", side_effect=fake_signal):
            result = simulate(
                {symbol: candles},
                {
                    symbol: {
                        "spread_fraction": 0.0,
                        "slippage_fraction": 0.0,
                        "fee_buy": 0.0,
                        "fee_sell": 0.0,
                    }
                },
                {symbol: {"quantity_increment": 0.001}},
                start,
                end,
            )

        self.assertEqual(len(result["trades"]), 1)
        trade = result["trades"][0]
        self.assertEqual(trade["entry_fill_price"], 110.0)
        self.assertEqual(trade["exit_fill_price"], 130.0)
        self.assertEqual(trade["entry_signal_price"], 100.0)
        self.assertEqual(trade["exit_signal_price"], 120.0)
        self.assertEqual(trade["entry_time"], datetime.fromtimestamp(start_timestamp + 3600, timezone.utc).isoformat())
        self.assertEqual(trade["exit_time"], end.isoformat())


if __name__ == "__main__":
    unittest.main()
