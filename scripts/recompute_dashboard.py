from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard import dashboard_payload

RAW_DIR = ROOT / "logs" / "raw"
OUT_FILE = ROOT / "dashboard" / "offline_dashboard.html"
LOG_TYPES = ("calls", "candles", "controls", "equity", "errors", "orders", "signals", "snapshots", "trades")


def load_logs(log_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}
    for event_type in LOG_TYPES:
        path = log_dir / f"{event_type}.jsonl"
        rows: List[Dict[str, Any]] = []
        if path.exists():
            with path.open("r", encoding="utf-8-sig") as file:
                for line_number, line in enumerate(file, start=1):
                    if line.strip():
                        value = json.loads(line)
                        if not isinstance(value, dict):
                            raise ValueError(f"{path}:{line_number} is not a JSON object")
                        rows.append(value)
        result[event_type] = rows
    return result


def _format_percent(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.2%}"


def _format_idr(value: Any) -> str:
    return "N/A" if value is None else f"Rp {float(value):,.0f}"


def _format_number(value: Any) -> str:
    if value is None:
        return "N/A"
    if value == "infinite":
        return "∞"
    return f"{float(value):.2f}"


def render_html(payload: Dict[str, Any]) -> str:
    backtest = payload.get("backtest") or {}
    forward = payload.get("forward") or {}
    forward_window = backtest.get("forward_window") or {}
    operations = payload.get("operations") or {}
    benchmark = payload.get("benchmark_btc_return")
    calibration_timing = backtest.get("calibration_timing")
    data_status = (
        "Data berasal dari log asli yang diekspor."
        if payload.get("data_available")
        else "Belum ada log backtest/forward test. Angka akan muncul setelah data asli direkam."
    )
    calibration_notice = (
        "PERINGATAN: kalibrasi friction dilakukan setelah jadwal forward dimulai; "
        "hasil backtest ini eksploratif dan tidak memenuhi prosedur freeze."
        if calibration_timing == "late_after_forward_start_non_compliant"
        else "Kalibrasi friction dilakukan sebelum forward start."
        if calibration_timing == "before_forward_start"
        else "Status waktu kalibrasi belum tersedia."
    )
    rows = [
        ("Return total", _format_percent(backtest.get("total_return")), _format_percent(forward.get("total_return"))),
        ("CAGR", _format_percent(backtest.get("cagr")), "Tidak ditampilkan untuk forward 10 hari"),
        ("Maximum drawdown", _format_percent(backtest.get("max_drawdown")), _format_percent(forward.get("max_drawdown"))),
        ("Profit factor", _format_number(backtest.get("profit_factor")), _format_number(forward.get("profit_factor"))),
        ("Win rate", _format_percent(backtest.get("win_rate")), _format_percent(forward.get("win_rate"))),
        ("Rata-rata untung", _format_idr(backtest.get("average_win_idr")), _format_idr(forward.get("average_win_idr"))),
        ("Rata-rata rugi", _format_idr(backtest.get("average_loss_idr")), _format_idr(forward.get("average_loss_idr"))),
        ("Jumlah trade", str(backtest.get("trade_count", "N/A")), str(forward.get("trade_count", "N/A"))),
        ("Porsi biaya / laba kotor", _format_percent(backtest.get("cost_share_of_gross_profit")), _format_percent(forward.get("cost_share_of_gross_profit"))),
    ]
    table_rows = "\n".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(bt))}</td><td>{html.escape(str(fw))}</td></tr>"
        for label, bt, fw in rows
    )
    spreads = payload.get("spread_medians") or {}
    spread_rows = "\n".join(
        f"<tr><th>{html.escape(symbol)}</th><td>{float(value):.4%}</td></tr>"
        for symbol, value in sorted(spreads.items())
    ) or '<tr><td colspan="2">Belum ada snapshot live</td></tr>'
    uptime = operations.get("uptime_fraction")
    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard Forward Test Indodax</title>
<style>
body{{font:16px system-ui,Segoe UI,sans-serif;background:#0b1220;color:#e5edf8;margin:0;padding:24px}}
main{{max-width:1100px;margin:auto}}h1,h2{{color:#9ed4ff}}.note,section{{background:#121d30;border:1px solid #263751;border-radius:12px;padding:18px;margin:16px 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}}.card{{background:#17243a;padding:16px;border-radius:9px}}
.label{{font-size:12px;color:#aab8ca;text-transform:uppercase}}.value{{font-size:24px;font-weight:700;margin-top:8px}}
table{{border-collapse:collapse;width:100%;margin-top:12px}}td,th{{text-align:left;padding:9px;border-bottom:1px solid #263751}}th{{color:#b9d8fc}}
</style>
</head>
<body><main>
<h1>Indodax Dry-Run Forward Test</h1>
<p class="note">{html.escape(data_status)} Dashboard ini dibuat ulang dari log mentah; jangan mengisi metrik secara manual.</p>
<section><h2>Ringkasan operasional</h2><div class="grid">
<div class="card"><div class="label">Candle terjadwal</div><div class="value">{operations.get("scheduled_candles", "N/A")}</div></div>
<div class="card"><div class="label">Candle diproses tepat waktu</div><div class="value">{operations.get("processed_candles", "N/A")}</div></div>
<div class="card"><div class="label">Uptime</div><div class="value">{_format_percent(uptime)}</div></div>
<div class="card"><div class="label">Error API/operasional</div><div class="value">{operations.get("api_errors", "N/A")}</div></div>
<div class="card"><div class="label">Pemakaian kill switch</div><div class="value">{operations.get("kill_switch_uses", "N/A")}</div></div>
</div></section>
<section><h2>Backtest vs forward</h2><table><thead><tr><th>Metrik</th><th>Backtest 3 tahun</th><th>Forward test</th></tr></thead><tbody>{table_rows}</tbody></table>
<p class="note">{html.escape(calibration_notice)}</p>
<p>Forward test belum memiliki log live; tabel tidak membuktikan bot berjalan.</p>
<p>Benchmark buy-and-hold BTC/IDR (jendela forward): {_format_percent(benchmark)}</p>
<p>Backtest 10 hari pembanding: {_format_percent(forward_window.get("total_return"))}. Gap forward − backtest: {_format_percent(payload.get("gap_forward_vs_backtest_return"))}.</p>
</section>
<section><h2>Median spread dari snapshot mentah forward</h2><table><thead><tr><th>Pasangan</th><th>Median spread</th></tr></thead><tbody>{spread_rows}</tbody></table></section>
<section><h2>Catatan audit</h2><p>Harga strategi berasal dari candle tertutup. Forward fill dihitung dari level bid/ask; backtest memakai median spread dan market impact yang diukur dari snapshot order book.</p></section>
</main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute all offline dashboard metrics from raw JSONL logs.")
    parser.add_argument("--logs", default=str(RAW_DIR))
    parser.add_argument("--output", default=str(OUT_FILE))
    args = parser.parse_args()
    logs = load_logs(Path(args.logs))
    payload = dashboard_payload(logs)
    html_content = render_html(payload)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_content, encoding="utf-8")
    print(json.dumps({"payload": payload, "offline_dashboard": str(output)}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
