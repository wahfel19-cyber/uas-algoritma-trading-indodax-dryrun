# Indodax dry-run bot — UAS Algorithmic Trading

## Paket pengumpulan

Unduh [ZIP ringkas terbaru dengan folder `.git` dan riwayat commit](./indodax-dryrun-bot-uas-submission-compact-with-git.zip). Paket memuat source, data candle, snapshot order book, hasil backtest, skrip, dashboard offline, refleksi sementara, `.env.example`, dan riwayat Git.

Untuk menjaga ukuran unggahan, checkout ZIP ini tidak menyertakan file turunan besar `data/backtest_signals.jsonl`. File tersebut masih ada dalam riwayat Git sebelum commit pengemasan dan dapat diregenerasi dengan skrip backtest. ZIP lokal lengkap yang juga menyertakan file tersebut tersedia terpisah.

## Status dan integritas

- Freeze wajib 4 November 2026 pukul 12.00 WIB terlewat. Commit pertama proyek dibuat 4 November pukul 17.41 WIB; riwayat Git tidak membuktikan freeze tepat waktu.
- Backtest historis tersedia dari candle publik Indodax, tetapi kalibrasi order book hanya menggunakan satu snapshot per pair yang direkam setelah forward dimulai. Backtest tersebut berlabel eksploratif/non-compliant, bukan hasil yang memenuhi prosedur freeze.
- Hasil eksploratif: return -51,50%, maximum drawdown 57,31%, 1.225 transaksi. Jangan menyajikannya sebagai hasil patuh UAS.
- Hingga 4 November 2026, bot belum dideploy ke Vercel/Upstash dan belum menghasilkan log forward. Forward test 10 hari belum selesai; metrik forward tidak tersedia.
- Jangan mengklaim deployment, freeze tepat waktu, atau hasil forward yang belum dibuktikan. Tidak ada secret/API key dalam repo; bot hanya untuk order simulasi.
