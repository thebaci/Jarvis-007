# Design: open links and edit .md files right inside the chat panel

Date: 2026-07-18
Status: approach approved (option A)

## Background and problem

In the chat panel, Jarvis 007 occasionally sends .md files, text files and links. Currently:

- A markdown link `[text](https://...)` can already be clicked to open a new tab. But a "bare"
  URL (Jarvis 007 types `https://...` directly without wrapping it in markdown) shows up only as
  text and cannot be clicked.
- Clicking a .md file link in chat only jumps to the Files page and highlights that file; the
  user must click once more to open the editor panel.

The user wants: every link is clickable, and a .md file opens an editor panel (view + edit)
immediately when clicked.

## Goals

1. A bare URL in chat automatically becomes a link that opens in a new tab.
2. Clicking a .md file link (and text files) in chat immediately opens an edit panel in the
   middle of the screen to view and edit, with saving.

## Out of scope

- No drag-and-drop WYSIWYG editor (option B was rejected). The edit panel uses a source
  textarea, and .md alone gets a toggle button to view the rendered version.
- No change to inline image behavior (clicking an image stays as before).
- No server endpoint changes. Reuse the existing `/files/read`, `/files/write`, `/files/raw`,
  `/files/list`.

## Important detail: two path conventions

- File paths in chat are **relative to the brain root** (per the CLAUDE.md convention when the
  AI writes).
- `/files/read` and `/files/raw` use `_safe_serve_path`, which accepts BOTH conventions (the
  browse ceiling and the brain root), so reading/showing an image with the chat path works.
- `/files/write` uses `_safe_path`, which counts only the **browse ceiling**. On localhost the
  ceiling = the whole disk, so writing with a brain-root path would land in the wrong place.

Conclusion: to SAVE correctly, the brain-root path must be turned into a browse-ceiling path by
prepending the brain's "home" prefix. This prefix comes from `/files/list` (the `home` field).
This is exactly what the tree editor (`openNote` via `_vtHome`) already does. The new edit panel
will prepend `home` for BOTH reading and writing for consistency.

## Architecture and components

### Part 1 - Recognizing bare URLs (edit `dashboard/chat-render.js`)

In `mdToHtml`, add a step after code fences, inline code, images and markdown links have been
stashed into placeholders (private-use sentinels), BEFORE block parsing. This step touches only
ordinary text:

- Catch `https?://...` with a regex, stripping trailing punctuation (`.,;:!?)]}'"`) off the link.
- Wrap it as `<a href target="_blank" rel="noopener">`, passing it through `put()` so it is not
  escaped again.
- Because the old code/links are already sentinels they are not touched; sentinels do not match
  the URL regex.

### Part 2 - The file edit panel (`dashboard/file-editor.js`, NEW)

A standalone IIFE module that injects its own CSS and attaches the modal to `document.body`. It
works from any page because `position: fixed` is at the body level, independent of the HUD
layout or the Files page.

Interface: `window.JavisEditFile(brainRelPath)`

Flow:

1. Get the brain's `home` prefix (fetch `/files/list?brain=<brain>` once, cached per brain).
   Ceiling path = `home ? home + "/" + brainRel : brainRel`.
2. Read `/files/read?brain=<brain>&path=<ceilingPath>` → `{name, editable, content}`.
3. Show by type:
   - Image (`.png .jpg .jpeg .gif .webp .bmp .ico`): `<img src=/files/raw...>`.
   - `.pdf`: `<iframe src=/files/raw...>`.
   - Editable text (`editable` from the server): `<textarea>`. `.md` alone gets a "Source /
     View" toggle button; the View version is rendered with the existing `window.mdToHtml`
     (read-only, built from the textarea's current value).
   - Anything else: a Download button.
4. Save: POST `/files/write` (FormData: brain, path=<ceilingPath>, content). The button shows
   "✓ Saved".
5. Close: Esc, the ✕ button, clicking the dimmed backdrop. Quick save: Ctrl+S.

The brain comes from `window.currentBrainPath()` (the source chat already uses). `esc` is
defined locally in the module.

### Wiring chat to the editor (edit the handler in `dashboard/chat-render.js`)

The click handler for `a.jv-floc` (vault file/folder links):

- Keep the Ctrl/Cmd/Shift/Alt/middle-click branch -> let the browser open the `#open=` deep link
  in a new tab (as before).
- If the anchor CONTAINS an `<img>` (inline image) -> keep the old behavior (`JavisOpenFiles`).
- Otherwise inspect the path: it has a file extension (the last segment contains a dot) -> call
  `window.JavisEditFile(path)`; no extension (a folder) -> `JavisOpenFiles(path)` as before.
- Fallback: if `window.JavisEditFile` is not loaded yet -> fall back to `JavisOpenFiles`.

### Script loading (edit `dashboard/index.html`)

Add `<script src="file-editor.js"></script>` next to where `chat-render.js` is loaded.

## Data flow

Click a .md link → chat-render handler → `JavisEditFile(brainRel)` → (fetch home if not cached)
→ `/files/read` → build the textarea → edit → Ctrl+S/Save → `/files/write` (ceiling path) →
report saved.

## Error handling

- Fetch home fails: use an empty prefix (reading still works thanks to the dual convention;
  saving is correct when ceiling == brain). If saving returns an error the button shows
  "⚠ Error", it does not swallow it silently.
- `/files/read` fails/cannot read: show a message + "Open in new tab" / "Download" links through
  `/files/raw`.
- A file that cannot be edited (binary): show a Download button, do not allow editing.

## Testing

- Unit (node): add a test for `mdToHtml` (chat-render.js already exports it) checking a bare URL
  becomes a link, and does not break existing code blocks / markdown links / inline code.
- Manual (browser): clicking a .md link in chat opens the edit panel, edit, Ctrl+S to save,
  reopen and see the change; clicking a bare URL opens a new tab; clicking a folder link still
  jumps to the Files page; clicking an inline image works as before.

## Files touched

- `dashboard/file-editor.js` (NEW): the modal edit panel + `window.JavisEditFile`.
- `dashboard/chat-render.js` (EDIT): bare URL autolink; wire the file click -> editor.
- `dashboard/index.html` (EDIT): load file-editor.js.
- Test: add an autolink case for mdToHtml (the test file next to chat-render).
