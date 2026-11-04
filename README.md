# Indodax dry-run bot (UAS Algorithmic Trading)

Bot long-only untuk pasangan IDR Indodax. Menggunakan candle dan order book publik, mensimulasikan fill dengan level bid/ask, menyimpan state dan log di Upstash Redis, serta menjalankan tick terjadwal melalui GitHub Actions. Tidak menggunakan endpoint trading privat, API key Indodax, uang sungguhan, atau leverage.

> **Integritas hasil:** data pasar berasal dari Indodax. Jangan mengarang atau mengubah log maupun angka dashboard secara manual. Nilai forward hanya mencerminkan panggilan bot yang benar-benar tercatat.

## Status dan batasan UAS

- Freeze diwajibkan pada 4 November 2026 pukul 12.00 WIB. Riwayat repository dibuat setelah waktu itu sehingga **tidak membuktikan freeze tepat waktu**.
- Jendela UAS yang ditentukan: 4 November 2026 pukul 12.00 WIB sampai 14 November 2026 pukul 12.00 WIB. Bot baru berhasil menerima tick setelah jadwal dimulai; hasil ini tidak dapat diklaim sebagai forward test 10 hari lengkap sesuai jadwal.
- Data historis yang tersedia: 27.007 candle 1 jam dari Indodax untuk setiap delapan kandidat, 5 Oktober 2023 23.00 UTC sampai 4 November 2026 05.00 UTC. Universe top-5 dipilih berdasarkan turnover 30 hari awal: BTCIDR, ETHIDR, XRPIDR, DOGEIDR, SOLIDR.
- Backtest historis eksploratif: modal Rp100.000.000; ekuitas akhir Rp48.499.921,59; return -51,50%; max drawdown 57,31%; CAGR -21,44%; 1.225 trade; win rate 21,31%; profit factor 0,735; benchmark buy-and-hold BTC/IDR +153,02%.
- Kalibrasi friction memakai satu snapshot order book per pair, direkam setelah forward dimulai. Summary menandainya `late_after_forward_start_non_compliant`; hasil backtest ini **bukan bukti kepatuhan terhadap prosedur freeze**.
- Vercel Production dan Upstash Free terhubung. Pemeriksaan `/api/health` berhasil: API publik Indodax terjangkau dan lima pair tersedia. Dashboard live: https://uas-algoritma-trading-indodax-dryru.vercel.app/ .
- GitHub Actions run #4 berhasil secara manual pada 5 November 2026 sekitar 04.02 WIB. Metrik saat pemeriksaan: 1 panggilan, 1 candle diproses, 5 sinyal, 0 trade, 0 error API, equity simulasi Rp100.000.000. Ini hanya satu tick; bukan hasil 10 hari. Run #3 sebelumnya gagal karena secret belum tersedia saat deployment dibuat.
- Workflow dijadwalkan setiap jam pada menit ke-7 UTC. Tick pertama yang berhasil tidak mencakup candle-candle sebelum bot aktif; jangan mengisi periode yang terlewat dengan data buatan.
- Perbaikan konfigurasi Upstash dibuat setelah batas freeze pada commit `855b3bc0b8f0b3d0a19f76b908153234a42bee5e`. Perubahan tersebut memperbaiki integrasi, tidak mengubah atau membuktikan freeze strategi.
- Repository publik: https://github.com/wahfel19-cyber/uas-algoritma-trading-indodax-dryrun .

Bot long-only untuk pasangan IDR Indodax. Menggunakan candle dan order book publik, mensimulasikan fill dengan level bid/ask, menyimpan state dan log di Upstash Redis, serta menjalankan tick terjadwal melalui GitHub Actions. Tidak menggunakan endpoint trading privat, API key Indodax, uang sungguhan, atau leverage.

> **Integritas hasil:** data pasar berasal dari Indodax. Jangan mengarang atau mengubah log maupun angka dashboard secara manual. Nilai forward hanya mencerminkan panggilan bot yang benar-benar tercatat.

## Status dan batasan UAS

- Freeze diwajibkan pada 4 November 2026 pukul 12.00 WIB. Riwayat repository dibuat setelah waktu itu sehingga **tidak membuktikan freeze tepat waktu**.
- Jendela UAS yang ditentukan: 4 November 2026 pukul 12.00 WIB sampai 14 November 2026 pukul 12.00 WIB. Bot baru berhasil menerima tick setelah jadwal dimulai; hasil ini tidak dapat diklaim sebagai forward test 10 hari lengkap sesuai jadwal.
- Data historis yang tersedia: 27.007 candle 1 jam dari Indodax untuk setiap delapan kandidat, 5 Oktober 2023 23.00 UTC sampai 4 November 2026 05.00 UTC. Universe top-5 dipilih berdasarkan turnover 30 hari awal: BTCIDR, ETHIDR, XRPIDR, DOGEIDR, SOLIDR.
- Backtest historis eksploratif: modal Rp100.000.000; ekuitas akhir Rp48.499.921,59; return -51,50%; max drawdown 57,31%; CAGR -21,44%; 1.225 trade; win rate 21,31%; profit factor 0,735; benchmark buy-and-hold BTC/IDR +153,02%.
- Kalibrasi friction memakai satu snapshot order book per pair, direkam setelah forward dimulai. Summary menandainya `late_after_forward_start_non_compliant`; hasil backtest ini **bukan bukti kepatuhan terhadap prosedur freeze**.
- Vercel Production dan Upstash Free terhubung. Pemeriksaan `/api/health` berhasil: API publik Indodax terjangkau dan lima pair tersedia. Dashboard live: https://uas-algoritma-trading-indodax-dryru.vercel.app/ .
- GitHub Actions run #4 berhasil secara manual pada 5 November 2026 sekitar 04.02 WIB. Metrik saat pemeriksaan: 1 panggilan, 1 candle diproses, 5 sinyal, 0 trade, 0 error API, equity simulasi Rp100.000.000. Ini hanya satu tick; bukan hasil 10 hari. Run #3 sebelumnya gagal karena secret belum tersedia saat deployment dibuat.
- Workflow dijadwalkan setiap jam pada menit ke-7 UTC. Tick pertama yang berhasil tidak mencakup candle-candle sebelum bot aktif; jangan mengisi periode yang terlewat dengan data buatan.
- Perbaikan konfigurasi Upstash dibuat setelah batas freeze pada commit `855b3bc0b8f0b3d0a19f76b908153234a42bee5e`. Perubahan tersebut memperbaiki integrasi, tidak mengubah atau membuktikan freeze strategi.
- Repository publik: https://github.com/wahfel19-cyber/uas-algoritma-trading-indodax-dryrun .
- Raw log tersimpan di Redis. Sebelum pengumpulan akhir, ekspor log dengan `python scripts\export_logs.py`, hitung ulang dashboard dengan `python scripts\recompute_dashboard.py`, lalu periksa hasilnya. Belum ada hasil akhir perbandingan backtest 10 hari dengan jendela forward yang sama.

## Strategi

Lihat [strategy.md](strategy.md). Prinsip UTS Momentum Basket dipertahankan: momentum multi-horizon, filter SMA pendek/panjang, long-only, basket terbatas, cash sebagai penyangga, serta pembatasan likuiditas. Untuk kripto 1 jam, periode UTS saham (12/3 bulan dan rebalance 21 hari) diganti dengan momentum 24 jam/7 hari dan evaluasi candle per jam.

## Operasi dan keamanan

- Hanya endpoint publik Indodax yang dipanggil. Tidak ada API key akun atau order sungguhan.
- Rahasia hanya berada di environment Vercel/GitHub; jangan commit `.env`, token, atau URL berisi kredensial.
- Fungsi sinyal yang sama dipakai bot dan simulator. Retry dibatasi; error/data invalid dicatat dan pair tidak diperdagangkan.
- Tiap candle hanya diproses sekali per pair; daily loss limit WIB 2%, maksimum tiga posisi dan 15% equity per posisi.
- Tes lokal: `python -m unittest discover -s tests -v`.
- Refleksi pada [reflection.md](reflection.md) masih sementara dan tidak menyatakan kesimpulan final forward test.
