# Refleksi status pengujian (sementara, 4 November 2026)

Dokumen ini **bukan refleksi akhir forward test**. Pada waktu pencatatan, batas freeze sudah lewat, forward window 4–14 November 2026 masih berjalan, proyek belum dideploy ke Vercel/Upstash, dan belum ada log tick forward. Karena itu kecocokan sinyal, uptime, return forward, gap return 10 hari, serta rata-rata keterlambatan tidak dapat dihitung. Nilai-nilai tersebut sengaja tidak diisi dengan nol.

## Bukti dan hasil yang tersedia

- Downloader menyimpan 27.007 candle 1 jam dari Indodax untuk masing-masing delapan kandidat, pada rentang 5 Oktober 2023 23.00 UTC sampai 4 November 2026 05.00 UTC.
- Universe top-5 menurut turnover 30 hari awal adalah BTCIDR, ETHIDR, XRPIDR, DOGEIDR, dan SOLIDR. Data seleksi 30 hari dikeluarkan dari periode backtest.
- Backtest historis eksploratif yang tersedia menggunakan modal awal Rp100.000.000 dan menghasilkan ekuitas akhir Rp48.499.921,59, return total -51,50%, maximum drawdown 57,31%, CAGR -21,44%, 1.225 transaksi, win rate 21,31%, dan profit factor 0,735.
- Benchmark buy-and-hold BTC/IDR pada jendela historis tersebut tercatat +153,02%.
- Kalibrasi eksekusi memakai satu snapshot order book untuk setiap pair aktif. Snapshot tersebut direkam pada 4 November 2026 10.59.48 UTC, sesudah forward dimulai pada 05.00 UTC. Hasil historis di atas diberi label `late_after_forward_start_non_compliant`; kalibrasi ini tidak memenuhi syarat bukti pra-forward/freeze dan hasilnya tidak boleh disebut backtest patuh UAS.
- Sumber data candle dan snapshot adalah data publik Indodax. Skrip `scripts/recompute_dashboard.py` membangun ulang dashboard offline dari summary dan log yang tersedia.
- Tes unit lokal terakhir: 16 tes lulus. Tes tersebut memvalidasi fungsi data, strategi, simulasi, eksekusi, dan dashboard; bukan bukti deployment atau forward test.

## Keterbatasan yang belum dapat diselesaikan dari bukti saat ini

- Tidak ada commit freeze sebelum 4 November 2026 pukul 12.00 WIB.
- Tidak ada bukti deployment Vercel/Upstash, tick terjadwal, atau koneksi deployment `/api/health`.
- Tidak ada raw log forward, sehingga metrik operasional dan hasil trading forward belum tersedia.
- Backtest pembanding khusus 10 hari yang sama belum dijalankan; jendela forward juga belum berakhir.
- Snapshot order book terlambat dan jumlahnya hanya satu per pair, sehingga tidak mewakili variasi likuiditas intraperiode.

## Refleksi sementara

Hasil eksploratif menunjukkan strategi kehilangan modal pada periode historis yang dihitung dan tertinggal dari benchmark buy-and-hold BTC. Biaya transaksi, spread, dan slippage terukur dalam summary membatasi hasil; jumlah sinyal/trade yang tinggi dan biaya yang besar perlu ditinjau sebelum menyimpulkan apa pun tentang strategi. Namun, karena kalibrasi terlambat, angka ini hanya bahan analisis dan bukan hasil yang memenuhi prosedur UAS. Tidak ada dasar untuk menyimpulkan kecocokan backtest-forward atau keberhasilan strategi.

Sebelum berkas ini dapat menjadi refleksi akhir, perlu arahan dosen mengenai tindak lanjut setelah freeze terlewat. Jika forward test terlambat diizinkan, jalankan bot tanpa mengubah strategi/universe, simpan semua raw log, hitung pembanding 10 hari dari data yang sama, lalu isi metrik hanya dari skrip dan log yang dapat diaudit. Jangan mengubah timestamp atau menyajikan pengujian terlambat sebagai pengujian sesuai jadwal.
