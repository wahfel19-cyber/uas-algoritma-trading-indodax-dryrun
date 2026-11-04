# Indodax dry-run bot (UAS Algorithmic Trading)




Bot long-only untuk pasangan IDR Indodax. Ia memakai candle dan order book publik, mensimulasikan fill dengan menghabiskan level bid/ask, menyimpan state/log di Upstash Redis, dan berjalan melalui GitHub Actions setiap jam pada menit ke-7. Tidak ada endpoint trading privat, API key Indodax, uang sungguhan, atau leverage.




> **Integritas hasil:** repo ini tidak berisi angka backtest/forward rekaan. Backtest hanya menerima data `history_v2` asli dan snapshot order book mentah. Forward metrics baru ada setelah bot menerima panggilan sungguhan. Jangan mengisi atau mengubah log/angka dashboard secara manual.




## Status submission




- Repo publik dibuat pada 4 November 2026 setelah batas freeze pukul 12.00 WIB. Riwayat commit tidak membuktikan freeze tepat waktu; jangan klaim sebaliknya.
- Saat publikasi awal, data backtest tiga tahun, deployment Vercel, dan log forward test faktual belum tersedia.
- Strategi, aturan risk, kode, dan universe harus dibekukan dalam commit pada atau sebelum **4 November 2026 pukul 12.00 WIB**.
- Forward window: **4 November 2026 pukul 12.00 WIB – 14 November 2026 pukul 12.00 WIB**.
- Pemulihan terlambat: downloader kini mengambil 27.007 candle/jam asli untuk masing-masing delapan kandidat dari 5 Oktober 2023 23.00 UTC sampai 4 November 2026 05.00 UTC; universe top-5 ditetapkan dari turnover 30 hari awal.
- Snapshot order book pertama baru direkam 4 November 2026 10.59.48 UTC, sesudah forward dimulai. Backtest yang dihitung memakai satu snapshot per pair tersebut sebagai kalibrasi terlambat, ditandai `late_after_forward_start_non_compliant`; hasilnya eksploratif dan bukan bukti kepatuhan terhadap freeze.
- Deploy Vercel sudah Ready dan terhubung ke Upstash (Free); `/api/health` mengonfirmasi API publik Indodax terjangkau dan lima pair tersedia. `/api/metrics` menampilkan hasil backtest historis, tetapi forward masih kosong dan `operations.calls` = 0.
- Uji workflow manual #3 pada 5 November 2026 gagal: deployment yang dipanggil belum memuat `CRON_SECRET` (HTTP 503). Secret sudah ditambahkan ke Vercel Production dan GitHub Actions. Redeploy perlu dilakukan setelah variabel tersedia, lalu workflow harus diuji ulang; belum ada tick maupun log forward yang berhasil.
- Deployment aktif saat dokumentasi ini diperbarui: commit `855b3bc0b8f0b3d0a19f76b908153234a42bee5e`. Perubahan ini adalah perbaikan konfigurasi setelah batas freeze, bukan bukti freeze tepat waktu.
- Satu jam Indodax diidentifikasi oleh waktu buka candle UTC. Panggilan pertama setelah 05.00 UTC memproses candle 04.00 UTC yang baru tertutup.
- Setelah freeze, jangan ubah strategi, parameter, atau universe. Perbaikan bug non-strategi perlu dicatat dan di-commit tanpa menulis ulang riwayat.
- Commit hash, waktu commit, link repo publik, link deployment, dan refleksi final harus ditambahkan setelah bukti tersebut benar-benar ada. Tidak ada hash, URL, atau hasil deploy palsu dalam repo ini.




## Aturan strategi




Lihat [strategy.md](strategy.md). Prinsip UTS Momentum Basket dipertahankan: momentum multi-horizon, filter SMA pendek/panjang, long-only, basket terbatas, cash sebagai penyangga, serta pembatasan likuiditas. Untuk kripto 1 jam, periode UTS saham (12/3 bulan dan rebalance 21 hari) diganti dengan momentum 24 jam/7 hari dan evaluasi candle per jam. Perubahan ini harus selesai dan dibekukan sebelum forward test.


## Pembaruan operasional (5 November 2026)

Deployment Production terbaru berstatus Ready setelah CRON_SECRET ditambahkan ke Vercel dan trigger deployment baru. Tick manual GitHub Actions run #4 berhasil; /api/metrics mencatat 1 panggilan, 1 candle diproses, 0 error API, 5 sinyal, 0 trade, dan equity tetap Rp100.000.000. Angka ini hanya menggambarkan tick tersebut, bukan forward test lengkap; 239 candle terjadwal belum diproses dan tidak ada trade yang diisi. Baris status sebelumnya yang menyatakan belum ada tick menggambarkan keadaan sebelum run #4.
