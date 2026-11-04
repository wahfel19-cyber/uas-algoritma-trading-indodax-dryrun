import unittest
from unittest.mock import patch

from app.dashboard import dashboard_payload


class DashboardTests(unittest.TestCase):
    def test_missing_forward_logs_do_not_look_like_zero_return_or_full_uptime(self):
        with patch("app.dashboard._read_backtest_summary", return_value={}):
            payload = dashboard_payload({})

        self.assertIsNone(payload["forward"]["total_return"])
        self.assertIsNone(payload["forward"]["max_drawdown"])
        self.assertIsNone(payload["forward"]["trade_count"])
        self.assertIsNone(payload["operations"]["uptime_fraction"])
        self.assertIsNone(payload["operations"]["api_errors"])
        self.assertIsNone(payload["forward_signal_count"])


if __name__ == "__main__":
    unittest.main()
