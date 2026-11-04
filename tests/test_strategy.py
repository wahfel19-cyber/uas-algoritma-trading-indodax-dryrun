import unittest

from app.strategy import MIN_HISTORY, entry_score, signal_for_pair, strategy_values


def candles_from_closes(closes):
    return [
        {
            "time": index * 3600,
            "open": value,
            "high": value,
            "low": value,
            "close": value,
            "volume": 1.0,
        }
        for index, value in enumerate(closes)
    ]


class StrategyTests(unittest.TestCase):
    def test_requires_full_seven_day_history(self):
        self.assertIsNone(signal_for_pair(candles_from_closes([100.0] * (MIN_HISTORY - 1))))

    def test_rising_market_triggers_buy(self):
        closes = [100.0 * (1.001**index) for index in range(MIN_HISTORY)]
        candles = candles_from_closes(closes)
        self.assertEqual(signal_for_pair(candles), "BUY")
        self.assertGreater(entry_score(candles), 0)

    def test_flat_market_holds(self):
        self.assertEqual(signal_for_pair(candles_from_closes([100.0] * MIN_HISTORY)), "HOLD")

    def test_falling_market_triggers_sell(self):
        closes = [100.0 * (0.999**index) for index in range(MIN_HISTORY)]
        self.assertEqual(signal_for_pair(candles_from_closes(closes)), "SELL")

    def test_indicator_values_use_completed_series(self):
        values = strategy_values(candles_from_closes([100.0 * (1.001**i) for i in range(MIN_HISTORY)]))
        self.assertAlmostEqual(values["close"], 100.0 * (1.001 ** (MIN_HISTORY - 1)))
        self.assertGreater(values["sma_20"], values["sma_50"])


if __name__ == "__main__":
    unittest.main()
