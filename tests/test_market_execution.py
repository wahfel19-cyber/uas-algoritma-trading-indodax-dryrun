import unittest

from app.data_client import closed_candles, normalize_candles, normalize_order_book, validate_candles
from app.execution import (
    best_prices,
    daily_loss_reached,
    fee_rate_for_pair,
    fill_market_order,
    floor_quantity,
)


class MarketDataTests(unittest.TestCase):
    def test_normalizes_real_indodax_history_shape(self):
        candles = normalize_candles(
            {
                "value": [
                    {
                        "Time": 1000,
                        "Open": 100,
                        "High": 110,
                        "Low": 90,
                        "Close": 105,
                        "Volume": "2.5",
                    }
                ]
            }
        )
        self.assertEqual(candles[0]["time"], 1000)
        self.assertEqual(candles[0]["volume"], 2.5)

    def test_normalizes_top_level_history_array(self):
        candles = normalize_candles(
            [
                {
                    "Time": 1000,
                    "Open": 100,
                    "High": 110,
                    "Low": 90,
                    "Close": 105,
                    "Volume": "2.5",
                }
            ]
        )
        self.assertEqual(candles[0]["time"], 1000)
        self.assertEqual(candles[0]["volume"], 2.5)

    def test_normalizes_live_depth_buy_sell_levels(self):
        book = normalize_order_book(
            {
                "buy": [{"value": ["99", "2"], "Count": 1}],
                "sell": [{"value": ["100", "3"], "Count": 1}],
            }
        )
        self.assertEqual(best_prices(book), (99.0, 100.0))

    def test_drops_open_candle(self):
        candles = [{"time": 0}, {"time": 3600}, {"time": 7200}]
        self.assertEqual([row["time"] for row in closed_candles(candles, 10800)], [0, 3600, 7200])
        self.assertEqual([row["time"] for row in closed_candles(candles, 10799)], [0, 3600])

    def test_rejects_gapped_or_zero_volume_indicator_window(self):
        candles = [
            {"time": index * 3600, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}
            for index in range(169)
        ]
        self.assertIsNone(validate_candles(candles, 169 * 3600))
        candles[-2]["time"] -= 1
        self.assertEqual(validate_candles(candles, 169 * 3600), "missing_candle_in_indicator_window")
        candles[-2]["time"] = (len(candles) - 2) * 3600
        candles[-1]["volume"] = 0
        self.assertEqual(validate_candles(candles, 169 * 3600), "zero_or_negative_price_or_volume")


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.book = {
            "bids": [(99.0, 5.0), (98.0, 10.0)],
            "asks": [(100.0, 2.0), (110.0, 5.0)],
        }

    def test_buy_consumes_ask_levels_and_calculates_fee(self):
        fill = fill_market_order(self.book, "BUY", 3.0, 0.1, 0.002)
        self.assertEqual(fill["filled_quantity"], 3.0)
        self.assertAlmostEqual(fill["average_price"], 310 / 3)
        self.assertAlmostEqual(fill["fee"], 0.62)
        self.assertEqual(fill["best_bid"], 99.0)
        self.assertEqual(fill["best_ask"], 100.0)

    def test_quantity_rounds_down_to_pair_increment(self):
        self.assertEqual(floor_quantity(1.239, 0.01), 1.23)

    def test_daily_loss_limit_threshold(self):
        self.assertTrue(daily_loss_reached(98.0, 100.0))
        self.assertFalse(daily_loss_reached(98.01, 100.0))

    def test_api_fee_is_raised_to_side_specific_official_all_in_floor(self):
        pair = {"trade_fee_percent_taker": 0.2}
        self.assertAlmostEqual(fee_rate_for_pair(pair, "BUY"), 0.0020555)
        self.assertAlmostEqual(fee_rate_for_pair(pair, "SELL"), 0.0041555)


if __name__ == "__main__":
    unittest.main()
