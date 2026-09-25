---
name: Kppics CDN Extractor
description: Ubah kpopping.com/kpics URL menjadi photo_collection gallery satu langkah full pipeline — scrape CDN, update JSON, download aset WebP, rewrite ke GitHub Pages.
---

# Kpics CDN Extractor

Gunakan skill ini setiap ada permintaan "ubah url kpopping menjadi list CDN", "isi photo_collection", atau "@kpics-cdn-extractor <url> <app>".

Default adalah satu langkah full pipeline: scrape CDN → update `*-content.json` → download aset `--to-webp` → rewrite ke GitHub Pages. Tidak ada tahap terpisah kecuali user eksplisit meminta opt-out (`cdn-only` / `tanpa download` / `tanpa webp`).

## Input

Satu atau banyak URL bentuk:

`https://kpopping.com/kpics/<slug>`

URL bisa ditempel di chat, atau disimpan sebagai file teks satu URL per baris (mis. `/tmp/urls.txt`).
Petunjuk app target bisa berupa nama app, api_dir, atau bagian perintah user (mis. `CORTIS`, `cortis`, `cortis-api`, `BTS - ARMY`, `bts`, `BLACKPINK`).

## Title otomatis

`title` diambil dari data halaman/API, prioritas:

1. `title` dari endpoint JSON resmi `/api/photos?slug=<slug>` (dipakai halaman Kpopping sendiri)
2. `<h1>` dari HTML halaman (mis. `CORTIS 2026 Lollapalooza Photo Sketch`)
3. `og:title`
4. `<title>` (dibersihkan dari suffix `HQ Photos`/`Photos` dan prefix `ARTIST —`)
5. Fallback: slug humanize (`cortis-2026-lollapalooza-photo-sketch` → `Cortis 2026 Lollapalooza Photo Sketch`)

Jangan menebak title di luar urutan itu. Saat update entry lama, pertahankan title kurasi manual kecuali user meminta `--update-title`.

## Mapping file via constanta.json

1. Baca `constanta.json` di repo root untuk mapping `app_name -> api_dir`.
   Contoh: `CORTIS -> cortis-api`, `BTS - ARMY -> bts-api`.
2. Cocokkan petunjuk user case-insensitive sebagai substring terhadap `app_name` ATAU `api_dir`.
   Contoh: `cortis`, `CORTIS`, `cortis-api` → `cortis-api`; `bts` → `bts-api`; `blackpink` → `blackpink-api`.
3. Jika `APP NAME` tidak ada di `constanta.json` tapi direktori `<slug>-api` ada (mis. `ENHYPEN` → `enhypen-api`), tetap pakai direktori tersebut dan laporkan sebagai fallback.
4. File target: `<api_dir>/*-content.json` pertama yang cocok, field `gallery`.

## Aturan (wajib)

1. Jangan pakai `webfetch` untuk halaman kpopping — endpoint HTML sering mendapat challenge Cloudflare 403. Skrip memakai `curl`; untuk `/kpics/<slug>` coba API JSON resmi terlebih dahulu, baru HTML sebagai fallback.
2. Jangan menebak URL CDN — gunakan hanya `albumImages[].src` dari `/api/photos` atau structured `initialData.albumImages[].src` di HTML. Jangan memindai semua URL `/kpics/` di HTML karena dapat mencakup foto related/galeri lain. Endpoint API adalah sumber resmi yang dipanggil bundle halaman Kpopping.
3. Dedup + sort. Abaikan `static/`, `avatar`, `graph`.
4. Format aset yang didukung pipeline saat ini hanya JPEG (`.jpg`/`.jpeg`). Record PNG/WebP ditolak fail-closed sampai downloader mendukung konversi/path-nya; jangan mutate gallery dengan album campuran yang tidak tervalidasi.
5. Jika API dan HTML fallback sama-sama diblokir Cloudflare (`Just a moment...` dan kecil <20KB), tandai `blocked`, jangan keluarkan list kosong seolah lengkap. Jangan timpa `photo_collection` lama dengan hasil blocked/kosong.
6. Jangan hapus `api_url` di `*-content.json` kecuali user eksplisit meminta format `{title, photo_collection}` tanpa `api_url` (pakai `--drop-api-url` hanya atas otorisasi itu).
7. Langsung full pipeline tanpa bertanya konfirmasi bila URL + petunjuk app sudah diberikan: scrape → update `photo_collection` → download aset `--to-webp` → rewrite ke GitHub Pages. Default `rewrite-base`: `https://fandomkpopuk-bot.github.io`. Lewati download hanya bila user eksplisit meminta opt-out (`cdn-only` / `tanpa download` / `tanpa webp`). Jangan `git commit` — hanya ubah working tree, commit biar user yang lakukan.
8. Tulis JSON dengan `ensure_ascii=False, indent=2`. Validasi dengan `python3 -m json.tool`.
9. Bila endpoint API tidak tersedia, atau HTML fallback diblokir: pakai `--html-file` (HTML/MHTML simpanan browser, tanpa fetch jaringan). Bila download CDN diblokir, pakai `--cookies` (cookies.txt ekspor browser). Sumber tetap HTML/cookie asli, bukan tebakan.

## Workflow

Bila user memberi URL + petunjuk app (mis. `@kpics-cdn-extractor <url> cortis`), LANGSUNG full pipeline — tanpa bertanya dulu, tanpa `git commit`:

```sh
# Buat /tmp/urls.txt dengan file-writer/editor (satu URL per baris).
# Jangan interpolasi URL chat langsung ke echo/printf shell.
python3 .opencode/skills/kpics-cdn-extractor/scripts/extract_kpics.py --app CORTIS --apply --input /tmp/urls.txt --output /tmp/cdn.json --delay 2 &&
python3 .opencode/skills/kpics-cdn-extractor/scripts/download_assets.py --app CORTIS --to-webp --rewrite-base https://fandomkpopuk-bot.github.io --delay 0.5 &&
python3 -m json.tool <api_dir>/<slug>-content.json > /dev/null && echo "JSON OK"
```

Hanya berhenti untuk konfirmasi bila: hasil `blocked`, `empty`, match ambigu (dilaporkan script), atau app tidak ketemu di `constanta.json` maupun fallback direktori. `blocked` mencakup input URL invalid, HTTP/curl gagal, atau Cloudflare; `empty` berarti response valid tanpa foto. **Jangan lanjut ke download bila extractor exit 1** (agar tidak menimpa data lama). Opt-out: bila user menulis `cdn-only` / `tanpa download` / `tanpa webp`, berhenti setelah langkah `extract_kpics.py`.

Scrape saja tanpa tulis (bila user hanya minta list, tanpa petunjuk app):

```sh
python3 .opencode/skills/kpics-cdn-extractor/scripts/extract_kpics.py --input /tmp/urls.txt --output /tmp/cdn.json --delay 2
```

Untuk satu URL cepat:

```sh
python3 .opencode/skills/kpics-cdn-extractor/scripts/extract_kpics.py "https://kpopping.com/kpics/<slug>"
```

Output: `{"items": {url: {"title": ..., "photos": [...]}}, "photos": {...}, "blocked": [...], "empty": [...]}`. `blocked` berarti fetch gagal/Cloudflare; `empty` berarti HTML/API valid tetapi tidak menghasilkan URL foto. Keduanya tidak boleh diterapkan ke gallery.
2. Langsung terapkan ke gallery (mapping otomatis via `constanta.json`):
   ```sh
   python3 .opencode/skills/kpics-cdn-extractor/scripts/extract_kpics.py --app CORTIS --apply --input /tmp/urls.txt --delay 2
   ```
   Matching idempotent: (1) `api_url` persis, (2) title persis ternormalisasi, (3) token-subset (semua token title kurasi ada di title halaman, pemenang token terbanyak, diterima bila unik dan >=2 token; title satu kata tidak ikut agar tak salah tempel). Entry cocok diupdate `photo_collection`-nya (title dipertahankan), URL tanpa kandidat yang cocok di-append sebagai `{title, api_url, photo_collection}` dan dilaporkan sebagai unmatched. Match ambiguous dilewati, tidak di-append, dan membuat pipeline berhenti dengan exit 1.
   Opsi:
   - `--update-title`: timpa title lama dengan title dari halaman.
   - `--drop-api-url`: entry baru tanpa `api_url` (destructive, hanya bila user meminta format tanpa `api_url`).
3. Jika `blocked` tidak kosong, itu berarti input invalid atau endpoint `/api/photos` dan fallback HTML sama-sama gagal (HTTP/Cloudflare). Untuk error transient beri jeda lebih lama (mis. `--delay 5`) dan retry sekali; URL invalid tidak di-retry. Kalau masih blocked, minta user simpan HTML dari browser (buka URL → View Source/`Ctrl+U` → Save As) lalu lanjut tanpa fetch:
   ```sh
   python3 .opencode/skills/kpics-cdn-extractor/scripts/extract_kpics.py --app CORTIS --apply --html-file /path/page.html "https://kpopping.com/kpics/<slug>"
   ```
   Tanpa URL pun bisa bila HTML memuat canonical/og:url Kpopping yang tervalidasi. Jika URL input diberikan, canonical/og:url wajib cocok; file tanpa metadata atau untuk slug lain ditolak. File simpanan berisi halaman challenge ikut terdeteksi `blocked` dan dilewati saat `--apply` (tidak mutasi gallery). Kalau masih blocked, laporkan sebagai partial failure — jangan klaim lengkap.
4. Verifikasi (ganti `cortis-api` dengan target aktual):
   ```sh
   python3 -m json.tool cortis-api/cortis-content.json > /dev/null && echo "JSON OK"
   python3 -c "import json; d=json.load(open('cortis-api/cortis-content.json')); print([(e['title'], len(e.get('photo_collection',[]))) for e in d['gallery']])"
   ```
5. Laporkan per URL: title terdeteksi, jumlah foto, 1 contoh, target file hasil mapping, dan mana yang blocked/fallback.

## Download aset + rewrite ke GitHub Pages (default langkah 2 dari full pipeline)

Script `scripts/download_assets.py` mengunduh `photo_collection` ke `<asset-dir>/<slug-title>/` dan menulis ulang link menjadi base Pages. Ini OTOMATIS jalan setelah `extract_kpics.py --apply`, bukan opsional terpisah:

```sh
python3 .opencode/skills/kpics-cdn-extractor/scripts/download_assets.py --app CORTIS --dry-run --rewrite-base https://fandomkpopuk-bot.github.io
python3 .opencode/skills/kpics-cdn-extractor/scripts/download_assets.py --app CORTIS --rewrite-base https://fandomkpopuk-bot.github.io --delay 0.5
python3 .opencode/skills/kpics-cdn-extractor/scripts/download_assets.py --app CORTIS --to-webp --rewrite-base https://fandomkpopuk-bot.github.io --delay 0.5
python3 -m json.tool cortis-api/cortis-content.json > /dev/null && echo "JSON OK"
```

Aturan: extractor dan downloader saat ini hanya menerima source JPEG (`.jpg`/`.jpeg`); PNG/WebP fail-closed. File JPEG valid dilewati secara idempotent; rewrite HANYA untuk URL yang file lokalnya terbukti ada — sisanya dipertahankan agar tak jadi link mati; `photo_collection` hasil rewrite mis. `https://fandomkpopuk-bot.github.io/cortis-asset/lollapalooza-photo-sketch/xxx.jpg`. Default asset dir `<app>-asset` (mis. `cortis-api` → `cortis-asset/`), bisa dioverride via `--asset-dir`. Jangan `git commit`.

Mode WebP (`--to-webp`, butuh `pip install pillow`, fallback `cwebp`/`ffmpeg`): file disimpan sebagai `.webp` (`xxx.jpg` → `xxx.webp`, kualitas default `--quality 80`), `.jpg` sementara dihapus kecuali `--keep-jpg`; idempotent (`.webp` valid dilewati, `.jpg` lama dikonversi tanpa download ulang); rewrite menunjuk ke `.xxx.webp`. Uji nyata: 4.7MB JPG → ~0.7MB WebP q80.

Bila `cdn.kpopping.com` 403 Cloudflare: minta user ekspor cookies browser (ekstensi "Get cookies.txt", setelah halaman lolos challenge) lalu:
```sh
python3 .opencode/skills/kpics-cdn-extractor/scripts/download_assets.py --app CORTIS --to-webp --rewrite-base https://fandomkpopuk-bot.github.io --cookies /tmp/cookies.txt --delay 0.5
```
Cookies Kpopping tidak berlaku untuk host R2. Bila URL R2 mengembalikan 403/access denied, laporkan sebagai masalah akses asset; jangan mengirim cookies Kpopping ke R2.

## Catatan

- Jumlah foto berasal dari `albumImages` API atau `initialData.albumImages` pada HTML, dengan fallback `src` untuk record lama (dapat 1 atau puluhan; jangan berasumsi Instagram update selalu 1 foto).
- Lokasi script relatif terhadap direktori skill ini: `scripts/extract_kpics.py`.
