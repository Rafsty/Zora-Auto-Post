# Cek - Batch Screenshot Coin Zora

`fullpage_screenshot.py` adalah utilitas Python yang memanfaatkan Playwright untuk mengambil screenshot penuh halaman coin Zora (`https://zora.co/coin/base:{contract}`) secara massal. Daftar contract diambil dari `ca.txt`, sehingga Anda bisa mengotomatisasi dokumentasi kampanye atau audit tanpa membuka halaman satu per satu.

## Isi Folder
- `fullpage_screenshot.py` - skrip utama yang memuat parser input dan logika pengambilan screenshot.
- `ca.txt` - contoh daftar email|ticker|contract; baris bertanda `-` pada kolom contract otomatis dilewati.
- `screenshots/` - direktori keluaran; akan dibuat otomatis bila belum ada.

## Fitur Utama
- Validasi format `email|ticker|contract` beserta dukungan komentar diawali `#`.
- Sanitasi nama file agar aman untuk semua sistem operasi dan menyertakan nomor urut (`001_TICKER.png`).
- Parameter CLI untuk viewport, timeout, dan jeda setelah halaman dimuat, sehingga mudah di-tune sesuai kecepatan jaringan.
- Penanganan error eksplisit (mis. contract kosong, halaman timeout) agar mudah menindaklanjuti.

## Prasyarat
- Python 3.10+ (disarankan menggunakan virtual environment terpisah).
- Paket Python: `playwright`.
- Browser Playwright Chromium (diinstal lewat `playwright install chromium`).
- Akses internet untuk memuat halaman Zora.

## Instalasi Cepat
1. `cd cek`
2. `python -m venv .venv`
3. `.venv\Scripts\activate` (Windows) atau `source .venv/bin/activate` (macOS/Linux).
4. `pip install --upgrade pip playwright`
5. `playwright install chromium`

## Format `ca.txt`
Setiap baris wajib mengikuti pola `email|ticker|contract`. Baris kosong, baris komentar (`# ...`), atau contract yang kosong/bernilai `-` akan otomatis di-skip.

```
ip7lags7fx@dollicons.com|IRANVSISRAEL 1|0x8684eb2709106ab0f8f4b4f9d6ffc53270335845
c44o610oxk@dollicons.com|IRANVSISRAEL 1|0xe6d90d8b0efefaa195eb3aa3d41a6de8a320e4aa
# Contoh baris yang akan dilewati karena contract kosong
6qghl71g7s@dollicons.com|IRANVSISRAEL 1|-
```

Tips:
- Gunakan ticker pendek agar nama file tidak terlalu panjang; skrip akan mengganti karakter non-alfanumerik dengan `_`.
- Anda bisa memecah daftar besar menjadi beberapa file input dan menjalankan skrip terpisah bila ingin paralel.

## Cara Menjalankan
Jalankan perintah berikut dari dalam folder `cek` (virtual environment opsional tetapi disarankan):

```powershell
python fullpage_screenshot.py `
  --input ca.txt `
  --output-dir screenshots `
  --viewport 1366x768 `
  --timeout 45000 `
  --wait-after-load 7000
```

Tanpa argumen tambahan, skrip otomatis membaca `ca.txt`, menulis ke `screenshots/`, menggunakan viewport `1280x720`, timeout 30000 ms, dan jeda 5000 ms.

## Parameter CLI
| Flag | Default | Keterangan |
| --- | --- | --- |
| `--input` | `ca.txt` | Jalur file sumber daftar contract. |
| `--output-dir` | `screenshots` | Folder tujuan penyimpanan PNG. Dibuat otomatis bila belum ada. |
| `--viewport` | `1280x720` | Ukuran viewport `WIDTHxHEIGHT`. Gunakan resolusi lebih tinggi bila ingin detail tambahan. |
| `--timeout` | `30000` | Batas waktu (ms) menunggu halaman Zora selesai dimuat (`networkidle`). |
| `--wait-after-load` | `5000` | Jeda ekstra (ms) sebelum screenshot; berguna bila halaman punya animasi atau data lambat. |

## Output
- Setiap contract valid menghasilkan file PNG full-page di folder output.
- Nama file mengikuti pola `NNN_<ticker>.png` sehingga urutan input tetap terlihat.
- Jika halaman gagal dimuat, Playwright mengangkat `PlaywrightTimeoutError` dan proses berhenti; perbaiki koneksi atau tingkatkan `--timeout`.

## Troubleshooting
- **`Halaman tidak selesai dimuat`**: tingkatkan `--timeout` dan `--wait-after-load`, pastikan koneksi stabil, dan coba ulangi daftar yang gagal.
- **`File input tidak ditemukan`**: pastikan menjalankan skrip dari folder yang benar atau gunakan jalur absolut lewat `--input`.
- **`python: command not found`**: gunakan `py` di Windows (`py fullpage_screenshot.py`) atau pastikan virtual environment aktif.

## Pengembangan
- Script hanya bergantung pada Playwright; jika ingin menambah fitur (misal menyimpan log CSV), gunakan fungsi `parse_lines` dan `take_screenshots` yang sudah modular.
- Tambahkan pengujian cepat dengan menjalankan `python -m compileall fullpage_screenshot.py` untuk memastikan tidak ada error sintaks sebelum push.
