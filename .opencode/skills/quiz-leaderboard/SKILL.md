---
name: Quiz Leaderboard Updater
description: Update leaderboard *-quiz.json dari data tabular APP NAME, dedup DEVICE ID ambil skor tertinggi, skip skor kosong/error, maks 8 entri.
---

# Quiz Leaderboard Updater

Gunakan skill ini setiap ada permintaan "update leaderboard" dengan data tabular.

## Input

Tabel TSV / teks dengan kolom:

`APP NAME | NAME | COUNTRY | PHONE | SCORE | DATE | DEVICE ID`

Data bisa ditempel di chat user, atau disimpan sebagai file (mis. `/tmp/leaderboard.tsv`).

## Acuan

1. Baca `constanta.json` di repo root untuk mapping `app_name -> api_dir`.
   Contoh: `CORTIS -> cortis-api`, `BTS - ARMY -> bts-api`.
2. File target: `<api_dir>/<slug>-quiz.json`, field `leaderboard`.
   Format entri yang disimpan hanya:
   ```json
   {"name": "...", "country": "...", "score": 1234}
   ```
3. Jika `APP NAME` tidak ada di `constanta.json` tapi direktori `<slug>-api` ada (mis. `ENHYPEN`), tetap update direktori tersebut dan laporkan.

## Aturan (wajib)

1. `SCORE` harus integer valid. Jika kosong, `#ERROR!`, non-numerik → SKIP baris tersebut.
2. Dedup per `APP NAME + DEVICE ID`: jika satu DEVICE ID muncul >1x, simpan SATU dengan `SCORE` tertinggi. Jika seri, ambil kemunculan pertama.
3. Sort descending by `score` per app.
4. Ambil maksimal 8 entri teratas per app.
5. Replace seluruh `leaderboard` di file JSON target (jangan merge dengan dummy lama).
6. Pertahankan `quiz_list`, `event_list`, `quiz_version`. Tulis JSON dengan `ensure_ascii=False, indent=2`.

## Workflow

1. Kumpulkan baris data ke file sementara, lalu jalankan:
   ```sh
   python3 .opencode/skills/quiz-leaderboard/scripts/update_leaderboard.py --input /tmp/leaderboard.tsv
   ```
   Script membaca `constanta.json` otomatis, melakukan dedup/sort/top-8, dan menulis ulang file `*-quiz.json`.
2. Jika input ditempel langsung di chat (bukan file), simpan dulu ke `/tmp/leaderboard.tsv` lalu jalankan script.
3. Verifikasi:
   ```sh
   python3 -c "import json,glob; [print(f+': '+str(len(json.load(open(f))['leaderboard']))) for f in sorted(glob.glob('*-api/*-quiz.json'))]"
   ```
4. Laporkan per app: jumlah entri, skor teratas, baris yang di-skip (error) dan duplikat yang dibuang.

## Catatan

- Jangan menebak mapping: selalu baca `constanta.json`.
- Jangan menyimpan `PHONE`, `DATE`, `DEVICE ID` ke JSON — hanya untuk dedup.
- Ejaan `NAME`/`COUNTRY` dipertahankan apa adanya (termasuk emoji/unicode).
