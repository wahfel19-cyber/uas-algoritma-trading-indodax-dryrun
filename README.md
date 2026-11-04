# Indodax dry-run bot (UAS Algorithmic Trading)

Bot long-only untuk pasangan IDR Indodax. Menggunakan candle dan order book publik, mensimulasikan fill pada level bid/ask, menyimpan state serta log di Upstash Redis, dan menjalankan tick terjadwal lewat GitHub Actions. Bot tidak memakai endpoint trading privat, API key Indodax, uang sungguhan, atau leverage.

> **Integritas hasil:** data pasar berasal dari Indodax. Jangan mengarang atau mengubah log maupun angka dashboard secara manual. Nilai forward hanya mencerminkan panggilan bot yang benar-benar tercatat.

## Status dan batasan UAS (5 November 2026)

- Freeze diwajibkan 4 November 2026 pukul 12.00 WIB. Riwayat repository dibuat setelah waktu itu dan **tidak membuktikan freeze tepat waktu**.
- Jendela UAS: 4 November 2026 pukul 12.00 WIB sampai 14 November 2026 pukul 12.00 WIB. Bot baru berhasil menerima tick setelah jendela dimulai; hasilnya tidak dapat diklaim sebagai forward test 10 hari penuh sesuai jadwal.
- Data historis tersedia: 27.007 candle 1 jam dari Indodax untuk setiap delapan kandidat, 5 Oktober 2023 23.00 UTC hingga 4 November 2026 05.00 UTC. Universe top-5 dipilih berdasarkan turnover 30 hari awal: BTCIDR, ETHIDR, XRPIDR, DOGEIDR, SOLIDR.
- Backtest historis eksploratif: modal Rp100.000.000; ekuitas akhir Rp48.499.921,59; return -51,50%; max drawdown 57,31%; CAGR -21,44%; 1.225 trade; win rate 21,31%; profit factor 0,735; benchmark buy-and-hold BTC/IDR +153,02%.
- Kalibrasi friction menggunakan satu snapshot order book per pair setelah forward dimulai. Summary menandai `late_after_forward_start_non_compliant`; hasil itu **bukan bukti kepatuhan terhadap prosedur freeze**.
- Vercel Production, Upstash Free, dan pemeriksaan `/api/health` berhasil. Dashboard: https://uas-algoritma-trading-indodax-dryru.vercel.app/ . Repository publik: https://github.com/wahfel19-cyber/uas-algoritma-trading-indodax-dryrun .
- GitHub Actions run #4 berhasil secara manual pada 5 November sekitar 04.02 WIB. Saat diperiksa, metrik mencatat 1 panggilan, 1 candle diproses, 5 sinyal, 0 trade, 0 error API, dan equity simulasi Rp100.000.000. Ini hanya satu tick, bukan hasil forward test 10 hari.
- Workflow berjalan setiap jam pada menit ke-7 UTC. Kini workflow **gagal secara eksplisit** jika secret wajib tidak tersedia, agar run yang tidak menjalankan tick tidak tampak sukses. Tick tidak merekonstruksi candle sebelum bot aktif.
- Perbaikan konfigurasi Upstash dibuat setelah freeze pada commit `855b3bc0b8f0b3d0a19f76b908153234a42bee5e`; perubahan tersebut memperbaiki integrasi, tidak mengubah atau membuktikan freeze strategi.
- Log berada di Redis dan belum diverifikasi sebagai arsip lokal. Belum ada hasil akhir perbandingan backtest 10 hari dengan jendela forward yang sama. Refleksi di [reflection.md](reflection.md) masih sementara.

## Strategi

Lihat [strategy.md](strategy.md). Prinsip UTS Momentum Basket dipertahankan: momentum multi-horizon, filter SMA pendek/panjang, long-only, basket terbatas, cash sebagai penyangga, serta pembatasan likuiditas. Untuk kripto 1 jam, periode UTS saham diganti dengan momentum 24 jam/7 hari dan evaluasi candle per jam.

## Operasi dan keamanan

- Hanya endpoint publik Indodax yang dipanggil. Tidak ada API key akun atau order sungguhan.
- Rahasia hanya berada di environment Vercel/GitHub; jangan commit `.env`, token, atau URL berisi kredensial. Contoh variabel ada di [.env.example](.env.example).
- Fungsi sinyal yang sama dipakai bot dan simulator. Retry dibatasi; error/data invalid dicatat dan pair tidak diperdagangkan.
- Tiap candle hanya diproses sekali per pair; daily loss limit WIB 2%, maksimum tiga posisi dan 15% equity per posisi.
- Tes lokal: `python -m unittest discover -s tests -v`.
- Sebelum pengumpulan akhir, ekspor log dengan `python scripts\export_logs.py`, hitung ulang dashboard dengan `python scripts\recompute_dashboard.py`, lalu periksa hasilnya dan lengkapi refleksi. Jangan menampilkan angka hasil hitung ulang sebelum skrip benar-benar dijalankan atas log mentah.
