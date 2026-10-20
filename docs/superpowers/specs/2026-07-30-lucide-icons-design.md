# Replace emoji with the Lucide icon set in the dashboard

Date: 2026-07-30
Status: settled, under construction

## Problem

The dashboard uses ~400 emoji pasted directly into HTML strings as icons. Three things are wrong:

1. **Every machine draws its own version.** Emoji are drawn by the system font, so Windows, macOS, Android
   and Linux produce four different shapes. There is no control over the shape.
2. **Hard-coded color, does not follow the theme.** Jarvis 007 has a DARK theme and a LIGHT theme. Emoji do not
   take `color`, so in the light theme they glare and clash with the palette.
3. **Inconsistent strokes.** Colored emoji sitting next to geometric symbols (`✕ ↻ ▾`) produce a
   patchwork look with no sense of a single set.

## Goal

Every icon in the dashboard UI is drawn with Lucide: one stroke set, automatically recolored by the
theme and by the text color where it sits, identical on every machine.

## Scope

**In scope:** `dashboard/index.html`, `dashboard/*.js`, `dashboard/style.css`,
`dashboard/console.css`.

**Out of scope, with reasons:**

- **Obsidian Tasks syntax in .md files** (`📅` due date, `⏫🔼🔽` priority,
  `✅` completion date, `🛫` start date). This is a **data format**, not
  an icon. Changing it breaks compatibility with Obsidian and breaks
  `tests/python/test_dataview_tasks.py`. The **display** of these markers in the UI
  is still switched to icons; only the strings written into the .md file stay unchanged.
- **Emoji in server-side Telegram messages.** Telegram renders emoji consistently on
  every device so there is no display problem, and a message is not the web UI.
- **`dashboard/vendor/`** (other people's code), `dashboard/docs/`, `voice-test.html`
  (a standalone page, not part of the Jarvis 007 UI).

## Approach: vendor a trimmed set + a string-returning function

Three options were weighed:

| Option | Gains | Costs | Verdict |
|---|---|---|---|
| **A. Vendor a trimmed set + `ic()`** | 18.1KB for 102 icons; no network call at runtime; returns exactly the thing the code needs, a string | Needs a code-generation script + manifest | **Chosen** |
| B. Vendor the whole UMD bundle | Any name you type works immediately | 414KB (95% unused); `createIcons()` scans the DOM so it must rescan after every `innerHTML` change, which is slow and easy to miss icons; you still have to write the string-returning function yourself | Rejected |
| C. SVG sprite + `<use>` | Short markup, one shared cached file | An extra network fetch before icons appear (a white flash on page load); `currentColor` with external files has failed on Safari before | Rejected |

The deciding reason: the dashboard builds HTML from template strings (`innerHTML = \`...\``)
everywhere, so the thing needed most is **a function that returns an SVG string**. Option A also fits
the repo's existing habit exactly (a file in `vendor/` + a global variable, no build,
no imports), and this repo has no `package.json`, so a build step cannot be added.

## Architecture

Four parts, one job each:

```
dashboard/icons.manifest.json   source of truth: list of icon names, grouped
        |
        v  python tools/gen_icons.py   (run by hand, needs internet, development only)
        |
dashboard/vendor/lucide-icons.js  GENERATED file, committed to the repo
        |                          window.LucideIcons = { name: svg body }
        v
dashboard/icons.js               API layer: ic() / Icons.msg() / Icons.render()
        |
        v
style.css .ic                    sized at 1em, color currentColor, aligned to the text baseline
```

Why the manifest is separated from the generated file: the generated file must not be edited by hand, but
people need an easy-to-read place to add icons. The manifest is grouped by purpose so lookup is
quick, and the script rejects both duplicate names and names that do not exist.

### Three ways to use it

```js
// 1. Inside a template string - the main way, used the most
html += `<button>${ic("save")} Save</button>`;

// 2. In the static HTML of index.html - Icons.render() substitutes it at page load
<i data-ic="search" class="vs-ico"></i>

// 3. Status messages containing a string from the server - this way is MANDATORY
el.innerHTML = Icons.msg("triangle-alert", r.error);
```

Way 3 is a **security** decision, not a convenience. Many places today are
`el.textContent = "⚠ " + r.error`. `textContent` does not interpret HTML so it is safe
by default. Switching to icons forces a move to `innerHTML`, and `r.error` is a string from the
server - concatenating it directly would open an XSS hole in exactly the places that used to be safe.
`Icons.msg()` escapes the text portion, which shuts that path completely. This is a real risk of this
migration and it must be handled with an API, not with reminders.

### Design decisions

**Data tables hold icon NAMES, not SVG.** `VIEW_META` in console.js is
computed when the file loads. If it said `icon: ic("workflow")` it would call `ic()` right at parse time,
which would force the script load order to be exactly right. With `icon: "workflow"` and `ic()` called
at render time, the table stays readable and the order constraint disappears.

**Icon size is `1em`, not px.** An icon scales with the font size of its container, so
an icon in an 11px button and an icon in an 18px heading are both balanced without declaring a
size at each spot. The stroke gets thinner as the icon grows (`.ic-lg`, `.ic-xl`) because a stroke of 2 at
16px is right but at 32px it is coarse.

**A missing icon must show itself.** A mistyped name is an invisible bug. `ic()` draws a question mark in its
place and calls `console.warn` once per wrong name; a static test catches it at CI time too.

**`<select>` uses `<optgroup>` + plain text.** An `<option>` tag accepts only text, not
SVG. Three places are affected: the brain picker (`📁` distinguishes an external folder - this is
**information**, not decoration, so it becomes
`<optgroup label="External folders">`), the model picker (`✏️` is dropped entirely), and the task priority picker
(`🔺🔼🔽` become the words "High/Medium/Low"). We do not build a custom dropdown: it would have to handle
keyboard, touch and close-on-outside-click itself - too much risk for the brain picker.

**Status lights use `circle` + a color class.** A solid `●` and an empty `○` become
`ic("circle", {cls:"ic-fill ic-ok"})` and `ic("circle")`. A bonus: the light now uses
the color variables, so the light theme automatically gets a darker version, which `🟢🔴⚪` could not do.

## Mapping table

This is not a mechanical character-by-character replacement: the same character means different things depending on where it is.
`✓` in "✓ Saved" is `check`, while `✓` used as a result light is `circle-check`.

### Navigation bar (`VIEW_META` in console.js)

| Old | New | Item |
|---|---|---|
| `⬡` | `hexagon` | Jarvis 007 |
| `💬` | `message-circle` | Chat |
| `🤖` | `bot` | Agents |
| `🧩` | `puzzle` | Skills |
| `⚡` | `workflow` | Workflows |
| `♻` | `repeat` | Scheduled |
| `🔌` | `plug` | Connections |
| `📊` | `chart-column` | Usage |
| `⚙` | `settings` | Settings |
| `◈` | `cpu` | Models |
| `✉` | `mail` | Channels |
| `🗂` | `folder-tree` | Files |
| `🗒` | `scroll-text` | Log |
| `🧰` | `toolbox` | Plugins |

### Buttons and actions

| Old | New | | Old | New |
|---|---|---|---|---|
| `💾` | `save` | | `✕` | `x` |
| `↻` `🔄` | `rotate-cw` | | `▶` | `play` |
| `■` | `circle-stop` | | `🗑` | `trash-2` |
| `✎` `✏` | `pencil` | | `🔍` | `search` |
| `➕` | `plus` | | `⌂` `🏠` | `house` |
| `⬆` | `arrow-up` | | `↗` | `external-link` |
| `⇩` | `download` | | `↩` `↶` | `undo-2` |
| `↓` | `arrow-down` | | `←` | `chevron-left` |
| `⇅` | `arrow-up-down` | | `🕘` | `history` |
| `🔊` | `volume-2` | | `🔗` | `link` |
| `❝` | `quote` | | `📎` | `paperclip` |
| `⛶` | `maximize` | | `☰` | `menu` |
| `▾` `⌄` | `chevron-down` | | `▸` | `chevron-right` |
| `🧹` | `brush-cleaning` | | `🧠` | `brain` |

### Status

| Old | New | Note |
|---|---|---|
| `⚠` `⚠️` | `triangle-alert` + `.ic-warn` | 78 places, mostly through `Icons.msg()` |
| `✓` | `check` | confirmation mark inside a sentence |
| `✅` | `circle-check` + `.ic-ok` | result light |
| `✗` | `circle-x` + `.ic-err` | |
| `⏳` | `hourglass` | waiting |
| `◎` | `loader` + `.ic-spin` | loading |
| `●` `⬤` | `circle` + `.ic-fill` | light on |
| `○` | `circle` | light off |
| `🟢` | `circle` + `.ic-fill .ic-ok` | |
| `🔴` | `circle` + `.ic-fill .ic-err` | |
| `⚪` | `circle` + `.ic-dim` | |
| `▲` `▼` | `trending-up` `trending-down` | token change |

### File types and other things

| Old | New | | Old | New |
|---|---|---|---|---|
| `📁` | `folder` | | `📂` | `folder-open` |
| `🖼` | `image` | | `📕` `📝` | `file-text` |
| `📜` | `file-code` | | `🎵` | `file-audio` |
| `📄` | `file` | | `🌐` | `globe` |
| `📖` | `book-open` | | `📦` | `package` |
| `★` `⭐` | `star` | | `🛡` | `shield` |
| `⛔` | `ban` | | `🔒` | `lock` |
| `🔧` | `wrench` | | `✨` `✦` | `sparkles` |
| `💡` | `lightbulb` | | `⏰` | `alarm-clock` |
| `🔁` | `repeat` | | `🪝` | `webhook` |
| `▦` | `table-2` | | `☑` | `list-todo` |
| `❓` | `circle-help` | | `♙` | `user` |
| `◆` | `diamond` | | `✍` | `pen-line` |
| `🔺` | `chevrons-up` | | `🔼` | `chevron-up` |
| `🔽` | `chevron-down` | | `⏫` `⏬` | `chevrons-up` `chevrons-down` |
| `🛫` | `plane-takeoff` | | `📅` | `calendar` |

### Unchanged, with reasons

`→` (212 places) is punctuation inside **sentences**: "Hostinger → App terminal", "Sign in to
Claude → all MCPs available". That is text, not an icon. Same reasoning for `─` `•` `↔`
(divider lines, bullets, symbols in developer notes).

## Construction in 5 batches

Each batch can be tested immediately; no batch leaves the UI half-done.

1. **Infrastructure** - manifest, generation script, vendor file, `icons.js`, CSS, tests.
   Nothing changes visually yet. *(done)*
2. **Structured tables** - `VIEW_META`, `GROUP_META`, `_fileIcon()`, `_PRIO`.
   Fewest edit spots but the most visible difference, since each table is a single point of change.
3. **Static HTML + buttons** - `index.html` moves to `data-ic`; the buttons in JS.
   Note: anywhere that currently assigns `textContent` must move to `innerHTML`.
4. **Status strings** - 78 `⚠`, 41 `✓`, 18 `✅` through `Icons.msg()`.
5. **`<select>` + final sweep** - `<optgroup>`, remove emoji in `<option>`, clean up the
   leftovers so the batch 6 test goes green.

## Verification

`tests/python/test_icons.py`, run like every other test in the repo
(`python tests/python/test_icons.py`):

- The vendor set matches the manifest, nothing missing and nothing extra.
- **Every icon name called in the source actually exists.** This blocks typos turning into invisible icons.
- The API layer still has `ic`, `Icons.msg` (the XSS barrier), `Icons.render`, the console warning,
  `aria-hidden`, `currentColor`.
- The script load order in `index.html` is right: data before the API, the API before every file that uses it.
- The CSS still has `.ic`, size `1em`, text-baseline alignment, `.ic-fill`, and respects `prefers-reduced-motion`.
- **No emoji left in the UI.** There is a short exception list, with the reason noted for
  each line, for the Obsidian Tasks syntax. The test prints the files and the number of violating lines, so
  it is both a progress meter during construction and a guard afterwards.

Visual check once done: open both the DARK and LIGHT themes, and review the navigation bar,
the Connections page, the Files page, the Tasks page, the Settings window, and the chat box.

## Risks

| Risk | How it is blocked |
|---|---|
| Moving `textContent` to `innerHTML` opens an XSS hole | `Icons.msg()` escapes by default; batch 4 goes through each place that has a server string |
| A mistyped icon name becomes an invisible icon | A name cross-check test; `ic()` draws a question mark + a console warning |
| Icon misaligned with the text row | `.ic` aligns at `-0.14em`; visual check in the last batch |
| Changing the Obsidian Tasks syntax corrupts data | Removed from scope; recorded in the test's exception list |
| Adding 2 script files slows loading | 18.1KB, no network call; the `?v=` cache-bust is already automatic from VERSION |
