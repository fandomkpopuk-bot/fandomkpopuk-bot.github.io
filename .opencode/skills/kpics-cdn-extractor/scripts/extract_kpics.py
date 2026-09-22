#!/usr/bin/env python3
"""Extract cdn.kpopping.com photo list + title from kpopping.com/kpics/<slug> pages.

Usage:
  python3 extract_kpics.py https://kpopping.com/kpics/<slug> [...]
  python3 extract_kpics.py --input /tmp/urls.txt --output /tmp/cdn.json --delay 2
  python3 extract_kpics.py --app CORTIS --apply --input /tmp/urls.txt --delay 2

Notes:
- Uses curl with a browser UA via subprocess. Do NOT use webfetch/default
  HTTP client: kpopping returns 403 for non-browser UA.
- Detects Cloudflare "Just a moment..." challenge and reports blocked
  instead of returning empty silently.
- Idempotent: same URL list always yields same sorted-dedup output.
- Title: diambil dari <h1> > og:title > <title> > slug humanize.
  Jangan menebak title selain fallback tersebut.
- Target file: dibaca dari constanta.json (app_name -> api_dir ->
  <api_dir>/*-content.json). Lihat SKILL.md untuk aturan mapping.
"""
import argparse
import glob
import html as htmlmod
import json
import os
import re
import subprocess
import sys
import time

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def fetch_html(url: str, timeout: int = 25) -> str:
    r = subprocess.run(
        ["curl", "-sL", "-A", UA, "-m", str(timeout), url],
        capture_output=True,
    )
    return r.stdout.decode("utf-8", errors="ignore")


def slug_humanize(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    slug = slug.split("?")[0]
    text = slug.replace("-", " ").replace("_", " ").strip()
    return text.title() if text else slug


def clean_title(raw: str) -> str:
    t = htmlmod.unescape(raw or "").strip()
    t = re.sub(r"\s+", " ", t)
    # Buang suffix umum: " HQ Photos", " Photos" pada <title>/og:title.
    t = re.sub(r"\s+HQ Photos?$", "", t, flags=re.I)
    # Pola "<title>CORTIS — CORTIS 2026 ... Photos</title>": ambil sesudah em-dash.
    if "—" in t:
        parts = [p.strip() for p in t.split("—") if p.strip()]
        # Hindari duplikasi "CORTIS — CORTIS ...": ambil bagian terpanjang.
        t = max(parts, key=len)
    t = re.sub(r"\s+Photos?$", "", t, flags=re.I).strip()
    return t


def extract_title(html: str, url: str) -> str:
    if "Just a moment..." in html and len(html) < 20000:
        return slug_humanize(url)
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    if m:
        t = clean_title(re.sub(r"<[^>]+>", "", m.group(1)))
        if t:
            return t
    m = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.I,
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        html,
        re.I,
    )
    if m:
        t = clean_title(m.group(1))
        if t:
            return t
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if m:
        t = clean_title(m.group(1))
        if t:
            return t
    return slug_humanize(url)


def extract_cdn(html: str) -> list[str]:
    if "Just a moment..." in html and len(html) < 20000:
        return []
    out: set[str] = set()
    # Direct CDN refs: https://cdn.kpopping.com/kpics/...jpg (skip static/avatar)
    for m in re.findall(r"https?://cdn\.kpopping\.com/kpics/[A-Za-z0-9\-/._]+?\.jpg", html):
        if "static/" in m or "avatar" in m:
            continue
        out.add(m.split("\\")[0])
    # Next.js encoded payloads: kpics%2F2026%2F09%2Fxxx.jpg
    for fid in re.findall(r"kpics%2F(\d{4})%2F(\d{2})%2F([A-Za-z0-9\-\.]+?\.jpg)", html):
        year, month, name = fid
        out.add(f"https://cdn.kpopping.com/kpics/{year}/{month}/{name}")
    # Plain payloads: kpics/2026/09/xxx.jpg
    for fid in re.findall(r"kpics/(\d{4})/(\d{2})/([A-Za-z0-9\-\.]+?\.jpg)", html):
        year, month, name = fid
        out.add(f"https://cdn.kpopping.com/kpics/{year}/{month}/{name}")
    return sorted(out)


def load_constanta(path: str = "constanta.json") -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def resolve_content_file(app_hint: str, constanta_path: str = "constanta.json") -> str:
    """Map petunjuk/perintah user -> file *-content.json via constanta.json.

    1. Baca constanta.json (app_name -> api_dir).
    2. Cocokkan app_hint case-insensitive sebagai substring terhadap app_name
       ATAU api_dir (mis. "cortis", "CORTIS", "bts", "BLACKPINK - BLINK").
    3. Jika tidak cocok tapi direktori "<hint>-api" ada (mis. ENHYPEN),
       pakai direktori tersebut dan laporkan sebagai fallback.
    4. Kembalikan "<api_dir>/*-content.json" pertama yang ada.
    """
    hint = (app_hint or "").strip().lower()
    if not hint:
        raise ValueError("app_hint kosong")
    entries = load_constanta(constanta_path)
    api_dir = None
    for e in entries:
        app_name = str(e.get("app_name", ""))
        dir_name = str(e.get("api_dir", ""))
        if hint in app_name.lower() or hint == dir_name.lower() or hint in dir_name.lower():
            api_dir = dir_name
            break
    if api_dir is None:
        # Fallback: <hint>-api persis (mis. ENHYPEN -> enhypen-api).
        cand = f"{hint}-api"
        if os.path.isdir(cand):
            api_dir = cand
        else:
            # Fallback longgar: direktori *-api yang mengandung hint.
            for d in sorted(glob.glob("*-api")):
                if hint in d.lower() and os.path.isdir(d):
                    api_dir = d
                    break
    if api_dir is None:
        known = [str(e.get("app_name", "")) for e in entries]
        raise FileNotFoundError(f"app '{app_hint}' tidak ada di {constanta_path} ({known}) dan tidak ada direktori *-api yang cocok")
    matches = sorted(glob.glob(os.path.join(api_dir, "*-content.json")))
    if not matches:
        raise FileNotFoundError(f"tidak ada *-content.json di {api_dir}/")
    return matches[0]


def norm_title(t: str) -> str:
    t = htmlmod.unescape(t or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def norm_tokens(t: str) -> list[str]:
    return norm_title(t).split()


def apply_to_gallery(
    content_path: str,
    items: dict[str, dict],
    keep_api_url: bool = True,
    update_title: bool = False,
) -> dict:
    """Terapkan hasil scrape ke gallery secara idempotent.

    Urutan matching per URL:
    1. api_url persis == URL kpopping.
    2. Title persis ternormalisasi (temuan halaman == title kurasi).
    3. Token-subset: semua token title kurasi ada di title halaman,
       pemenang = token terbanyak; hanya diterima bila unik (selisih
       >=1 dari runner-up) DAN pemenang punya >=2 token. Title kurasi
       satu kata (mis. "Cortis", "Martin") tidak ikut similarity agar
       tidak salah tempel — dilaporkan sebagai unmatched.
    Jika cocok: update photo_collection; title hanya diubah bila
    --update-title (agar judul kurasi manual tidak tertimpa).
    Jika tidak cocok: append entry baru {title, [api_url,] photo_collection}.
    Mengembalikan ringkasan {updated, appended, total, ambiguous, unmatched}.
    """
    with open(content_path, encoding="utf-8") as f:
        data = json.load(f)
    gallery = data.get("gallery")
    if gallery is None:
        gallery = []
        data["gallery"] = gallery
    by_api: dict[str, dict] = {}
    by_title: dict[str, dict] = {}
    for e in gallery:
        if not isinstance(e, dict):
            continue
        if e.get("api_url"):
            by_api[e["api_url"]] = e
        if e.get("title"):
            by_title.setdefault(norm_title(e["title"]), e)
    updated, appended = 0, 0
    ambiguous, unmatched = [], []
    for url, item in items.items():
        photos = item["photos"]
        title = item["title"]
        e = by_api.get(url) or by_title.get(norm_title(title))
        basis = "api_url" if by_api.get(url) else ("exact" if e is not None else None)
        if e is None:
            toks = set(norm_tokens(title))
            scored = []
            for cur_norm, cand in by_title.items():
                cur_toks = cur_norm.split()
                if len(cur_toks) < 2 or not toks:
                    continue
                if all(t in toks for t in cur_toks):
                    scored.append((len(cur_toks), cand))
            scored.sort(key=lambda x: -x[0])
            if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]):
                e = scored[0][1]
                basis = f"similar({scored[0][0]}t)"
            elif scored:
                ambiguous.append(url)
        if e is not None:
            e["photo_collection"] = photos
            if update_title or not e.get("title"):
                e["title"] = title
            updated += 1
            print(f"{url} -> '{e.get('title')}' via {basis} photos={len(photos)}",
                  file=sys.stderr)
        else:
            if url not in ambiguous:
                unmatched.append(url)
            new_entry: dict = {"title": title}
            if keep_api_url:
                new_entry["api_url"] = url
            new_entry["photo_collection"] = photos
            gallery.append(new_entry)
            appended += 1
            print(f"{url} -> NEW '{title}' photos={len(photos)}", file=sys.stderr)
    with open(content_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"updated": updated, "appended": appended, "total": len(gallery),
            "ambiguous": ambiguous, "unmatched": unmatched}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--input", default=None)
    ap.add_argument("--output", default=None)
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--app", default=None,
                    help="Petunjuk app (mis. CORTIS) untuk mapping via constanta.json")
    ap.add_argument("--constanta", default="constanta.json")
    ap.add_argument("--apply", action="store_true",
                    help="Tulis langsung ke <api_dir>/*-content.json (perlu --app)")
    ap.add_argument("--drop-api-url", action="store_true",
                    help="Entry baru tanpa api_url (destructive, perlu otorisasi user)")
    ap.add_argument("--update-title", action="store_true",
                    help="Timpa title lama dengan title dari halaman")
    args = ap.parse_args()

    urls = list(args.urls)
    if args.input:
        with open(args.input, encoding="utf-8") as f:
            urls += [l.strip() for l in f if l.strip()]

    if not urls:
        print("no urls", file=sys.stderr)
        return 2

    if args.apply and not args.app:
        print("--apply perlu --app", file=sys.stderr)
        return 2

    items: dict[str, dict] = {}
    blocked: list[str] = []
    for i, u in enumerate(urls):
        html = fetch_html(u)
        if "Just a moment..." in html and len(html) < 20000:
            blocked.append(u)
            items[u] = {"title": slug_humanize(u), "photos": []}
        else:
            items[u] = {"title": extract_title(html, u), "photos": extract_cdn(html)}
        if i < len(urls) - 1:
            time.sleep(args.delay)

    photos_only = {u: v["photos"] for u, v in items.items()}
    payload = {"items": items, "photos": photos_only, "blocked": blocked}
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    elif not args.apply:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    applied = None
    target = None
    if args.apply:
        target = resolve_content_file(args.app, args.constanta)
        applied = apply_to_gallery(
            target,
            items,
            keep_api_url=not args.drop_api_url,
            update_title=args.update_title,
        )

    for u, v in items.items():
        print(f"{u} -> title={v['title']!r} photos={len(v['photos'])}", file=sys.stderr)
    if blocked:
        print(f"BLOCKED (cloudflare): {len(blocked)}", file=sys.stderr)
    if target:
        print(f"TARGET: {target} applied={applied}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
