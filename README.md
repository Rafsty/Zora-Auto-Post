## Prasyarat Umum
1. **Python 3.10+** (disarankan via virtual environment).
2. Paket Python: `playwright`, `requests`, `faker`, `colorama` (plus dependensi standar).
3. Browser Playwright Chromium (`playwright install chromium`).
4. Akses internet, serta akun/proxy sesuai kebutuhan skrip.
5. Folder `avatars/` berisi gambar `.png/.jpg/.webp` untuk unggah profil.

Contoh setup cepat:
```powershell
cd C:\Users\AXIOO\Zora
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip playwright requests faker colorama
playwright install chromium
```

## Struktur Direktori Singkat
- `post.py` - otomasi posting coin/token Zora banyak akun + ekspor cookies.
- `regist.py` - generator akun baru berbasis Mail.tm dengan dukungan proxy list/sistem/manual.
- `pw.py` - versi ringan pembuatan akun tanpa pengaturan proxy rumit; cocok untuk batch kecil.
- `mc.py` - demo otomatisasi login dan aksi dasar (OTP, Start trading, buka chat) untuk satu akun list.
- `mailtm.py` - helper API Mail.tm (buat akun, login, baca OTP) yang dipakai skrip lain.
- `mail.txt` / `Mail.txt` - penyimpanan daftar `email|password` (case berbeda tapi di Windows dianggap sama).
- `info.txt` - override judul/ticker awal untuk `post.py` (format `key=value`).
- `info_post.txt` - log hasil posting (`email|ticker|contract`).
- `proxies.txt` - daftar proxy `ip:port` atau `ip:port:user:pass` untuk `regist.py`.
- `avatars/` - stok avatar yang dipilih acak saat registrasi.
- `cek/` - utilitas screenshot massal coin (lihat `cek/README.md` untuk detail lengkap).

## Penjelasan Skrip Utama
### `post.py`
Otomatisasi lengkap proses pembuatan coin/token di zora.co untuk banyak akun:
- Membaca daftar akun dari `mail.txt` (bisa batasi via `--start-index` dan `--max-accounts`).
- Mendukung login-only (ekspor cookies ke JSON) atau lanjut sampai token terbit.
- Bisa upload gambar (`--image`) atau memakai mode generate otomatis.
- Mengambil OTP dari Mail.tm via API, auto-fill form, menangani popup, klik tombol `View post`, dan mengekstrak contract address.
- Mencatat hasil ke `info_post.txt` serta menyimpan cookies (`--cookies-out`).
- Mengambil override `ticker`/`title`/`ticker_group_start` dari `info.txt` dan prompt interaktif awal.

Contoh penggunaan:
```powershell
python post.py `
  --mail-file mail.txt `
  --cookies-out cookies.json `
  --image elite.png `
  --title "ELITE GLOBAL" `
  --ticker "ELITE GLOBAL" `
  --max-accounts 3
```
Tip: Jika ingin nama file cookies per akun, cukup beri `--cookies-out cookies.json` sehingga skrip otomatis menambahkan suffix `_1`, `_2`, dst.

### `regist.py`
Generator akun asinkron dengan fleksibilitas proxy:
- Menanyakan jumlah akun, sumber proxy (list `proxies.txt`, proxy sistem Windows, atau input manual), dan mengatur Mail.tm agar mengikuti proxy yang sama.
- Memakai Playwright headless untuk membuka URL undangan (`INVITE_URL`), login via email, menangkap OTP Mail.tm, upload avatar acak, generate username unik, mengisi display name, menyelesaikan proses `Create account -> Finish -> Activate`.
- Menyimpan setiap pasangan `email|password` ke `Mail.txt` agar dapat digunakan `post.py`/`mc.py`.
- Bila menggunakan proxy list, setiap akun membuka instance browser baru dengan proxy berbeda; fallback otomatis jika sebuah proxy gagal mengambil domain Mail.tm.

Jalankan:
```powershell
python regist.py
```
Ikuti prompt untuk memilih sumber proxy (y/n) dan jumlah akun.

### `pw.py`
Varian lebih sederhana bila tidak butuh pengaturan proxy:
- Selalu menggunakan Chromium non-headless agar mudah dipantau.
- Membuat email Mail.tm baru, menangkap OTP, upload avatar acak, memvalidasi username, dan menyimpan akun ke `Mail.txt`.
- Cocok untuk pengecekan manual atau batch kecil sebelum menjalankan `regist.py`.

### `mc.py`
Skrip "macro" satu akun untuk memverifikasi alur login:
- Mengambil akun pertama dari `mail.txt`, login via OTP, klik tombol `Start trading`, membuka profil dan chat.
- Dapat membantu debugging perubahan UI karena menjalankan langkah demi langkah dengan log jelas dan `expect()`.

### `mailtm.py`
Library kecil agar kode lain tidak perlu mengulang logika Mail.tm:
- `get_available_domains()`, `create_random_mailtm_account()`, `login_mailtm()`, `check_inbox_mailtm()`.
- `set_mailtm_proxy()` memungkinkan `regist.py` mengganti proxy Requests agar konsisten dengan Playwright.

### `cek/`
Berisi utilitas `fullpage_screenshot.py` plus `ca.txt` dan `screenshots/`. README khusus sudah ada di `cek/README.md` (bahasa Indonesia) sehingga folder ini siap dipush sebagai bukti visual setiap contract.

## File Konfigurasi dan Data
- `mail.txt` / `Mail.txt`: satu email per baris, format `email|password`. Pastikan huruf kecil/besar konsisten jika repo dijalankan di Linux/macOS.
- `info.txt`: isi opsi seperti `title=ELITE GLOBAL`, `ticker=ELITE GLOBAL`, `ticker_group_start=2` untuk override default `post.py`.
- `info_post.txt`: output otomatis, jangan dihapus jika ingin riwayat contract.
- `proxies.txt`: gunakan format `ip:port:user:pass` atau `http://user:pass@host:port`. Baris `#` diabaikan.
- `avatars/`: letakkan beberapa avatar agar `regist.py`/`pw.py` bisa memilih acak.

## Alur Kerja yang Disarankan
1. Generate akun - pakai `regist.py` (dengan proxy) atau `pw.py` (tanpa proxy) sampai `Mail.txt` terisi.
2. Posting coin/token - jalankan `post.py` menggunakan daftar pada `mail.txt`. Jangan lupa siapkan `info.txt`, gambar, dan folder output cookies.
3. Dokumentasi - pindah ke folder `cek/` dan jalankan `python fullpage_screenshot.py --input ca.txt` untuk mengambil screenshot tiap contract (sesuaikan `ca.txt` dari `info_post.txt`).
4. Validasi manual - gunakan `mc.py` jika ingin memastikan flow login masih sesuai setelah ada perubahan UI Zora.

Dengan README ini seluruh skrip di root maupun di `cek/` sudah terdokumentasi dalam Bahasa Indonesia dan siap dipublikasikan di GitHub.
