# CTA Constata — Announcement Lightbox

> Sumber: `ADS.md` §13, `types/content.ts`, `UI/content/announcement.ts`, `UI/screens/HomeScreen.tsx`.

## 1. Kontrak

Key `announcement` di `API_ENDPOINT_CONTENT`. Validasi `validateAnnouncement()`:

- Wajib: `id` + `title` (trimmed, non-empty). Invalid/absen = `null` = no popup.
- Opsional degradasi ke empty: `badge`, `description`, `image`, `start_date`, `end_date`.
- `rewards`: array, filter `text` non-empty, cap 3 (`ANNOUNCEMENT_MAX_REWARDS`). Display-only, tanpa claim logic.
- `cta.action`: `'open_page'` (default) | `'open_url'`. Nilai lain = fallback `open_page`.
- `cta.page`: harus ada di registry, selain itu = `undefined` (CTA jadi no-op, lightbox hanya ditutup).
- `cta.params`: object string map saja (`Record<string,string>`), else `undefined`.
- `cta.url`: trimmed, empty = `undefined`.
- Show rule `shouldShowAnnouncement()`: ada `id` + belum ada di `seenIds` (`announcementStore`, persist `announcement-storage`).
- Trigger `HomeScreen`: mount + delay 1200ms, sekali per mount. CTA engage = close + `markSeen(id)` dulu baru navigasi.

## 2. Registry `AnnouncementPage`

| `page` | Target | `params` | Handler (`HomeScreen.handleAnnouncementCta`) |
|---|---|---|---|
| `Trivia` | `openGame()` (GameModal) | — | langsung `openGame()` |
| `Event` | stack `Event` | `{ "eventId": "<id>" }` | `navigate('Event', params)` |
| `NewsDetail` | stack `NewsDetail` | `{ "articleId": "<id>" }` | `navigate('NewsDetail', params)` |
| `MemberProfile` | stack `MemberProfile` | `{ "name": "<member name>" }` | `navigate('MemberProfile', params)`, resolve case-insensitive ke `bandDetail.members` |
| `NowPlaying` | stack `NowPlaying` | — | `navigate('NowPlaying', {})` |
| `FullLyrics` | stack `FullLyrics` | — | `navigate('FullLyrics', {})` |
| `Library` | tab `Library` | — | `navigate('MainTabs', { screen: 'Library' })` |
| `Home` | — (no-op) | — | close saja |
| `Gallery` | tab `Gallery` | — | ⚠️ ada di `types/content.ts` tapi belum di `PAGES` validator → saat ini di-drop jadi `undefined` |

## 3. Sample payload penuh

```json
{
  "announcement": {
    "id": "trivia-launch-01",
    "badge": "✨ What's New",
    "title": "Guess The Lyrics Trivia",
    "description": "Test your skills in quick lyric rounds!",
    "image": "https://example.com/hero.jpg",
    "rewards": [
      { "icon": "timer", "text": "2 free runs every day" },
      { "icon": "trophy", "text": "Top scores on this device" }
    ],
    "cta": {
      "label": "Play Trivia Now",
      "action": "open_page",
      "page": "Trivia"
    }
  }
}
```

## 4. Varian `cta` (`open_page`)

```json
{ "label": "Play Now", "action": "open_page", "page": "Trivia" }
{ "label": "Join Event", "action": "open_page", "page": "Event", "params": { "eventId": "summer-race-01" } }
{ "label": "Read News", "action": "open_page", "page": "NewsDetail", "params": { "articleId": "aespa-kiss-n-tell-2026" } }
{ "label": "View Profile", "action": "open_page", "page": "MemberProfile", "params": { "name": "Karina" } }
{ "label": "Open Library", "action": "open_page", "page": "Library" }
{ "label": "Open Player", "action": "open_page", "page": "NowPlaying" }
{ "label": "View Lyrics", "action": "open_page", "page": "FullLyrics" }
{ "label": "Got It", "action": "open_page", "page": "Home" }
```

## 5. Pembanding `open_url`

```json
{
  "label": "Download Now",
  "action": "open_url",
  "url": "https://play.google.com/store/apps/details?id=com.babymonster.lyrics"
}
```

Gagal `Linking.openURL()` = popup error `Failed to open link.`.
