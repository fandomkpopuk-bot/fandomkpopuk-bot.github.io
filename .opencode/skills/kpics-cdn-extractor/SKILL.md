---
name: Kppics CDN Extractor
description: Ubah kpopping.com/kpics URL menjadi list link CDN cdn.kpopping.com untuk photo_collection gallery.
---

# Kpics CDN Extractor

Gunakan skill ini setiap ada permintaan "ubah url kpopping menjadi list CDN" atau "isi photo_collection".

## Input

Satu atau banyak URL bentuk:

`https://kpopping.com/kpics/<slug>`

URL bisa ditempel di chat, atau disimpan sebagai file teks satu URL per baris (mis. `/tmp/urls.txt`).
Petunjuk app target bisa berupa nama app, api_dir, atau bagian perintah user (mis. `CORTIS`, `cortis`, `cortis-api`, `BTS - ARMY`, `bts`, `BLACKPINK`).

## Title otomatis

`title` diambil dari halaman itu sendiri, prioritas:

1. `<h1>` (paling bersih, mis. `CORTIS 2026 Lollapalooza Photo Sketch`)
2. `og:title`
3. `<title>` (dibersihkan dari suffix `HQ Photos`/`Photos` dan prefix `ARTIST —`)
4. Fallback: slug humanize (`cortis-2026-lollapalooza-photo-sketch` → `Cortis 2026 Lollapalooza Photo Sketch`)

Jangan menebak title di luar urutan itu. Saat update entry lama, pertahankan title kurasi manual kecuali user meminta `--update-title`.

## Mapping file via constanta.json

1. Baca `constanta.json` di repo root untuk mapping `app_name -> api_dir`.
   Contoh: `CORTIS -> cortis-api`, `BTS - ARMY -> bts-api`.
2. Cocokkan petunjuk user case-insensitive sebagai substring terhadap `app_name` ATAU `api_dir`.
   Contoh: `cortis`, `CORTIS`, `cortis-api` → `cortis-api`; `bts` → `bts-api`; `blackpink` → `blackpink-api`.
3. Jika `APP NAME` tidak ada di `constanta.json` tapi direktori `<slug>-api` ada (mis. `ENHYPEN` → `enhypen-api`), tetap pakai direktori tersebut dan laporkan sebagai fallback.
4. File target: `<api_dir>/*-content.json` pertama yang cocok, field `gallery`.

## Aturan (wajib)

1. Jangan pakai `webfetch` untuk halaman kpopping — selalu 403. Pakai script via `curl` dengan browser UA.
2. Jangan menebak URL CDN — hanya keluarkan URL yang benar-benar muncul di HTML halaman tersebut.
3. Dedup + sort. Abaikan `static/`, `avatar`, `graph`.
4. Jika HTML berisi `Just a moment...` dan kecil (<20KB) → tandai `blocked`, jangan keluarkan list kosong seolah lengkap. Jangan timpa `photo_collection` lama dengan hasil blocked/kosong.
5. Jangan hapus `api_url` di `*-content.json` kecuali user eksplisit meminta format `{title, photo_collection}` tanpa `api_url` (pakai `--drop-api-url` hanya atas otorisasi itu).
6. Langsung update file tanpa bertanya konfirmasi bila URL + petunjuk app sudah diberikan. Jangan `git commit` — hanya ubah working tree, commit biar user yang lakukan.
7. Tulis JSON dengan `ensure_ascii=False, indent=2`. Validasi dengan `python3 -m json.tool`.

## Workflow

Bila user memberi URL + petunjuk app (mis. `@kpics-cdn-extractor <url> cortis`), LANGSUNG scrape lalu update file — tanpa bertanya dulu, tanpa `git commit`:

```sh
echo "<url>" > /tmp/urls.txt
python3 .opencode/skills/kpics-cdn-extractor/scripts/extract_kpics.py --app CORTIS --apply --input /tmp/urls.txt --output /tmp/cdn.json --delay 2
python3 -m json.tool <api_dir>/<slug>-content.json > /dev/null && echo "JSON OK"
```

Hanya berhenti untuk konfirmasi bila: hasil `blocked`, match ambigu (dilaporkan script), atau app tidak ketemu di `constanta.json` maupun fallback direktori.

Scrape saja tanpa tulis (bila user hanya minta list, tanpa petunjuk app):

```sh
python3 .opencode/skills/kpics-cdn-extractor/scripts/extract_kpics.py --input /tmp/urls.txt --output /tmp/cdn.json --delay 2
```

Untuk satu URL cepat:

```sh
python3 .opencode/skills/kpics-cdn-extractor/scripts/extract_kpics.py "https://kpopping.com/kpics/<slug>"
```

Output: `{"items": {url: {"title": ..., "photos": [...]}}, "photos": {...}, "blocked": [...]}`.
2. Langsung terapkan ke gallery (mapping otomatis via `constanta.json`):
   ```sh
   python3 .opencode/skills/kpics-cdn-extractor/scripts/extract_kpics.py --app CORTIS --apply --input /tmp/urls.txt --delay 2
   ```
   Matching idempotent: (1) `api_url` persis, (2) title persis ternormalisasi, (3) token-subset (semua token title kurasi ada di title halaman, pemenang token terbanyak, diterima bila unik dan >=2 token; title satu kata tidak ikut agar tak salah tempel). Entry cocok diupdate `photo_collection`-nya (title dipertahankan), URL tak cocok di-append sebagai `{title, api_url, photo_collection}` dan dilaporkan sebagai ambiguous/unmatched.
   Opsi:
   - `--update-title`: timpa title lama dengan title dari halaman.
   - `--drop-api-url`: entry baru tanpa `api_url` (destructive, hanya bila user meminta format tanpa `api_url`).
3. Jika `blocked` tidak kosong, beri jeda lebih lama (mis. `--delay 5`) dan retry sekali. Kalau masih blocked, laporkan sebagai partial failure — jangan klaim lengkap.
4. Verifikasi (ganti `cortis-api` dengan target aktual):
   ```sh
   python3 -m json.tool cortis-api/cortis-content.json > /dev/null && echo "JSON OK"
   python3 -c "import json; d=json.load(open('cortis-api/cortis-content.json')); print([(e['title'], len(e.get('photo_collection',[]))) for e in d['gallery']])"
   ```
5. Laporkan per URL: title terdeteksi, jumlah foto, 1 contoh, target file hasil mapping, dan mana yang blocked/fallback.

## Download aset + rewrite ke GitHub Pages

Script `scripts/download_assets.py` mengunduh `photo_collection` ke `<asset-dir>/<slug-title>/` dan opsional menulis ulang link menjadi base Pages:

```sh
python3 .opencode/skills/kpics-cdn-extractor/scripts/download_assets.py --app CORTIS --dry-run --rewrite-base https://fandomkpopuk-bot.github.io
python3 .opencode/skills/kpics-cdn-extractor/scripts/download_assets.py --app CORTIS --rewrite-base https://fandomkpopuk-bot.github.io --delay 0.5
python3 .opencode/skills/kpics-cdn-extractor/scripts/download_assets.py --app CORTIS --to-webp --rewrite-base https://fandomkpopuk-bot.github.io --delay 0.5
python3 -m json.tool cortis-api/cortis-content.json > /dev/null && echo "JSON OK"
```

Aturan: idempotent (file JPEG valid dilewati); rewrite HANYA untuk URL yang file lokalnya terbukti ada — sisanya dipertahankan agar tak jadi link mati; `photo_collection` hasil rewrite mis. `https://fandomkpopuk-bot.github.io/cortis-asset/lollapalooza-photo-sketch/xxx.jpg`. Default asset dir `<app>-asset` (mis. `cortis-api` → `cortis-asset/`), bisa dioverride via `--asset-dir`. Jangan `git commit`.

Mode WebP (`--to-webp`, butuh `pip install pillow`, fallback `cwebp`/`ffmpeg`): file disimpan sebagai `.webp` (`xxx.jpg` → `xxx.webp`, kualitas default `--quality 80`), `.jpg` sementara dihapus kecuali `--keep-jpg`; idempotent (`.webp` valid dilewati, `.jpg` lama dikonversi tanpa download ulang); rewrite menunjuk ke `.xxx.webp`. Uji nyata: 4.7MB JPG → ~0.7MB WebP q80.

## Catatan

- Lollapalooza photo sketch menghasilkan ~32 foto; Instagram update biasanya 1 foto cover di HTML statis.
- Lokasi script relatif terhadap direktori skill ini: `scripts/extract_kpics.py`.
