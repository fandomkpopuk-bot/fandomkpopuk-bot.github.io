#!/usr/bin/env python3
"""Extract cdn.kpopping.com photo list + title from kpopping.com/kpics/<slug> pages.

Usage:
  python3 extract_kpics.py https://kpopping.com/kpics/<slug> [...]
  python3 extract_kpics.py --input /tmp/urls.txt --output /tmp/cdn.json --delay 2
  python3 extract_kpics.py --app CORTIS --apply --input /tmp/urls.txt --delay 2
  python3 extract_kpics.py --app CORTIS --apply --html-file page.html https://kpopping.com/kpics/<slug>

Notes:
- Uses curl via subprocess. Do NOT use webfetch/default HTTP clients for
  kpopping pages: Cloudflare returns a 403 "Just a moment..." challenge.
- API-first: untuk /kpics/<slug>, baca endpoint JSON yang dipanggil halaman
  sendiri, /api/photos?slug=<slug>. Endpoint ini mengembalikan title dan
  albumImages[].src tanpa challenge. HTML page hanya fallback.
- Bila API dan HTML tidak tersedia, --html-file menerima file HTML/MHTML
  yang disimpan dari browser asli (View Source -> Save As). HTML fallback
  hanya memakai initialData.albumImages, bukan semua URL related.
- Asset validation currently accepts JPEG (`.jpg`/`.jpeg`) only. PNG/WebP
  records are rejected fail-closed until the downloader supports them.
- Detects Cloudflare "Just a moment..." challenge and reports blocked
  instead of returning empty silently.
- Idempotent: same URL list always yields same sorted-dedup output.
- Title: API `title` > <h1> > og:title > <title> > slug humanize.
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
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse, urlunparse

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
STATUS_MARKER = b"\n__KPICS_HTTP_STATUS__:"
# Host gambar yang dipakai API resmi saat ini. Jangan persist/download
# URL dari origin arbitrer yang hanya muncul di payload.
TRUSTED_ASSET_HOSTS = {
    "cdn.kpopping.com",
    "pub-dc9a9c6ac2a64ba48bce426ced0ac56a.r2.dev",
}
SUPPORTED_ASSET_EXTENSIONS = (".jpg", ".jpeg")
KPOPPING_PAGE_HOSTS = {"kpopping.com", "www.kpopping.com"}


def is_cloudflare_challenge(html: str) -> bool:
    return "Just a moment..." in html and len(html) < 20000


def normalize_kpics_url(page_url: str) -> str | None:
    """Validate and canonicalize one public Kpopping kpics page URL."""
    if not isinstance(page_url, str):
        return None
    try:
        parsed = urlparse(page_url)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme != "https" or host not in KPOPPING_PAGE_HOSTS:
        return None
    if port not in (None, 443) or parsed.username or parsed.password:
        return None
    if parsed.query or parsed.fragment:
        return None
    path = parsed.path.rstrip("/")
    parts = path.split("/")
    if len(parts) != 3 or parts[0] != "" or parts[1].lower() != "kpics":
        return None
    slug = unquote(parts[2])
    if not slug or "/" in slug or slug in {".", ".."}:
        return None
    return f"https://kpopping.com/kpics/{quote(slug, safe='-._~')}"


def build_photo_api_url(page_url: str) -> str | None:
    """Bangun endpoint JSON resmi yang dipanggil halaman /kpics/[slug]."""
    normalized = normalize_kpics_url(page_url)
    if not normalized:
        return None
    slug = unquote(urlparse(normalized).path.rsplit("/", 1)[-1])
    return urlunparse((
        "https",
        "kpopping.com",
        "/api/photos",
        "",
        urlencode({"slug": slug}),
        "",
    ))


def fetch_html_response(url: str, timeout: int = 25) -> tuple[str, int, str]:
    """Fetch HTML while retaining HTTP status/curl error for safe fallback."""
    result = subprocess.run(
        [
            "curl", "-sS", "-A", UA, "-m", str(timeout),
            "-w", "\n__KPICS_HTTP_STATUS__:%{http_code}", url,
        ],
        capture_output=True,
    )
    body, marker, status_raw = result.stdout.rpartition(STATUS_MARKER)
    try:
        status = int(status_raw.strip()) if marker else 0
    except ValueError:
        status = 0
    error = result.stderr.decode("utf-8", errors="ignore").strip()
    if result.returncode != 0:
        error = error or f"curl exit {result.returncode}"
    return body.decode("utf-8", errors="ignore"), status, error


def fetch_html(url: str, timeout: int = 25) -> str:
    """Backward-compatible HTML-only wrapper."""
    return fetch_html_response(url, timeout)[0]


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


def clean_title(raw: object) -> str:
    t = htmlmod.unescape(raw if isinstance(raw, str) else "").strip()
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


def normalized_sort_order(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def is_kpic_asset_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(htmlmod.unescape(value).strip())
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme != "https" or host not in TRUSTED_ASSET_HOSTS:
        return False
    if parsed.fragment:
        return False
    if port not in (None, 443) or parsed.username or parsed.password:
        return False
    path = unquote(parsed.path).lower()
    if not path.startswith("/kpics/") or not path.endswith(SUPPORTED_ASSET_EXTENSIONS):
        return False
    return ".." not in path.split("/") and not any(
        part in path for part in ("/static/", "/avatar", "/graph")
    )


def parse_photo_api(
    page_url: str,
    payload: object,
    fallback_title: str | None = None,
) -> dict | None:
    """Ubah respons /api/photos menjadi item extractor tanpa menebak URL."""
    if not isinstance(payload, dict):
        return None
    requested = build_photo_api_url(page_url)
    if not requested:
        return None
    requested_slug = parse_qs(urlparse(requested).query).get("slug", [""])[0]
    if str(payload.get("slug") or "") != requested_slug:
        return None

    title = clean_title(payload.get("title"))
    if not title and fallback_title is not None:
        title = clean_title(fallback_title) or slug_humanize(page_url)
    if not title:
        return None

    album_images_present = "albumImages" in payload
    album_images = payload.get("albumImages")
    if album_images_present and not isinstance(album_images, list):
        return None
    if not album_images_present:
        album_images = []
    for image in album_images:
        if not isinstance(image, dict) or not is_kpic_asset_url(image.get("src")):
            print(
                f"WARN API malformed albumImages for {requested_slug}",
                file=sys.stderr,
            )
            return None
        if "sortOrder" in image and normalized_sort_order(image.get("sortOrder")) is None:
            print(
                f"WARN API malformed sortOrder for {requested_slug}",
                file=sys.stderr,
            )
            return None
    ordered = sorted(
        enumerate(album_images),
        key=lambda pair: (
            normalized_sort_order(pair[1].get("sortOrder"))
            if isinstance(pair[1], dict)
            and normalized_sort_order(pair[1].get("sortOrder")) is not None
            else float("inf"),
            pair[0],
        ),
    )
    photos: list[str] = []
    seen: set[str] = set()
    for _, image in ordered:
        src = htmlmod.unescape(image["src"]).strip()
        if src not in seen:
            seen.add(src)
            photos.append(src)

    # src adalah fallback hanya untuk record lama tanpa albumImages, atau
    # ketika albumImages benar-benar kosong. Jangan menutupi list yang
    # nonempty tetapi gagal divalidasi.
    raw_src = payload.get("src")
    if "src" in payload and raw_src is not None and not isinstance(raw_src, str):
        print(f"WARN API malformed src for {requested_slug}", file=sys.stderr)
        return None
    if not photos and (not album_images_present or not album_images):
        if isinstance(raw_src, str) and raw_src and not is_kpic_asset_url(raw_src):
            print(f"WARN API malformed src for {requested_slug}", file=sys.stderr)
            return None
        if is_kpic_asset_url(raw_src):
            photos.append(htmlmod.unescape(raw_src).strip())

    if "albumCount" in payload:
        expected = payload.get("albumCount")
        valid_count = (
            isinstance(expected, int)
            and not isinstance(expected, bool)
            and expected >= 0
        )
        if not valid_count or expected != len(photos):
            print(
                f"WARN API incomplete: albumCount={expected!r} images={len(photos)} "
                f"for {requested_slug}",
                file=sys.stderr,
            )
            return None
    elif album_images:
        print(
            f"WARN API incomplete: albumCount missing images={len(photos)} "
            f"for {requested_slug}",
            file=sys.stderr,
        )
        return None
    return {"title": title, "photos": photos}


def extract_embedded_photo_item(html: str, page_url: str) -> dict | None:
    """Ambil initialData.albumImages dari RSC HTML, bukan semua URL halaman."""
    search_from = 0
    while True:
        marker = html.find("initialData", search_from)
        if marker < 0:
            return None
        start = html.find("{", marker)
        if start < 0:
            return None
        depth = 0
        in_string = False
        escaped = False
        end = None
        for index in range(start, len(html)):
            char = html[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if in_string:
                if char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        if end is None:
            return None
        raw = html[start:end]
        candidates = [raw, f'"{raw}"']
        for candidate in candidates:
            text = candidate
            for _ in range(3):
                try:
                    payload = json.loads(text)
                except (TypeError, ValueError):
                    break
                if isinstance(payload, dict):
                    item = parse_photo_api(
                        page_url,
                        payload,
                        fallback_title=extract_title(html, page_url),
                    )
                    if item is not None:
                        return item
                    break
                if not isinstance(payload, str):
                    break
                text = payload
        search_from = end


def fetch_photo_api(page_url: str, timeout: int = 25) -> dict | None:
    """Ambil data galeri dari API publik; endpoint ini tidak lewat challenge."""
    endpoint = build_photo_api_url(page_url)
    if not endpoint:
        return None
    result = subprocess.run(
        [
            "curl", "-sS", "--compressed", "-A", UA,
            "-m", str(timeout), "-w", "\n__KPICS_HTTP_STATUS__:%{http_code}",
            endpoint,
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    body, marker, status_raw = result.stdout.rpartition(STATUS_MARKER)
    if not marker or status_raw.strip() != b"200":
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return parse_photo_api(page_url, payload)


def extract_title(html: str, url: str) -> str:
    if is_cloudflare_challenge(html):
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
    """Ambil URL kanonis tervalidasi (canonical > og:url), khusus /kpics/."""
    candidates = []
    m = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
        html, re.I,
    ) or re.search(
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']',
        html, re.I,
    )
    if m:
        candidates.append(m.group(1))
    m = re.search(
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.I,
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:url["\']',
        html, re.I,
    )
    if m:
        candidates.append(m.group(1))
    for candidate in candidates:
        normalized = normalize_kpics_url(htmlmod.unescape(candidate).strip())
        if normalized:
            return normalized
    return None


def extract_cdn(html: str) -> list[str]:
    if is_cloudflare_challenge(html):
        return []
    out: set[str] = set()
    # Direct CDN refs: only trusted HTTPS kpics assets survive validation.
    for m in re.findall(r"https?://cdn\.kpopping\.com/kpics/[A-Za-z0-9\-/._]+?\.jpg", html):
        candidate = m.split("\\")[0]
        if is_kpic_asset_url(candidate):
            out.add(candidate)
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
        # Fallback ternormalisasi: abaikan spasi/tanda baca
        # (mis. "le sserafim" -> lesserafim-api).
        nhint = re.sub(r"[^a-z0-9]+", "", hint)
        if nhint:
            for d in sorted(glob.glob("*-api")):
                ndir = re.sub(r"[^a-z0-9]+", "", d.lower())
                if nhint in ndir and os.path.isdir(d):
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
    Jika tidak cocok dan tidak ambiguous: append entry baru {title, [api_url,] photo_collection}.
    Match ambiguous dilewati agar tidak salah tempel. Mengembalikan ringkasan
    {updated, appended, total, ambiguous, unmatched}.
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
        if url in ambiguous:
            print(f"{url} -> SKIPPED ambiguous title match", file=sys.stderr)
            continue
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

    raw_urls = list(args.urls)
    if args.input:
        with open(args.input, encoding="utf-8") as f:
            raw_urls += [l.strip() for l in f if l.strip()]
    normalized_urls = [normalize_kpics_url(u) or u for u in raw_urls]
    urls = []
    seen_urls = set()
    for url in normalized_urls:
        if url not in seen_urls:
            seen_urls.add(url)
            urls.append(url)

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

    # Pasangan URL <-> file HTML lokal. File lokal harus punya canonical/
    # og:url Kpopping yang tervalidasi dan cocok dengan URL input; ini
    # mencegah HTML slug A diterapkan ke entry slug B.
    paired = {}
    fetch_urls = list(urls)
    valid_urls = {
        normalized for normalized in (normalize_kpics_url(u) for u in urls)
        if normalized is not None
    }
    for hf in html_paths:
        document_url = extract_canonical_url(html_contents[hf])
        if document_url is None:
            print(
                f"--html-file tanpa canonical/og:url Kpopping tervalidasi: {hf}",
                file=sys.stderr,
            )
            return 2
        if urls and document_url not in valid_urls:
            print(
                f"--html-file tidak cocok dengan URL input: {hf} "
                f"({document_url})",
                file=sys.stderr,
            )
            return 2
        if document_url in paired:
            print(f"duplikasi canonical URL pada --html-file: {document_url}",
                  file=sys.stderr)
            return 2
        paired[document_url] = hf
    for u in paired:
        if u in fetch_urls:
            fetch_urls.remove(u)

    items: dict[str, dict] = {}
    blocked: list[str] = []
    empty: list[str] = []

    def ingest(u: str, html: str, source: str,
               status: int = 200, error: str = "") -> None:
        if status != 200 or error or is_cloudflare_challenge(html):
            blocked.append(u)
            items[u] = {"title": slug_humanize(u), "photos": []}
            reason = f"http={status}" if status != 200 else (error or "cloudflare")
            print(f"{u} <- {source} BLOCKED ({reason}) photos=0",
                  file=sys.stderr)
            return

        document_url = extract_canonical_url(html)
        if document_url != normalize_kpics_url(u):
            blocked.append(u)
            items[u] = {"title": slug_humanize(u), "photos": []}
            print(f"{u} <- {source} BLOCKED (canonical/og:url tidak cocok) photos=0",
                  file=sys.stderr)
            return

        embedded = extract_embedded_photo_item(html, u)
        if embedded is None:
            blocked.append(u)
            items[u] = {"title": slug_humanize(u), "photos": []}
            print(f"{u} <- {source} BLOCKED (initialData.albumImages tidak valid) photos=0",
                  file=sys.stderr)
            return

        items[u] = embedded
        if not embedded["photos"]:
            empty.append(u)
        print(f"{u} <- {source} photos={len(embedded['photos'])}", file=sys.stderr)

    for i, u in enumerate(fetch_urls):
        if build_photo_api_url(u) is None:
            blocked.append(u)
            items[u] = {"title": slug_humanize(u), "photos": []}
            print(f"{u} <- invalid kpopping URL photos=0", file=sys.stderr)
        else:
            api_item = fetch_photo_api(u)
            if api_item is not None:
                items[u] = api_item
                if not api_item["photos"]:
                    empty.append(u)
                print(f"{u} <- api /api/photos photos={len(api_item['photos'])}",
                      file=sys.stderr)
            else:
                html, status, error = fetch_html_response(u)
                ingest(u, html, "fetch html", status=status, error=error)
        if i < len(fetch_urls) - 1 or paired:
            time.sleep(args.delay)
    for u, hf in paired.items():
        ingest(u, html_contents[hf], f"local {hf}")

    photos_only = {u: v["photos"] for u, v in items.items()}
    payload = {
        "items": items,
        "photos": photos_only,
        "blocked": blocked,
        "empty": empty,
    }
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    elif not args.apply:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    applied = None
    target = None
    if args.apply:
        target = resolve_content_file(args.app, args.constanta)
        # Jangan mutasi gallery dengan hasil blocked/kosong. apply_to_gallery
        # hanya dipanggil bila ada item yang benar-benar berisi foto.
        blocked_set = set(blocked)
        empty_set = set(empty)
        apply_items = {
            u: v for u, v in items.items()
            if u not in blocked_set and u not in empty_set
        }
        if apply_items:
            applied = apply_to_gallery(
                target,
                apply_items,
                keep_api_url=not args.drop_api_url,
                update_title=args.update_title,
            )
        else:
            applied = {"updated": 0, "appended": 0, "total": None}
        skipped_blocked = [u for u in items if u in blocked_set]
        skipped_empty = [u for u in items if u in empty_set]
        if skipped_blocked:
            applied["skipped_blocked"] = skipped_blocked
            print(f"SKIPPED blocked (tidak dimutasi): {len(skipped_blocked)}", file=sys.stderr)
        if skipped_empty:
            applied["skipped_empty"] = skipped_empty
            print(f"SKIPPED empty (tidak dimutasi): {len(skipped_empty)}", file=sys.stderr)

    for u, v in items.items():
        print(f"{u} -> title={v['title']!r} photos={len(v['photos'])}", file=sys.stderr)
    if blocked:
        print(f"BLOCKED: {len(blocked)}", file=sys.stderr)
    if empty:
        print(f"EMPTY (tidak diterapkan): {len(empty)}", file=sys.stderr)
    if target:
        print(f"TARGET: {target} applied={applied}", file=sys.stderr)
    has_ambiguous = bool(args.apply and applied and applied.get("ambiguous"))
    return 1 if blocked or empty or has_ambiguous else 0


if __name__ == "__main__":
    raise SystemExit(main())
