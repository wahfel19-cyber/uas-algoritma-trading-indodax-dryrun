# Refleksi status pengujian (sementara, 5 November 2026)

Dokumen ini **bukan refleksi akhir forward test**. Batas freeze 4 November 2026 pukul 12.00 WIB terlewat; deployment dan tick baru aktif setelah jadwal forward dimulai. Karena itu proyek ini tidak dapat mengklaim freeze tepat waktu atau forward test 10 hari penuh sesuai jadwal.

## Bukti dan hasil yang tersedia

- Downloader menyimpan 27.007 candle 1 jam dari Indodax untuk masing-masing delapan kandidat, pada rentang 5 Oktober 2023 23.00 UTC sampai 4 November 2026 05.00 UTC.
- Universe top-5 menurut turnover 30 hari awal adalah BTCIDR, ETHIDR, XRPIDR, DOGEIDR, dan SOLIDR. Data seleksi 30 hari dikeluarkan dari periode backtest.
- Backtest historis eksploratif menggunakan modal Rp100.000.000 dan menghasilkan ekuitas akhir Rp48.499.921,59, return total -51,50%, maximum drawdown 57,31%, CAGR -21,44%, 1.225 transaksi, win rate 21,31%, dan profit factor 0,735.
- Benchmark buy-and-hold BTC/IDR pada jendela historis tersebut tercatat +153,02%.
- Kalibrasi eksekusi memakai satu snapshot order book per pair. Snapshot direkam pada 4 November 2026 10.59.48 UTC, sesudah forward dimulai pada 05.00 UTC. Summary menandai `late_after_forward_start_non_compliant`; hasil historis di atas eksploratif dan bukan backtest yang memenuhi prosedur freeze.
- Deployment Vercel Production, Upstash Free, dan pemeriksaan koneksi /api/health telah berhasil.
- GitHub Actions run #4 berhasil secara manual pada 5 November 2026 sekitar 04.02 WIB. Pada pemeriksaan sesudahnya, metrik mencatat 1 panggilan, 1 candle diproses, 5 sinyal, 0 trade, 0 error API, dan equity simulasi Rp100.000.000. Satu tick ini bukan hasil forward test yang bermakna dan tidak membuktikan kelengkapan data.
- Skrip `scripts/recompute_dashboard.py` dirancang membangun ulang dashboard offline dari summary dan log mentah. Log saat ini berada di Redis dan belum diekspor sebagai arsip lokal yang dapat saya verifikasi di repository.
- Tes unit lokal terakhir yang tercatat: 16 tes lulus. Tes tersebut bukan bukti deployment atau forward test.

## Keterbatasan yang masih berlaku

- Tidak ada commit freeze sebelum 4 November 2026 pukul 12.00 WIB.
- Forward test terlambat dimulai; candle yang terlewat sebelum aktivasi tidak direkonstruksi. Pemeriksaan terkini mencatat satu candle diproses, bukan keseluruhan periode.
- Belum ada raw log yang diekspor dan diperiksa sebagai arsip submission.
- Forward window belum berakhir; backtest pembanding khusus untuk jendela forward yang benar-benar teramati belum dihitung.
- Snapshot order book terlambat dan hanya satu per pair, sehingga tidak mewakili variasi likuiditas intraperiode.

## Refleksi sementara

Hasil backtest eksploratif menunjukkan strategi kehilangan modal pada periode historis yang dihitung dan tertinggal dari benchmark buy-and-hold BTC. Biaya transaksi, spread, dan slippage membatasi hasil. Namun, karena kalibrasi terlambat, angka ini hanya bahan analisis dan bukan hasil yang memenuhi prosedur UAS. Satu tick awal menghasilkan sinyal tetapi tidak membuka trade; belum ada dasar untuk menyimpulkan kecocokan backtest-forward atau keberhasilan strategi.

Setelah forward window berakhir, bila pengujian terlambat diizinkan, ekspor semua log Redis, jalankan skrip hitung ulang dan backtest jendela yang sepadan, lalu laporkan cakupan dan keterlambatan secara eksplisit. Jangan mengubah timestamp atau menyajikan pengujian terlambat sebagai pengujian sesuai jadwal. Refleksi final harus menggunakan angka keluaran skrip dan log yang dapat diaudit, bukan nilai yang ditulis manual.
