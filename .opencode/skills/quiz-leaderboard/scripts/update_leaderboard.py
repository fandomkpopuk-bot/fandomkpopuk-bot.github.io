#!/usr/bin/env python3
"""Update leaderboard *-quiz.json dari data tabular.

Usage:
  python3 update_leaderboard.py --input /tmp/leaderboard.tsv [--root .]

Input: TSV / pipe / whitespace dengan kolom:
  APP NAME | NAME | COUNTRY | PHONE | SCORE | DATE | DEVICE ID
Header opsional (baris yang mengandung APP NAME + SCORE) otomatis di-skip.

Aturan: SCORE harus int, dedup APP+DEVICE ambil skor max, sort desc, top 8,
replace leaderboard [{name, country, score}].
"""
import argparse
import json
import pathlib
import re
import sys


def parse_rows(text: str):
    rows = []
    skipped = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        # skip header
        if re.search(r"APP\s*NAME", line, re.I) and re.search(r"SCORE", line, re.I) and re.search(r"DEVICE", line, re.I):
            continue
        parts = re.split(r"\t|\|", raw)
        parts = [p.strip() for p in parts]
        if len(parts) < 7:
            # coba split whitespace 7+ kolom dari kanan: DEVICE, DATE(2 token), SCORE, ...
            # fallback: skip
            skipped.append((lineno, raw, "kolom < 7"))
            continue
        app, name, country, phone, score_raw, date, device = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
        if not app or not device:
            skipped.append((lineno, raw, "app/device kosong"))
            continue
        try:
            score = int(str(score_raw).strip().replace(",", ""))
        except Exception:
            skipped.append((lineno, raw, f"score invalid: {score_raw!r}"))
            continue
        rows.append({
            "app": app.strip(),
            "name": name.strip(),
            "country": country.strip(),
            "score": score,
            "device": device.strip(),
            "lineno": lineno,
        })
    return rows, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", "-i", required=True, help="file TSV input")
    ap.add_argument("--root", "-r", default=".", help="repo root (berisi constanta.json)")
    args = ap.parse_args()

    root = pathlib.Path(args.root).resolve()
    const_path = root / "constanta.json"
    if not const_path.exists():
        print(f"constanta.json tidak ditemukan di {const_path}", file=sys.stderr)
        sys.exit(1)

    constanta = json.loads(const_path.read_text(encoding="utf-8"))
    mapping = {c["app_name"].strip(): c["api_dir"].strip() for c in constanta}

    text = pathlib.Path(args.input).read_text(encoding="utf-8")
    rows, skipped = parse_rows(text)

    # dedup per (app, device) -> skor max
    best = {}
    dup_dropped = 0
    for r in rows:
        key = (r["app"], r["device"])
        if key not in best or r["score"] > best[key]["score"]:
            if key in best:
                dup_dropped += 1
            best[key] = r
        else:
            dup_dropped += 1

    from collections import defaultdict
    groups = defaultdict(list)
    for r in best.values():
        groups[r["app"]].append(r)

    for app in sorted(groups):
        groups[app].sort(key=lambda x: -x["score"])
        groups[app] = groups[app][:8]

    for app, items in groups.items():
        api_dir = mapping.get(app)
        if api_dir is None:
            # fallback: slug-api, mis. ENHYPEN -> enhypen-api
            slug = re.sub(r"\s*-.*$", "", app).strip().lower().replace(" ", "")
            cand = root / f"{slug}-api"
            if cand.is_dir():
                api_dir = f"{slug}-api"
                print(f"[WARN] {app!r} tidak ada di constanta.json, fallback ke {api_dir}")
            else:
                print(f"[SKIP] {app!r}: tidak ada di constanta.json dan {cand} tidak ada")
                continue
        targets = sorted((root / api_dir).glob("*-quiz.json"))
        if not targets:
            print(f"[SKIP] {app!r}: tidak ada *-quiz.json di {api_dir}")
            continue
        lb = [{"name": r["name"], "country": r["country"], "score": r["score"]} for r in items]
        for target in targets:
            data = json.loads(target.read_text(encoding="utf-8"))
            data["leaderboard"] = lb
            target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"OK {target.relative_to(root)}: {len(lb)} entri (top={lb[0]['score'] if lb else '-'})")

    print(f"Dedup: {len(rows)} baris -> {len(best)} unik, {dup_dropped} duplikat dibuang, {len(skipped)} baris skip.")
    for lineno, raw, reason in skipped:
        print(f"  SKIP line {lineno}: {reason}: {raw[:120]}")


if __name__ == "__main__":
    main()
