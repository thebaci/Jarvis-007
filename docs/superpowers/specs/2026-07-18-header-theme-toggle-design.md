# Design: spread out the header + a deep-dark / soft-dark theme toggle

Date: 2026-07-18
Status: brainstormed + approach approved, waiting for implementation.

## Goals

Two things on the dashboard's header bar (`.hud-top`):

1. The header is "cramped": everything is crowded to the left, with ~414px on the right left
   empty. Spread it out so it is balanced.
2. Add a theme-tone toggle at the right corner of the header: flip between **deep dark**
   (current) and **soft dark** (dim). NO white-background light mode.

## Why the header is crowded

`.hud-top` is a `1fr auto 1fr` grid with 4 children: `.brand`, `.navbar-brain`,
`.hud-center-title`, `.hud-actions`.
On the management pages (`body.in-console`), `.brand` and `.hud-actions` are `display:none` →
auto-placement only places `.navbar-brain` in column 1 and `.hud-center-title` in column 2,
leaving column 3 (1fr, right) wide open. A 4-children-in-3-columns grid is also not robust on
the home screen.

## Design

### Part 1 - Header in 3 clear groups

Wrap the current children into 3 column-fixed groups, replacing the 4 flat children:

```
<header class="hud-top">
  <div class="hud-top-left">   .brand + .navbar-brain (brain select + ➕🗑📁 + graph-stats) </div>
  <div class="hud-top-center"> .hud-center-title (Jarvis 007 + date) </div>
  <div class="hud-top-right">  theme toggle button (ALWAYS visible) + .hud-actions (hidden when in-console) </div>
</header>
```

- `.hud-top { grid-template-columns: 1fr auto 1fr; }` stays; each group occupies exactly 1 column.
- `.hud-top-left { justify-self: start }`, `.hud-top-center { justify-self: center }`, `.hud-top-right { justify-self: end }`.
- A hidden child inside a group (`.brand`, `.hud-actions`) just shrinks by itself; the group
  still holds its column so the layout is balanced in BOTH modes (home and in-console).
- The theme toggle is a DIRECT child of `.hud-top-right` (outside `.hud-actions`) so it is always
  visible, even in-console → it fills exactly the empty right column.

### Part 2 - Theme toggle + the dim tone

- A "contrast" icon button (half light/half dark circle) in `.hud-top-right`, styled after the
  existing `.hud-icon-btn`.
- Click → flip the `data-theme` attribute on `<html>`: absent (default) = deep dark;
  `data-theme="dim"` = soft dark.
- Remember the choice through `localStorage["javis.theme"]`.
- Flash prevention: an inline script RIGHT at the top of `<head>` reads localStorage and sets
  `data-theme` before the CSS paints.

The dim palette (override `:root[data-theme="dim"]` in style.css) - clearly lighter than deep dark:

| Variable | Deep dark (current) | Soft dark (dim) |
|------|--------------------|----------------|
| `--bg`     | `#0e0e16` | `#282a37` |
| `--bg2`    | `#181822` | `#343646` |
| `--bg3`    | `#22222e` | `#414353` |
| `--border` | `#36364c` | `#545872` |
| `--text`   | `#f3f3fb` | `#eef0f7` |
| `--text2`  | `#c0c0da` | `#c2c5d6` |
| `--text3`  | `#9a9ab6` | `#9498ad` |

`--accent`, `--accent2`, `--green`, `--red`, `--yellow`, `--font` stay unchanged (the accent
suits both tones).

## Scope & boundaries

- The tone change only affects surfaces that USE the CSS variables (header, rail, cview, the
  pages, chat, panels). The 3D graph / starfield in the cockpit use hard-coded colors → KEEP the
  dark background as before. Acceptable because both tones are dark, so it looks continuous and
  not jarring. Do not touch graph3d.js/starfield within this scope.
- The rail (console.css) already uses its own variables (`--rail-bg`, `--glass-brd`) + a few
  hard-coded rgba; most of it follows `--text*` so the tone change takes effect on its own.
  Accept that a few hard-coded spots do not change (fine-tune later if needed).
- Mobile: the header uses the same CSS; the 3-group, 3-column layout still works. The theme
  button still shows at the right corner.

## Files touched

- `dashboard/index.html`: wrap the header into 3 groups; add the theme button; add the inline
  anti-flash script at the top of `<head>`.
- `dashboard/style.css`: the 3-group header layout; the `:root[data-theme="dim"]` dim palette;
  button style (reuse `.hud-icon-btn`); bump `?v`.
- Button click handling + saving to localStorage: a small script (inline at the end of body or in
  app.js), attached once.

## Testing

- Home + in-console: the header is balanced, the theme button is always at the right corner, not
  crowded into a clump.
- Click the button: `<html>` changes `data-theme`, the background/panels change tone right away,
  the icon responds, localStorage saves.
- Reload the page: keeps the chosen tone, with no flash of deep dark before switching.
- The cockpit graph keeps a dark background in both tones (no change expected).
