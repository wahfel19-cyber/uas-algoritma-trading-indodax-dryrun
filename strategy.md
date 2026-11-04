# Strategi dan aturan freeze

## Hubungan dengan strategi UTS

Strategi UTS adalah **Momentum Basket** untuk saham Kompas100: ranking momentum 12 bulan, konfirmasi 3 bulan positif, SMA20 > SMA50, rebalance 21 hari, pilih tiga saham, alokasikan total 90% sama rata dan simpan 10% kas. UTS memakai data hari sebelumnya, batas order 5% nilai transaksi rata-rata 20 hari, lot 100, fee beli/jual, serta spread.

Kripto Indodax tidak memiliki lot saham, volume/risk berbeda, dan forward test hanya 10 hari. Adaptasi yang ditetapkan sebelum freeze:

- Pertahankan pendekatan momentum multi-horizon, SMA20/SMA50, basket maksimum tiga posisi, long-only, dan modal tidak seluruhnya dipakai.
- Ganti horizon saham 12/3 bulan dengan momentum 24 jam dan 7 hari pada candle 1 jam. Ganti rebalance 21 hari dengan evaluasi setiap candle tertutup supaya forward window menghasilkan pengamatan yang cukup.
- Eksekusi buy/sell memakai order book, fee taker, ukuran minimum, pembulatan kuantitas dan limit risk, bukan harga penutupan sebagai fill.
- Universe saham Kompas100 diganti dengan delapan kandidat pair IDR tetap di bawah. Lima pair dipilih berdasarkan turnover quote pada 30 hari pertama periode seleksi; periode seleksi dikeluarkan dari backtest. Snapshot order book dipakai untuk menguji likuiditas, bukan return pada seluruh sampel.

Catat versi/parameter UTS sumber di ZIP sebagai bukti jika ada dokumen tambahan; dashboard UTS yang tersedia menunjukkan aturan di atas. Perubahan strategi ini harus dibekukan di commit sebelum 4 November 2026 pukul 12.00 WIB.

## Parameter yang dibekukan

| Parameter | Nilai |
|---|---:|
| Kandidat universe tetap | BTCIDR, ETHIDR, BNBIDR, SOLIDR, XRPIDR, ADAIDR, DOGEIDR, LINKIDR |
| Universe aktif | Top 5 kandidat menurut turnover quote pada 30 hari awal seleksi; disimpan di `data/universe.json` sebelum freeze |
| Timeframe | 1 jam (Indodax `tf=60`) |
| Sinyal | Hanya candle tertutup; jendela indikator harus berurutan dan valid |
| Momentum pendek | Close terakhir / close 24 candle lalu − 1 > 1,5% |
| Momentum panjang | Close terakhir / close 168 candle lalu − 1 > 4% |
| Filter trend | Close > SMA20 dan SMA20 > SMA50 |
| Ranking entry | momentum 24 jam + momentum 7 hari, urut menurun; tie-break alfabetis |
| Exit | close < SMA20 atau momentum 24 jam < 0 |
| Modal virtual | Rp100.000.000 |
| Arah | Long-only; tanpa short, margin, atau leverage |
| Maksimum posisi | 3 |
| Batas ukuran posisi | 15% equity saat entry |
| Daily loss limit | 2% dari equity awal hari WIB; hentikan entry sampai hari WIB berikutnya |
| Minimum order | Rp25.000 atau ketentuan resmi lebih ketat |
| Fee buy taker | `max(/api/pairs taker, fee resmi all-in)`; floor 0,20555% |
| Fee sell taker | `max(/api/pairs taker, fee resmi all-in)`; floor 0,41555% |
| Batas spread untuk entry/exit | Skip pasangan jika spread > 2% |
| Kill switch | Redis state melalui `/api/control`, tanpa redeploy |

Pada 3 November 2026, `/api/pairs` melaporkan `trade_fee_percent_taker=0.2` (0,20%) untuk pair IDR yang diperiksa. Artikel resmi yang diperbarui 1 November 2026 menunjukkan all-in taker IDR buy 0,20555% dan sell 0,41555%. Kode memakai maksimum dari data API dan floor resmi sesuai sisi transaksi. URL sumber dan tanggal akses dicatat di README. Hash commit freeze dan waktu commit harus diisi dari riwayat commit yang nyata sebelum forward test.

## Validasi data dan execution

Setiap eksekusi memeriksa candle terakhir tidak lebih lama dari 2× timeframe, minimal 169 candle indikator berurutan, OHLC dan volume positif, order book tidak kosong, serta spread maksimal 2%. Jika gagal, pair itu tidak membuat order dan alasan tercatat.

Sinyal dihitung dari candle tertutup terakhir. Bot mencatat best bid/ask, kuantitas, rata-rata fill berlapis, fee, spread dan market-impact estimasi, waktu sinyal, serta selisih fill terhadap close sinyal. Backtest memakai median spread dan market impact dari snapshot order book nyata yang diukur pada persiapan/forward test. Tidak menggunakan data sintetis.

## Universe dan survivorship

Daftar kandidat ditetapkan di muka dan jumlahnya delapan. Lima pair aktif dipilih berdasarkan turnover total pada 30 hari awal; jendela tersebut dikecualikan dari tiga tahun test. `data/universe.json` dan manifest membuktikan hasil seleksi dan harus dibekukan sebelum forward test. Pasangan yang tidak memiliki data penuh selama periode minimum tidak boleh diam-diam dimasukkan sebagai data lengkap; hentikan pengujian atau dokumentasikan keterbatasan data sebelum freeze. Jangan memilih pair berdasarkan return periode backtest.

Simulator menunggu sinyal candle tertutup lalu mengeksekusi pada open candle berikutnya dengan spread, impact, dan fee terukur. Harga close candle sinyal tidak pernah dipakai sebagai harga fill.

## Waktu dan bukti freeze

- Persiapan: 2 November sampai 4 November 2026 pukul 12.00 WIB.
- Freeze wajib: commit sebelum/tepat 4 November 2026 pukul 12.00 WIB.
- Forward test: 4 November pukul 12.00 WIB sampai 14 November pukul 12.00 WIB WIB.
- Jendela candle UTC untuk perbandingan: 4 November pukul 04.00 UTC sampai 14 November pukul 04.00 UTC (waktu buka candle 1 jam).

Tambahkan hash dan waktu commit nyata setelah commit dibuat. Setelah freeze, jangan ubah aturan, parameter, atau universe. Bugfix non-strategi saja yang boleh dilakukan, dengan catatan eksplisit.
