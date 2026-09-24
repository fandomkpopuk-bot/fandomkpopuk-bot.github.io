#!/usr/bin/env python3
"""Extract cdn.kpopping.com photo list + title from kpopping.com/kpics/<slug> pages.

Usage:
  python3 extract_kpics.py https://kpopping.com/kpics/<slug> [...]
  python3 extract_kpics.py --input /tmp/urls.txt --output /tmp/cdn.json --delay 2
  python3 extract_kpics.py --app CORTIS --apply --input /tmp/urls.txt --delay 2
  python3 extract_kpics.py --app CORTIS --apply --html-file page.html https://kpopping.com/kpics/<slug>

Notes:
- Uses curl with a browser UA via subprocess. Do NOT use webfetch/default
  HTTP client: kpopping returns 403 for non-browser UA.
- Bila curl diblokir Cloudflare, pakai --html-file: file HTML yang
  disimpan dari browser asli (View Source -> Save As). Tidak ada fetch
  jaringan untuk URL yang dipasangkan ke file lokal.
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


def read_input_file(path: str) -> str:
    """Baca file HTML simpanan browser (plain .html atau .mhtml/.mht).

    MHTML (multipart/related) di-decode via stdlib email: tiap part
    text/html di-decode (quoted-printable/base64) lalu digabung.
    Tanpa ini, URL di dalam MHTML terpecah encoding (=3D, soft break)
    sehingga regex CDN/canonical gagal match.
    """
    with open(path, "rb") as f:
        raw = f.read()
    lower = path.lower()
    if lower.endswith((".mhtml", ".mht")):
        import email
        from email import policy
        from io import BytesIO
        try:
            msg = email.message_from_binary_file(
                BytesIO(raw), policy=policy.default)
        except Exception:
            msg = None
        if msg is not None:
            parts = []
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        try:
                            parts.append(part.get_content_text())
                            continue
                        except Exception:
                            pass
                        try:
                            payload = part.get_payload(decode=True) or b""
                        except Exception:
                            payload = b""
                        parts.append(payload.decode("utf-8", errors="ignore"))
            if parts:
                return "\n".join(p for p in parts if p)
    return raw.decode("utf-8", errors="ignore")


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


def extract_canonical_url(html):
    """Ambil URL kanonis halaman (canonical > og:url), khusus /kpics/.

    Dipakai --html-file agar file simpanan browser otomatis terpetakan
    ke URL kpopping tanpa fetch jaringan. Kembalikan None bila tak ada.
    """
    m = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
        html, re.I,
    ) or re.search(
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']',
        html, re.I,
    )
    if m and "/kpics/" in m.group(1):
        return htmlmod.unescape(m.group(1)).strip()
    m = re.search(
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.I,
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:url["\']',
        html, re.I,
    )
    if m and "/kpics/" in m.group(1):
        return htmlmod.unescape(m.group(1)).strip()
    return None


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
    ap.add_argument("--html-file", action="append", default=[],
                    help="File HTML simpanan browser (.html atau .mhtml, "
                         "bypass Cloudflare, tanpa fetch jaringan). Bisa "
                         "diulang; tiap file dipasangkan ke satu URL "
                         "positional/--input (kasus 1 file + 1 URL) atau ke "
                         "canonical/og:url di HTML-nya.")
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

    html_paths = list(args.html_file or [])
    html_contents = {}
    for hf in html_paths:
        if not os.path.exists(hf):
            print(f"--html-file tidak ada: {hf}", file=sys.stderr)
            return 2
        html_contents[hf] = read_input_file(hf)

    if not urls and not html_paths:
        print("no urls", file=sys.stderr)
        return 2

    if args.apply and not args.app:
        print("--apply perlu --app", file=sys.stderr)
        return 2

    # Pasangan URL <-> file HTML lokal. Kasus umum: 1 file + 1 URL.
    # Selain itu tiap file memakai canonical/og:url dari HTML-nya,
    # fallback ke urutan urls. URL berpasangan TIDAK di-fetch.
    paired = {}
    fetch_urls = list(urls)
    if len(html_paths) == 1 and len(fetch_urls) == 1:
        paired[fetch_urls.pop(0)] = html_paths[0]
    else:
        for i, hf in enumerate(html_paths):
            cu = extract_canonical_url(html_contents[hf])
            if cu and cu not in paired:
                paired[cu] = hf
            elif i < len(urls) and urls[i] not in paired:
                paired[urls[i]] = hf
            else:
                print(f"--html-file tanpa pasangan URL (tidak ada "
                      f"canonical/og:url di {hf})", file=sys.stderr)
                return 2
        for u in paired:
            if u in fetch_urls:
                fetch_urls.remove(u)

    items: dict[str, dict] = {}
    blocked: list[str] = []

    def ingest(u: str, html: str, source: str) -> None:
        if "Just a moment..." in html and len(html) < 20000:
            blocked.append(u)
            items[u] = {"title": slug_humanize(u), "photos": []}
        else:
            items[u] = {"title": extract_title(html, u), "photos": extract_cdn(html)}
        print(f"{u} <- {source} photos={len(items[u]['photos'])}",
              file=sys.stderr)

    for i, u in enumerate(fetch_urls):
        ingest(u, fetch_html(u), "fetch")
        if i < len(fetch_urls) - 1 or paired:
            time.sleep(args.delay)
    for u, hf in paired.items():
        ingest(u, html_contents[hf], f"local {hf}")

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
        # Jangan mutasi gallery dengan hasil blocked/kosong (Cloudflare
        # "Just a moment..."): entry baru 0-foto maupun overwrite
        # photo_collection lama dilarang oleh SKILL.md aturan 4.
        apply_items = {u: v for u, v in items.items() if u not in blocked}
        skipped = [u for u in items if u in blocked]
        applied = apply_to_gallery(
            target,
            apply_items,
            keep_api_url=not args.drop_api_url,
            update_title=args.update_title,
        )
        if skipped:
            applied["skipped_blocked"] = skipped
            print(f"SKIPPED blocked (tidak dimutasi): {len(skipped)}", file=sys.stderr)

    for u, v in items.items():
        print(f"{u} -> title={v['title']!r} photos={len(v['photos'])}", file=sys.stderr)
    if blocked:
        print(f"BLOCKED (cloudflare): {len(blocked)}", file=sys.stderr)
    if target:
        print(f"TARGET: {target} applied={applied}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
