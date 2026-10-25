#!/usr/bin/env python3
"""Download gallery photo_collection ke direktori aset lokal + rewrite opsional.

Membaca <api_dir>/*-content.json (mapping via constanta.json, lihat
extract_kpics.resolve_content_file), mengunduh tiap URL photo_collection ke:

  <asset-dir>/<slug-title>/<nama-file>.<ext-asli>

lalu bila --rewrite-base diberikan, photo_collection ditulis ulang menjadi:

  <base>/<asset-dir>/<slug-title>/<nama-file>.jpg

Contoh base GitHub Pages: https://fandomkpopuk-bot.github.io
sehingga menjadi https://fandomkpopuk-bot.github.io/cortis-asset/<slug>/<file>

Mode WebP (--to-webp): file disimpan sebagai .webp (nama sama, ekstensi
diganti: xxx.jpg -> xxx.webp, yyy.png -> yyy.webp), rewrite menunjuk
ke .webp. Sumber yang sudah .webp dipakai apa adanya tanpa konversi.
Butuh Pillow
(pip install pillow); fallback ke cwebp/ffmpeg bila ada.

Aturan:
- Idempotent: file lokal yang sudah ada (>0 byte, magic valid) dilewati.
- Sumber valid: magic JPEG, PNG, atau WebP (sumber WebP dipakai apa adanya,
  tanpa konversi ulang, cukup rename/salin ke nama final .webp).
- Bila --to-webp dan file sumber sudah ada tapi .webp belum: konversi langsung
  tanpa download ulang.
- Tabrakan nama (mis. foo.jpg vs foo.png -> foo.webp) diberi suffix -2, -3.
- Rewrite HANYA untuk URL yang file lokalnya terbukti ada; sisanya
  dipertahankan agar tidak tercipta link mati.
- Jangan pernah git commit dari script ini.
- Jangan menebak URL: nama file = basename URL asli (ekstensi .webp bila
  --to-webp).

Usage:
  python3 download_assets.py --app CORTIS --dry-run
  python3 download_assets.py --app CORTIS
  python3 download_assets.py --app CORTIS --rewrite-base https://fandomkpopuk-bot.github.io
  python3 download_assets.py --app CORTIS --to-webp --rewrite-base https://fandomkpopuk-bot.github.io --delay 0.5
  python3 download_assets.py --app CORTIS --to-webp --quality 75 --keep-jpg
  python3 download_assets.py --app CORTIS --to-webp --rewrite-base https://fandomkpopuk-bot.github.io --cookies /tmp/cookies.txt

Bila cdn.kpopping.com memblokir curl (Cloudflare 403), ekspor cookies
dari browser asli (ekstensi "Get cookies.txt", setelah halaman lolos
challenge) lalu pakai --cookies. Token cf_clearance berlaku
jam-hari; curl memakai cookie browser sehingga download massal tembus.
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time

SPEC = importlib.util.spec_from_file_location(
    "kpics_extract",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "extract_kpics.py"),
)
KX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(KX)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def slugify(t: str) -> str:
    s = (t or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "untitled"


def default_asset_dir(api_dir: str) -> str:
    base = api_dir[:-4] if api_dir.endswith("-api") else api_dir
    return f"{base}-asset"


def is_jpeg(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(3) == b"\xff\xd8\xff"
    except OSError:
        return False


def is_png(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(8) == b"\x89PNG\r\n\x1a\n"
    except OSError:
        return False


def is_supported_source(path: str) -> bool:
    """File sumber valid: magic JPEG, PNG, atau WebP."""
    return is_jpeg(path) or is_png(path) or is_webp(path)


def is_webp(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(12)
        return (len(head) == 12 and head[0:4] == b"RIFF"
                and head[8:12] == b"WEBP")
    except OSError:
        return False


def is_valid_image(path: str, to_webp: bool = False) -> bool:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    if to_webp:
        return is_webp(path)
    return is_supported_source(path)


def webp_path_for(jpg_path: str) -> str:
    stem, _ = os.path.splitext(jpg_path)
    return stem + ".webp"


def build_plan(gallery, asset_abs, asset_dir, to_webp, rewrite_base):
    """Bangun (idx, entry, url, src_local, final_local, pages_url).

    final_local collision-safe: dua URL berbeda yang basename-nya memetakan
    ke file lokal yang sama (mis. foo.jpg vs foo.png -> foo.webp) diberi
    suffix -2, -3 agar tidak saling menimpa. Mapping deterministik sehingga
    fase download dan rewrite selalu sepakat.
    """
    plan = []
    used: dict[str, str] = {}
    for idx, e in enumerate(gallery):
        sub = slugify(e.get("title", ""))
        for url in e.get("photo_collection", []):
            fname = url.rstrip("/").split("/")[-1].split("?")[0]
            src_local = os.path.join(asset_abs, sub, fname)
            if to_webp and not url.rstrip("/").lower().endswith(".webp"):
                stem, _ = os.path.splitext(fname)
                final_local = os.path.join(asset_abs, sub, stem + ".webp")
            else:
                # Tanpa --to-webp, atau sumber sudah .webp: pakai apa adanya
                # (tidak ada konversi; hanya rename ke nama final).
                final_local = src_local
            base_stem, base_ext = os.path.splitext(os.path.basename(final_local))
            n = 2
            while final_local in used and used[final_local] != url:
                final_local = os.path.join(
                    asset_abs, sub, f"{base_stem}-{n}{base_ext}")
                n += 1
            used[final_local] = url
            pages = None
            if rewrite_base:
                pages = (f"{rewrite_base.rstrip('/')}/{asset_dir}/{sub}/"
                         f"{os.path.basename(final_local)}")
            plan.append((idx, e, url, src_local, final_local, pages))
    return plan


def convert_to_webp(src: str, dst: str, quality: int = 80) -> bool:
    """Konversi src (JPEG/PNG) -> dst (WebP). Coba Pillow, lalu cwebp, lalu ffmpeg."""
    # 1. Pillow (utama, cross-platform)
    try:
        from PIL import Image
        im = Image.open(src)
        if im.mode in ("RGBA", "LA"):
            pass  # webp dukung alpha, biarkan
        elif im.mode != "RGB":
            im = im.convert("RGB")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im.save(dst, "WEBP", quality=quality, method=6)
        if os.path.exists(dst) and is_webp(dst):
            return True
    except ImportError:
        pass
    except Exception as e:
        print(f"WARN pillow convert gagal {src}: {e}", file=sys.stderr)
    # 2. cwebp (binary webp, bila terinstal via brew/apt)
    if shutil.which("cwebp"):
        tmp = dst + ".part"
        r = subprocess.run(
            ["cwebp", "-q", str(quality), src, "-o", tmp],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            os.replace(tmp, dst)
            return True
        try:
            os.remove(tmp)
        except OSError:
            pass
    # 3. ffmpeg (fallback umum)
    if shutil.which("ffmpeg"):
        tmp = dst + ".part"
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", src,
             "-c:v", "libwebp", "-quality", str(quality), tmp],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and os.path.exists(tmp) and is_webp(tmp):
            os.replace(tmp, dst)
            return True
        try:
            os.remove(tmp)
        except OSError:
            pass
    return False


def download(url: str, path: str, referer: str = "https://kpopping.com/",
             cookies: str | None = None) -> bool:
    tmp = path + ".part"
    cmd = ["curl", "-sL", "-A", UA, "-H", f"Referer: {referer}"]
    if cookies:
        cmd += ["-b", cookies]
    cmd += ["-m", "40", "--retry", "2", "-o", tmp,
            "-w", "%{http_code} %{size_download}", url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    meta = (r.stdout or "").strip()
    code = meta.split()[0] if meta else "000"
    ok = code == "200" and os.path.exists(tmp) and is_supported_source(tmp)
    if ok:
        os.replace(tmp, path)
    else:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True,
                    help="Petunjuk app untuk mapping via constanta.json")
    ap.add_argument("--constanta", default="constanta.json")
    ap.add_argument("--asset-dir", default=None,
                    help="Direktori aset relatif repo root (default: <app>-asset)")
    ap.add_argument("--rewrite-base", default=None,
                    help="Base URL Pages, mis. https://fandomkpopuk-bot.github.io")
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--to-webp", action="store_true",
                    help="Simpan sebagai .webp (butuh Pillow: pip install pillow)")
    ap.add_argument("--quality", type=int, default=80,
                    help="Kualitas WebP 1-100 (default: 80)")
    ap.add_argument("--keep-jpg", action="store_true",
                    help="Dengan --to-webp: pertahankan file sumber asli "
                         "di samping .webp")
    ap.add_argument("--cookies", default=None,
                    help="File cookies Netscape (ekspor browser via Get cookies.txt) "
                         "agar download lolos Cloudflare")
    args = ap.parse_args()

    if args.cookies and not os.path.exists(args.cookies):
        print(f"--cookies tidak ada: {args.cookies}", file=sys.stderr)
        return 2

    if args.to_webp and not (1 <= args.quality <= 100):
        print("--quality harus 1-100", file=sys.stderr)
        return 2
    if args.to_webp:
        try:
            import PIL  # noqa: F401
        except ImportError:
            if not shutil.which("cwebp") and not shutil.which("ffmpeg"):
                print("ERROR --to-webp butuh Pillow (pip install pillow) "
                      "atau binary cwebp/ffmpeg.", file=sys.stderr)
                return 2
            print("WARN Pillow tidak ada, fallback ke "
                  + ("cwebp" if shutil.which("cwebp") else "ffmpeg"),
                  file=sys.stderr)

    target = KX.resolve_content_file(args.app, args.constanta)
    api_dir = os.path.dirname(target)
    asset_dir = args.asset_dir or default_asset_dir(os.path.basename(api_dir))
    asset_abs = os.path.join(os.getcwd(), asset_dir)

    data = json.load(open(target, encoding="utf-8"))
    gallery = data.get("gallery", [])

    plan = build_plan(gallery, asset_abs, asset_dir,
                      args.to_webp, args.rewrite_base)

    if args.dry_run:
        mode = "webp" if args.to_webp else "jpg"
        print(f"TARGET: {target} ASSET: {asset_dir}/ mode={mode} "
              f"entries={len(gallery)} files={len(plan)}")
        for title in sorted({e.get("title") for _, e, _, _, _, _ in plan}):
            n = sum(1 for _, e, _, _, _, _ in plan if e.get("title") == title)
            print(f"  {slugify(title)}/ <- '{title}' ({n} files)")
        if args.rewrite_base and plan:
            *_, sample = plan[0]
            print(f"  sample rewrite: {sample}")
        return 0

    ok, fail, skip, converted = 0, [], 0, 0
    for i, (idx, e, url, src_local, final_local, pages) in enumerate(plan, 1):
        if is_valid_image(final_local, to_webp=args.to_webp):
            skip += 1
            continue
        os.makedirs(os.path.dirname(final_local), exist_ok=True)
        if args.to_webp:
            # Sumber sudah .webp: unduh apa adanya tanpa konversi.
            if url.rstrip("/").lower().endswith(".webp"):
                if download(url, final_local, cookies=args.cookies):
                    ok += 1
                    print(f"[{i}/{len(plan)}] OK {final_local} (webp passthrough)",
                          flush=True)
                else:
                    fail.append(url)
                    print(f"[{i}/{len(plan)}] FAIL {final_local}", flush=True)
                time.sleep(args.delay)
                continue
            # Konversi dari file sumber yang sudah ada tanpa download ulang
            if is_jpeg(src_local) or is_png(src_local):
                if convert_to_webp(src_local, final_local, args.quality):
                    converted += 1
                    if not args.keep_jpg:
                        try:
                            os.remove(src_local)
                        except OSError:
                            pass
                    print(f"[{i}/{len(plan)}] CONVERT {final_local}", flush=True)
                    time.sleep(0.05)
                    continue
                # konversi gagal -> download ulang di bawah
            if download(url, src_local, cookies=args.cookies):
                if convert_to_webp(src_local, final_local, args.quality):
                    converted += 1
                    ok += 1
                    if not args.keep_jpg:
                        try:
                            os.remove(src_local)
                        except OSError:
                            pass
                    print(f"[{i}/{len(plan)}] OK {final_local}", flush=True)
                else:
                    fail.append(url)
                    print(f"[{i}/{len(plan)}] FAIL-convert {src_local}", flush=True)
            else:
                fail.append(url)
                print(f"[{i}/{len(plan)}] FAIL {src_local}", flush=True)
            time.sleep(args.delay)
        else:
            if download(url, src_local, cookies=args.cookies):
                ok += 1
            else:
                fail.append(url)
            print(f"[{i}/{len(plan)}] {'OK' if url not in fail else 'FAIL'} {src_local}", flush=True)
            time.sleep(args.delay)

    rewritten = 0
    if args.rewrite_base:
        by_entry: dict[int, list] = {}
        for idx, _e, url, _src, final_local, pages in plan:
            by_entry.setdefault(idx, []).append((url, final_local, pages))
        for idx, e in enumerate(gallery):
            new_coll = []
            for url in e.get("photo_collection", []):
                match = next((x for x in by_entry.get(idx, [])
                              if x[0] == url), None)
                if (match is not None
                        and is_valid_image(match[1], to_webp=args.to_webp)):
                    new_coll.append(match[2])
                    rewritten += 1
                else:
                    new_coll.append(url)  # file belum ada: jangan bikin link mati
            e["photo_collection"] = new_coll
        json.dump(data, open(target, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    print(f"DONE ok={ok} skip={skip} converted={converted} "
          f"fail={len(fail)} rewritten={rewritten}")
    for u in fail:
        print(f"FAIL {u}")
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
