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
- Deployment Vercel/Upstash dan forward tick/log live belum tersedia. Jangan menganggap metrik forward kosong sebagai hasil test.
- Satu jam Indodax diidentifikasi oleh waktu buka candle UTC. Panggilan pertama setelah 05.00 UTC memproses candle 04.00 UTC yang baru tertutup.
- Setelah freeze, jangan ubah strategi, parameter, atau universe. Perbaikan bug non-strategi perlu dicatat dan di-commit tanpa menulis ulang riwayat.
- Commit hash, waktu commit, link repo publik, link deployment, dan refleksi final harus ditambahkan setelah bukti tersebut benar-benar ada. Tidak ada hash, URL, atau hasil deploy palsu dalam repo ini.

## Aturan strategi

Lihat [strategy.md](strategy.md). Prinsip UTS Momentum Basket dipertahankan: momentum multi-horizon, filter SMA pendek/panjang, long-only, basket terbatas, cash sebagai penyangga, serta pembatasan likuiditas. Untuk kripto 1 jam, periode UTS saham (12/3 bulan dan rebalance 21 hari) diganti dengan momentum 24 jam/7 hari dan evaluasi candle per jam. Perubahan ini harus selesai dan dibekukan sebelum forward test.

Universe kandidat tetap terdiri atas BTCIDR, ETHIDR, BNBIDR, SOLIDR, XRPIDR, ADAIDR, DOGEIDR, dan LINKIDR. Script memilih lima pair berdasarkan turnover quote pada 30 hari pertama periode seleksi; periode itu dikeluarkan dari backtest. Daftar hasil seleksi disimpan di `data/universe.json` dan harus di-commit serta disalin persis ke `BOT_UNIVERSE` sebelum freeze. Semua delapan kandidat harus memiliki riwayat lengkap; script berhenti jika tidak.

## Siapkan backtest 3 tahun dan snapshot

Gunakan Python 3.10+ pada komputer yang dapat mengakses HTTPS:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python scripts\download_history.py --start 2023-10-04T00:00:00Z
python scripts\snapshot_orderbooks.py
```

`download_history.py` mengambil candle berurutan mundur karena satu respons 1 jam dibatasi sekitar 650 bar. Permintaan seri dan dijeda sekitar 0,36 detik; jangan menjalankannya paralel. CSV/manifest hanya berasal dari respons Indodax. Pastikan manifest benar-benar mencakup sekurangnya tiga tahun dan semua candle/volume wajar.

`--start` adalah awal periode seleksi likuiditas 30 hari, bukan awal backtest. Unduh rentang minimal tiga tahun ditambah 30 hari sebelum freeze; cocokkan tanggalnya dengan waktu pengumpulan aktual. Backtest tanpa argumen `--start` menggunakan `backtest_start_utc` dari manifest, yaitu setelah periode seleksi.

Sebelum freeze, kumpulkan snapshot tiap pair tiap jam (sekurangnya 3× sehari) dengan menjalankan `scripts/snapshot_orderbooks.py`. Backtest mengukur median spread dan market impact order Rp15 juta dari snapshot pra-forward yang berhasil mengisi setidaknya 99,9% kuantitas pada kedua sisi. Ia **berhenti dengan error jika tidak ada snapshot penuh untuk pair aktif**, bukan menebak impact atau menganggap order yang tak terisi sebagai fill penuh. Kalibrasi untuk backtest historis dan pembanding forward dibekukan sebelum forward; dashboard mengukur benchmark forward dari snapshot forward yang benar-benar cukup dalam.

Jika persiapan snapshot terlewat, jangan mengubah waktu snapshot atau menyebut hasilnya sebagai backtest sesuai prosedur freeze. Untuk analisis eksploratif saja, `--calibration-cutoff <UTC>` bersama `--allow-late-calibration` mencatat kalibrasi terlambat sebagai `late_after_forward_start_non_compliant`; hasil tersebut tidak membuktikan kepatuhan terhadap freeze.

Jalankan backtest (waktu akhir default berasal dari waktu server Indodax):

```powershell
python scripts\backtest.py
```

Data sumber ada di `data/historical/`, `data/pairs.json`, `data/download_manifest.json`; hasil yang dihitung ulang ada di `data/backtest_summary.json` dan `data/backtest_*.jsonl`. Simpan sumber data dan manifest tersebut dalam ZIP pengumpulan agar hasil dapat diverifikasi.

Setelah 10 hari selesai, hitung pembanding dengan sinyal yang sama pada candle window yang sama:

```powershell
python scripts\backtest.py --forward-start 2026-11-04T04:00:00Z `
  --forward-end 2026-11-14T04:00:00Z
```

Argumen forward memakai waktu buka candle UTC: interval 04.00–05.00 UTC adalah candle pertama yang tertutup pada awal forward test 05.00 UTC.

## Storage, secret, dan deployment Vercel

1. Buat database Upstash Redis melalui Vercel Marketplace dan catat REST URL/token. Buat `CRON_SECRET` acak panjang (minimal 32 karakter).
2. Deploy repo ini ke Vercel (Python serverless functions). Tambahkan `CRON_SECRET`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `BOT_UNIVERSE`, `BUY_TAKER_FEE_FLOOR`, dan `SELL_TAKER_FEE_FLOOR` di Vercel Project Environment Variables. Isi `BOT_UNIVERSE` dengan lima pair terpilih dari `data/universe.json`. Jangan masukkan secret ke repo/ZIP; `.env.example` hanya berisi nama konfigurasi.
3. Hubungkan repo yang sama ke GitHub Actions. Tambahkan repository secrets:
   - `VERCEL_BOT_URL` = origin deployment Vercel, tanpa `/` di akhir.
   - `CRON_SECRET` = nilai yang sama dengan env Vercel.
4. Aktifkan workflow `.github/workflows/hourly.yml` di branch default. Jadwal `7 * * * *` adalah UTC, bukan WIB. GitHub Actions dapat terlambat; log waktu aktual menjadi dasar uptime.
5. Uji koneksi publik: buka `https://<deployment>/api/health`. Respons harus menunjukkan `status: ok` dan seluruh pair tersedia.
6. Sebelum freeze, lakukan satu pemanggilan terautentikasi `/api/tick` untuk mengumpulkan snapshot/preflight. Sebelum waktu forward, bot hanya mencatat sinyal/snapshot dan **tidak** mengirim order simulasi.
7. Kill switch tanpa redeploy:

```powershell
Invoke-RestMethod -Method Post -Uri "$env:VERCEL_BOT_URL/api/control" `
  -Headers @{ Authorization = "Bearer $env:CRON_SECRET" } `
  -ContentType "application/json" -Body '{"kill_switch":true}'
```

Kirim `false` untuk menonaktifkannya. Kedua perubahan dicatat di Redis. Endpoint tick/control menolak request tanpa bearer secret.

Vercel filesystem bukan penyimpanan state. Bot menolak berjalan tanpa konfigurasi Redis; ia tidak memakai file sementara sebagai fallback state.

## Log, export, dan dashboard

`/api/metrics` melayani panel web di [index.html](index.html). Setelah forward test, ekspor semua log Redis ke JSONL lokal dengan env Redis yang sudah diset:

```powershell
python scripts\export_logs.py
python scripts\recompute_dashboard.py
```

File mentah disimpan per jenis di `logs/raw/` (calls, candles, controls, equity, errors, orders, signals, snapshots, trades). `dashboard/offline_dashboard.html` dihitung ulang dari log mentah dan summary backtest; buka langsung tanpa internet. Periksa bahwa nilai dashboard sama dengan keluaran skrip. Log order book menyertakan respons mentah untuk audit.

## Fee dan eksekusi

- Indodax publik `/api/pairs` saat data diambil melaporkan `trade_fee_percent_taker`; kode membandingkannya dengan fee floor resmi terpisah untuk buy dan sell.
- `/api/pairs` pada 3 November 2026 melaporkan taker service fee 0,20%. Artikel resmi all-in yang diperbarui 1 November 2026 menunjukkan taker IDR **buy 0,20555%** dan **sell 0,41555%**. Kode membandingkan nilai API dengan fee floor resmi secara terpisah per sisi dan menggunakan yang lebih tinggi. Sumber: [API pairs](https://indodax.com/api/pairs) dan [rincian biaya resmi](https://help.indodax.com/hc/id/articles/4416646599705-Rincian-Biaya-Transaksi-di-INDODAX), diakses 3 November 2026.
- Minimum order simulasi Rp25.000. Kuantitas dibulatkan turun menggunakan `quantity_increment` resmi pasangan.
- Fill live mengonsumsi level order book; buy di ask, sell di bid. Backtest OHLC mengestimasi sisi bid/ask dan market impact menggunakan median snapshot aktual. Harga mid/close tidak dipakai sebagai fill live.

## Keamanan dan pemeriksaan

- Hanya endpoint publik Indodax dipanggil. Tidak ada key Indodax.
- Rahasia hanya di environment Vercel/GitHub; jangan commit `.env`, token, atau URL berisi kredensial.
- Fungsi sinyal yang sama dipakai bot dan simulator.
- Retry jaringan dibatasi tiga kali; error/data invalid dicatat dan pair tidak diperdagangkan.
- Tiap candle hanya diproses sekali per pair; daily loss limit WIB 2%, maksimum tiga posisi dan 15% equity per posisi.
- Jalankan tes lokal: `python -m unittest discover -s tests -v`.

## Refleksi akhir

Isi `reflection.md` setelah forward selesai memakai angka yang dihasilkan dari log dan backtest 10 hari. Bandingkan candle sinyal, waktu panggilan, spread, impact, fee, missed/late candles, error, serta gap return. Jangan mengarang sebab atau angka sebelum data tersedia.


## Status operasional (4 November 2026, 22.30 WIB)

Workflow hourly sudah tersimpan di commit 815b977. Uji dispatch berhasil, tetapi tick dilewati karena secrets GitHub belum diatur; belum ada tick maupun log forward. /api/health merespons status ok, sedangkan /api/metrics masih HTTP 503 karena kredensial Upstash belum dikonfigurasi. Forward test 10 hari sesuai jadwal tidak dapat dipenuhi jika baru dimulai setelah 4 November 2026 pukul 12.00 WIB.
