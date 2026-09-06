# fandom-kpop

K-Pop Fandom Hub landing page. Source design: Google Stitch project `8311142084328686506` (Markdown Landing Page Generator).

Live via GitHub Pages: `https://<username>.github.io/web-fandom-kpop/` -> `index.html`.

## Pages
- `index.html` — desktop landing (Stitch screen `a13d5b35a9c94da3a23b538f35e28f29`), responsive, Tailwind CDN
- `mobile.html` — mobile variant (Stitch screen `ef69bef1f6734c7ca967d1c14d7c0a50`)
- `assets/logo.svg` — logo (Stitch screen `2c97e60d5f634cd3936285d223d587a9`)
- `assets/img/` — local copy of remote Stitch images (logo, hero)
- `DESIGN.md` — design system Galactic Idol Stage + tokens
- `stitch_raw/` — raw Stitch downloads (html, md, screenshots)

## Run local
```bash
python3 -m http.server 8000
# open http://localhost:8000
```

## Deploy GitHub Pages
1. Push repo to GitHub.
2. Settings > Pages > Deploy from branch > `main` / root.
3. Open `https://<username>.github.io/<repo>/`.

`.nojekyll` present so `assets/` served as-is.
