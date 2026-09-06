# DESIGN.md - K-Pop Fandom Hub

Source: Google Stitch project `projects/8311142084328686506` / Title: Markdown Landing Page Generator
Design system asset: `assets/7eb4a02f1e7d464192aeb344c3c5fc77` / Display: Galactic Idol Stage

Screens:
- K-Pop Fandom Hub Landing Page (desktop, a13d5b35a9c94da3a23b538f35e28f29) -> index.html
- K-Pop Fandom Hub (Mobile) (ef69bef1f6734c7ca967d1c14d7c0a50) -> mobile.html
- K-Pop Hub Logo (2c97e60d5f634cd3936285d223d587a9) -> assets/logo.svg
- landingpage.md (13468576152718652742) -> stitch_raw/landingpage.md

## Brand & Style

This design system channels the electrifying, hyper-sensory atmosphere of a modern Seoul arena concert: an ocean of coordinated lightsticks surging against deep galactic stadium shadows. Designed for passionate global K-Pop enthusiasts who prioritize immediacy, emotional connection, and visual spectacle, the visual tone blends high-tech entertainment with warm fan community culture.

The design movement combines **Glassmorphism** with **High-Contrast Neon Cyber-Aesthetics**:
- Deep cosmic violet and abyssal navy canvases create high depth without harsh pitch-black sterility.
- Multi-dimensional, frosted glass cards float smoothly above subtle dynamic radial spotlights.
- Chromatic neon accents—electric purple, hyper-pink, and laser cyan—guide the eye with the punchy urgency of stage pyrotechnics and comeback countdowns.
- Clean, energetic geometric sans typography bridges global Western streaming UI with ultra-modern East Asian entertainment typography.

## Layout & Spacing

A disciplined 8pt spatial cadence structures content density across devices, shifting from compact single-column mobile cards to multi-column idol gallery grids on wide screens.

- **Grid Model:** 12-column dynamic fluid grid on desktop (`>1024px`) with `2rem` gutters; 8-column layout on tablet (`768px - 1023px`) with `1.5rem` gutters; 4-column compact stacked viewport on mobile (`<767px`) with `1rem` gutters.
- **Card Distribution:** Group app cards align to 3 columns on standard desktop (span-4), 2 columns on tablet (span-4 of 8), and single-column full-width carousels/stacks on mobile devices.
- **Safe Vertical Air:** Ample `3rem` to `4.5rem` section buffers prevent neon UI fatigue and isolate card clusters visually.

## Elevation & Depth

Visual hierarchy is constructed through translucent surface tiers and tinted ambient glow rather than flat grey shadows.

- **Level 0 (Stage Floor):** Base canvas `#0B0819` with fixed ambient radial gradient spots (`rgba(139, 92, 246, 0.12)` at top-center and `rgba(236, 72, 153, 0.08)` at bottom-right).
- **Level 1 (Glass Cards):** Background `rgba(30, 23, 71, 0.55)`, `backdrop-filter: blur(16px)`, with a crisp `1px` gradient border: `linear-gradient(135deg, rgba(255,255,255,0.18) 0%, rgba(139,92,246,0.3) 50%, rgba(255,255,255,0.03) 100%)`.
- **Level 2 (Hover & Highlighted Hubs):** Surface lifts with `transform: translateY(-4px)`, increasing backdrop blur to `24px`. Casts an ambient dual-layer shadow: `0 12px 32px -8px rgba(11, 8, 25, 0.8), 0 0 24px -4px rgba(139, 92, 246, 0.25)`.
- **Level 3 (Modals, Overlays & Sticky Navbars):** Solidified glass `rgba(19, 14, 46, 0.85)` with `backdrop-filter: blur(28px)` and a continuous neon edge line at `rgba(236, 72, 153, 0.2)`.

## Components

### Buttons
- **Primary Action (Download Now):** Pill-shaped (`rounded-full`), styled with a sweeping diagonal gradient from `#9333EA` through `#EC4899`. White typography in `label-lg`, accompanied by a trailing neon pulse arrow. Default state has a soft outer glow (`0 0 20px rgba(236, 72, 153, 0.35)`), brightening to `0 0 28px rgba(236, 72, 153, 0.6)` on hover.
- **Secondary / Ghost Buttons:** High-gloss border (`1px solid rgba(139, 92, 246, 0.4)`), deep violet translucent body (`rgba(30, 23, 71, 0.6)`), text in `#F8FAFC`.

### Fandom Name Chips & Badges
- Pill-shaped tags displaying group-specific sub-identities (`ATINY`, `NSWER`, `MY`, `ARMY`, `BLINK`, `STAY`, `ONCE`, `BUNNIES`).
- Features a semi-translucent tinted fill matching the fandom's signature hue at 15% opacity, a matching `1px` outer rim, and uppercase typography using `label-md`. Includes a miniature neon indicator dot (`6px`) before the label.

### Glassmorphic Group Hub Cards
- Built using Level 1 Glassmorphism. Houses the artist emblem/photo banner, artist title, localized fandom badge, descriptive update snippet, and standard Google Play/App Store quick links.
- Transitions seamlessly to a subtle gradient stroke on hover, highlighting the specific group's signature neon hue.

### Input Fields & Search Bars
- Glassmorphic trough (`rgba(19, 14, 46, 0.7)`), `rounded-full`, with inner shadow depth.
- Border shifts from soft slate-violet (`rgba(148, 163, 184, 0.15)`) to electric violet glow (`#8B5CF6`) upon focus, showing an animated neon search cursor.

### Store Download Badges
- Hybrid card badges optimized for mobile and web surfaces: sleek black-violet pill casing containing an official store vector icon, paired with dual-tier typography (`label-sm` for "GET IT ON", `label-lg` for "Google Play").

---

## Tokens (project designMd)

```yaml
---
name: Galactic Idol Stage
colors:
  surface: '#141122'
  surface-dim: '#141122'
  surface-bright: '#3a374a'
  surface-container-lowest: '#0f0c1d'
  surface-container-low: '#1c192b'
  surface-container: '#201d2f'
  surface-container-high: '#2b283a'
  surface-container-highest: '#363245'
  on-surface: '#e6dff8'
  on-surface-variant: '#cbc3d7'
  inverse-surface: '#e6dff8'
  inverse-on-surface: '#322e41'
  outline: '#958ea0'
  outline-variant: '#494454'
  surface-tint: '#d0bcff'
  primary: '#d0bcff'
  on-primary: '#3c0091'
  primary-container: '#a078ff'
  on-primary-container: '#340080'
  inverse-primary: '#6d3bd7'
  secondary: '#ffb0cd'
  on-secondary: '#640039'
  secondary-container: '#aa0266'
  on-secondary-container: '#ffbad3'
  tertiary: '#4cd7f6'
  on-tertiary: '#003640'
  tertiary-container: '#009eb9'
  on-tertiary-container: '#002f38'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e9ddff'
  primary-fixed-dim: '#d0bcff'
  on-primary-fixed: '#23005c'
  on-primary-fixed-variant: '#5516be'
  secondary-fixed: '#ffd9e4'
  secondary-fixed-dim: '#ffb0cd'
  on-secondary-fixed: '#3e0022'
  on-secondary-fixed-variant: '#8c0053'
  tertiary-fixed: '#acedff'
  tertiary-fixed-dim: '#4cd7f6'
  on-tertiary-fixed: '#001f26'
  on-tertiary-fixed-variant: '#004e5c'
  background: '#141122'
  on-background: '#e6dff8'
  surface-variant: '#363245'
  surface-deep: '#0B0819'
  surface-stage: '#130E2E'
  surface-elevated: '#1E1747'
  accent-purple-core: '#9333EA'
  accent-pink-neon: '#EC4899'
  accent-cyan-laser: '#06B6D4'
  fandom-atiny-gold: '#F59E0B'
  fandom-blink-pink: '#F43F5E'
  fandom-army-purple: '#A855F7'
  fandom-dive-blue: '#38BDF8'
  text-primary: '#F8FAFC'
  text-secondary: '#94A3B8'
  text-muted: '#64748B'
typography:
  headline-hero:
    fontFamily: Plus Jakarta Sans
    fontSize: 56px
    fontWeight: '800'
    lineHeight: 64px
    letterSpacing: -0.03em
  headline-hero-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 36px
    fontWeight: '800'
    lineHeight: 42px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 34px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
  label-lg:
    fontFamily: Space Grotesk
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 18px
    letterSpacing: 0.06em
  label-md:
    fontFamily: Space Grotesk
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.08em
  label-sm:
    fontFamily: Space Grotesk
    fontSize: 10px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.1em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  space-xxs: 0.25rem
  space-xs: 0.5rem
  space-sm: 0.75rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
  space-2xl: 3rem
  space-3xl: 4.5rem
  gutter-mobile: 1rem
  gutter-tablet: 1.5rem
  gutter-desktop: 2rem
  margin-mobile: 1.25rem
  margin-tablet: 2rem
  margin-desktop: 3.5rem
---

## Brand & Style

This design system channels the electrifying, hyper-sensory atmosphere of a modern Seoul arena concert: an ocean of coordinated lightsticks surging against deep galactic stadium shadows. Designed for passionate global K-Pop enthusiasts who prioritize immediacy, emotional connection, and visual spectacle, the visual tone blends high-tech entertainment with warm fan community culture.

The design movement combines **Glassmorphism** with **High-Contrast Neon Cyber-Aesthetics**:
- Deep cosmic violet and abyssal navy canvases create high depth without harsh pitch-black sterility.
- Multi-dimensional, frosted glass cards float smoothly above subtle dynamic radial spotlights.
- Chromatic neon accents—electric purple, hyper-pink, and laser cyan—guide the eye with the punchy urgency of stage pyrotechnics and comeback countdowns.
- Clean, energetic geometric sans typography bridges global Western streaming UI with ultra-modern East Asian entertainment typography.

## Colors

The system is strictly calibrated for dark-mode immersion, preserving eye comfort during extended late-night streaming sessions while maximizing the luminescence of key fandom signifiers.

### Architectural Canvas
- **Deep Space Base (`#0B0819`):** The foundational backdrop, enriched with slight indigo pigment to avoid flat desaturated blacks.
- **Stage Tier (`#130E2E`):** Used for large sectional containers, drawers, and nested navigation shells.
- **Glass Panel Surface (`#1E1747` at 65% opacity):** Frosted glass backgrounds supporting vibrant badges and download CTA actions.

### Chromatic Lightstick Accents
- **Primary Electric Violet (`#8B5CF6`):** Drives primary user action points, active indicators, and high-level navigational state changes.
- **Secondary Neon Pink (`#EC4899`):** Represents high-energy live moments, trending status, and community heat tags.
- **Tertiary Cyan Laser (`#06B6D4`):** Used for platform utility actions (downloads, update indicators, streaming feeds).
- **Fandom Badges:** Pre-allocated semantic colors represent official group identities without compromising WCAG AAA legibility against deep glass cards.

## Typography

The type system pairs **Plus Jakarta Sans** for core editorial authority with **Space Grotesk** for fandom markers, meta chips, and micro-labels.

- **Headlines:** Set in `Plus Jakarta Sans` at 700 to 800 weight with tight negative letter-spacing, providing energetic, poster-like authority reminiscent of album sleeves and festival promotions.
- **Body:** Open counters and clear terminal designs in `Plus Jakarta Sans` maintain crisp reading clarity on AMOLED and mobile glass surfaces against dark backgrounds.
- **Micro & Labels:** `Space Grotesk` introduces a futuristic, tracklist-styled edge for fandom tags (e.g., `[ATINY]`, `[BLINK]`, `[VERIFIED]`), metadata counters, and CTA download telemetry.

## Layout & Spacing

A disciplined 8pt spatial cadence structures content density across devices, shifting from compact single-column mobile cards to multi-column idol gallery grids on wide screens.

- **Grid Model:** 12-column dynamic fluid grid on desktop (`>1024px`) with `2rem` gutters; 8-column layout on tablet (`768px - 1023px`) with `1.5rem` gutters; 4-column compact stacked viewport on mobile (`<767px`) with `1rem` gutters.
- **Card Distribution:** Group app cards align to 3 columns on standard desktop (span-4), 2 columns on tablet (span-4 of 8), and single-column full-width carousels/stacks on mobile devices.
- **Safe Vertical Air:** Ample `3rem` to `4.5rem` section buffers prevent neon UI fatigue and isolate card clusters visually.

## Elevation & Depth

Visual hierarchy is constructed through translucent surface tiers and tinted ambient glow rather than flat grey shadows.

- **Level 0 (Stage Floor):** Base canvas `#0B0819` with fixed ambient radial gradient spots (`rgba(139, 92, 246, 0.12)` at top-center and `rgba(236, 72, 153, 0.08)` at bottom-right).
- **Level 1 (Glass Cards):** Background `rgba(30, 23, 71, 0.55)`, `backdrop-filter: blur(16px)`, with a crisp `1px` gradient border: `linear-gradient(135deg, rgba(255,255,255,0.18) 0%, rgba(139,92,246,0.3) 50%, rgba(255,255,255,0.03) 100%)`.
- **Level 2 (Hover & Highlighted Hubs):** Surface lifts with `transform: translateY(-4px)`, increasing backdrop blur to `24px`. Casts an ambient dual-layer shadow: `0 12px 32px -8px rgba(11, 8, 25, 0.8), 0 0 24px -4px rgba(139, 92, 246, 0.25)`.
- **Level 3 (Modals, Overlays & Sticky Navbars):** Solidified glass `rgba(19, 14, 46, 0.85)` with `backdrop-filter: blur(28px)` and a continuous neon edge line at `rgba(236, 72, 153, 0.2)`.

## Shapes

The design system adopts a confident **Rounded (Level 2)** shape standard:
- Base standard radius is `0.5rem` (8px), scaling to `1rem` (16px) for cards and modals (`rounded-lg`), and `1.5rem` (24px) for hero panels (`rounded-xl`).
- High-interactivity elements such as CTA download triggers, fandom chips, and badge counters use full pill curvature (`rounded-full` / `9999px`) to express tactile friendliness and playful pop energy.
- Inner elements inside glass cards mirror parent radii minus card padding to maintain strict concentric geometry.

## Components

### Buttons
- **Primary Action (Download Now):** Pill-shaped (`rounded-full`), styled with a sweeping diagonal gradient from `#9333EA` through `#EC4899`. White typography in `label-lg`, accompanied by a trailing neon pulse arrow. Default state has a soft outer glow (`0 0 20px rgba(236, 72, 153, 0.35)`), brightening to `0 0 28px rgba(236, 72, 153, 0.6)` on hover.
- **Secondary / Ghost Buttons:** High-gloss border (`1px solid rgba(139, 92, 246, 0.4)`), deep violet translucent body (`rgba(30, 23, 71, 0.6)`), text in `#F8FAFC`.

### Fandom Name Chips & Badges
- Pill-shaped tags displaying group-specific sub-identities (`ATINY`, `NSWER`, `MY`, `ARMY`, `BLINK`, `STAY`, `ONCE`, `BUNNIES`).
- Features a semi-translucent tinted fill matching the fandom's signature hue at 15% opacity, a matching `1px` outer rim, and uppercase typography using `label-md`. Includes a miniature neon indicator dot (`6px`) before the label.

### Glassmorphic Group Hub Cards
- Built using Level 1 Glassmorphism. Houses the artist emblem/photo banner, artist title, localized fandom badge, descriptive update snippet, and standard Google Play/App Store quick links.
- Transitions seamlessly to a subtle gradient stroke on hover, highlighting the specific group's signature neon hue.

### Input Fields & Search Bars
- Glassmorphic trough (`rgba(19, 14, 46, 0.7)`), `rounded-full`, with inner shadow depth.
- Border shifts from soft slate-violet (`rgba(148, 163, 184, 0.15)`) to electric violet glow (`#8B5CF6`) upon focus, showing an animated neon search cursor.

### Store Download Badges
- Hybrid card badges optimized for mobile and web surfaces: sleek black-violet pill casing containing an official store vector icon, paired with dual-tier typography (`label-sm` for "GET IT ON", `label-lg` for "Google Play").
```