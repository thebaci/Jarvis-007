---
name: HTML to Webcake
description: Turn an HTML page into a .pke file the Webcake builder can open, keeping the original colours, type sizes, images and layout.
name_en: "HTML to Webcake"
description_en: "Turn an HTML page into a .pke file the Webcake builder can open, keeping the original colours, type sizes, images and layout."
group: Marketing
---

# HTML to Webcake (.pke)

## When to use

The user says things like: "convert this html file to webcake", "turn html into pke",
"create a webcake file from html", "make this landing page into a file I can edit on webcake",
"html to webcake", "convert html to webcake", "put the sales page I just wrote onto webcake".

## Understand the nature of the job before starting

- A `.pke` file = `base64( MessagePack( envelope ) )`, where `envelope.source` is the
  **page_source** of the Webcake editor (`settings, popup, page, options, cartConfigs`).
- Webcake is a **canvas positioned in ABSOLUTE pixels**, and every element records its own `top/left/width/height`
  for 2 sizes: mobile at width 420, desktop at width 960. It is not HTML that flows line by line.
- So the layout is **REBUILT** as vertically stacked sections plus multi-column rows. But **colors, font sizes,
  line-height, letter-spacing, images, content, order** are taken exactly from the source - the toolkit reads the real
  CSS cascade rather than eyeballing it. State this boundary clearly to the user.
- HTML published by Webcake (the exported version) does not contain the editing source; its content can still be read back.

## Tools (shipped with the skill, no package to install)

In the `tools/` folder next to this SKILL.md file. Run with `node`, no npm dependencies.

- `webcake-from-html.js` - **HTML -> spec.json**. Reads the DOM + the real CSS cascade (`var(--x)` variables,
  `clamp()`, `@media`, classes, inline styles), infers sections/headings/text/images/buttons/forms/price tables/
  cards/multi-column rows, then prints a list of warnings.
  `node tools/webcake-from-html.js trang.html spec.json [--name "Page name"]`
- `webcake-build.js` - **spec.json -> .pke**. Runs the lint automatically after building.
  `node tools/webcake-build.js spec.json out.pke [--check]` (`--check`: exit 1 if the lint finds errors)
- `webcake-lint.js` - checks the layout (overlaps, section overflow, dead gaps) **and text/background contrast**.
  `node tools/webcake-lint.js out.pke`
- `webcake-preview.js` - renders page_source into static HTML that simulates the canvas exactly, to LOOK AT it first.
  `node tools/webcake-preview.js out.pke previewBase [--debug]`
- `webcake-pke.js` - two-way codec: `decode file.pke file.json` / `encode file.json file.pke`.
- `webcake-html.js` - the shared HTML/CSS reading library (do not call it directly).

A standard hand-written spec example: `examples/salepage-16-buoc-spec.json`. A source HTML example: `examples/sample.html`.

## Procedure when activated (all 6 steps are MANDATORY)

1. **Identify the source HTML.** The user hands over an `.html` file or pastes HTML. If pasted, write it to a temp file first.
2. **Convert automatically**: `node tools/webcake-from-html.js trang.html spec.json`.
   **READ the "CAN LUU Y" section it prints carefully** ("CAN LUU Y" = "Things to note", a heading the tool prints in Vietnamese without diacritics) - these are the things it could NOT carry over (local images,
   svg/canvas, hover effects, CSS from external files). Do not skip it and then hand over an incomplete file.
3. **Review the spec by eye** and hand-fix what the machine cannot guess: the `ratio` of images that do not declare
   a size, which sections should be merged/split, which button is the main CTA. This step is for "looks good", not
   for "looks the same" - the "looks the same" part the machine has already done.
4. **Build**: `node tools/webcake-build.js spec.json out.pke`.
5. **Lint must show 0 ERROR.** If overlap/overflow/text-sinking-into-background errors remain, fix the spec and build again - do NOT
   hand over a file with errors. Low-contrast warnings should also be dealt with, that is text that is genuinely hard to read.
6. **Inspect before delivering**: `node tools/webcake-preview.js out.pke preview` then open
   `preview.desktop.html` + `preview.mobile.html`. If you can take screenshots, place them beside the original page and compare:
   section order, background color of each band, heading size, image position. Fix the spec wherever it differs and repeat.
7. **Deliver the file**: put `out.pke` next to the original HTML or in the vault, embed a markdown link for the user to download,
   and report BRIEFLY: how many sections, what QA was done, remind them to "upload to Webcake to edit" + the limitations.

## spec.json schema

```json
{
  "name": "Page name", "title": "SEO title", "description": "SEO description",
  "font": "Montserrat", "favicon": "https://... (optional)",
  "extraScript": "JS that runs on publish/preview (e.g. a countdown)",
  "extraCss": "Extra CSS on publish",
  "theme": {
    "colors": { "ink": "rgba(242,240,232,1)", "amber": "rgba(232,168,92,1)", "cta": "linear-gradient(...)" },
    "text":    { "color": "$soft", "size": 16 },
    "heading": { "color": "$ink" },
    "badge":   { "color": "$amber", "bg": "rgba(232,168,92,0.08)", "borderColor": "rgba(232,168,92,0.35)" },
    "card":    { "bg": "$cardBg", "borderColor": "$line", "radius": 16, "titleColor": "$ink", "textColor": "$soft" },
    "button":  { "bg": "$cta", "color": "$bg0", "radius": 99, "size": 17 },
    "textMaxWidth": 700, "headingMaxWidth": 800, "cardMaxWidth": 800
  },
  "sections": [ { "name": "hero", "background": "$bg0 or a CSS gradient string", "padTop": 56, "gap": 18, "padBottom": 56,
    "elements": [ ] } ]
}
```

**Color tokens**: `"$name"` (the whole string) or `${name}` (embedded in long html) -> automatically replaced with `theme.colors.name`. A name that does not exist is left as is (safe for strings like "$50").
Each of `theme.text/heading/badge/card/button/testimonial/priceTable/guarantee/progress/divider/ctaBlock` is the **default for the matching kind** - an element only states the fields that differ from the default.

### LEAF elements

| kind | main fields | notes |
|---|---|---|
| `heading` | `text` (inline HTML OK), `size`, `tag` h1/h2/h3, `align`, `kicker`, `lineHeight`, `letterSpacing` | `kicker: "01"` automatically generates a small pill above |
| `text` | `html`, `size`, `color`, `align`, `maxWidth`, `lineHeight`, `letterSpacing` | by default it is automatically bounded to `textMaxWidth` (~700) and the block is centered |
| `image` | `src`, `ratio` (w/h), `width` 0..1, `widthMobile`, `radius`, `boxShadow` | |
| `button` | `text`, `href` or `scrollTo`, `width`, `bg`, `color`, `radius`, `boxShadow`, `animation` | the glow is inferred from the bg color; long text automatically increases the height |
| `badge` | `text`, `align`, `bg`, `color`, `borderColor`, `padX`, `padY` | long text automatically LOWERS the font size; if it is still too long it wraps and the pill grows taller |
| `card` | `icon`, `iconTop`, `title`, `text`, `accent`, `pad`, `align`, `maxWidth` | a rounded background box + title + description |
| `divider` | `width` 0..1, `color`, `thickness` | a thin centered line |
| `progress` | `value` 0..1, `width`, `label`, `fillColor`, `trackColor`, `glow` | a progress bar |
| `priceTable` | `title`, `rows: [{label, price}]`, `total`, `strike`, `today` | a value table, a total row, a struck-through price line |
| `testimonial` | `quote`, `author`, `stars` 1..5 | wrapped in a card automatically |
| `guarantee` | `icon`, `title`, `text` | a large icon on the left, content on the right |
| `ctaBlock` | `text`, `href`, `sub`, `arrow` + every button field | an arrow + button + sub line as 1 block |
| `spacer` | `height` | |
| `window` | `title`, `lines: [{who: "you\|bot", text}]` | a chat window frame |
| `form` | `fields`, `submitText`, `submitBg`, `redirect` | inputs + a submit button |

Every kind also accepts `customCss` (plain CSS declarations for that element only, passed through Webcake's
`specials.custom_css`). Use it only for things you can SEE: gradients, shadows, rounding, filters, transitions. **Never** set
`position/top/left/width/height/display/flex/grid` here - the engine will throw an error, because they override the canvas's
absolute box and break the layout.

### LAYOUT elements (against the monotonous single-column page)

- `row` `{ "gap": 44, "valign": "center", "cols": [ {"w": 0.55, "items": []}, {"w": 0.45, "items": []} ] }` - on desktop the columns sit side by side, on mobile they stack automatically.
- `hero` `{ "side": "right|left", "mediaW": 0.4, "media": {image/window element}, "items": [] }` - the shortcut for "text on one side, picture on the other".
- `cardsRow` `{ "gap": 18, "cards": [ {icon,title,text} ] }` - 1 row of equal cards.
- `testimonialRow` `{ "items": [ {quote,author} ] }` - a horizontal row of testimonials.
- `iconRow` `{ "items": [ {icon, text} ] }` - a row of icons + short captions.

## Design pass (aesthetic checklist - score it BEFORE delivering)

1. **Background rhythm**: alternate dark / light section backgrounds; at most 1 accent radial-gradient for the hero + 1 for the price block.
2. **>= 3 layout patterns** per page (2-column hero, cardsRow, priceTable, testimonial...). 100% single column is forbidden.
3. **Readable text width**: paragraphs <= ~90 characters per line (`textMaxWidth` takes care of this).
4. **Consistent heading scale**: e.g. h1 42 / h2 31 / h3 19 on desktop (mobile is automatically multiplied by ~0.84).
5. **Spacing in multiples of 8** for padTop/padBottom/gap; do not chop it into one section per line.
6. **Repeat the CTA 2-3 times**, same color and same radius; the main button is the most prominent on the page.
7. **Lint 0 ERROR + preview at 2 sizes**: no overlapping text, no missing backgrounds, no text sinking into the background.

## Conversion principles

- **Emphasized text**: inline tags in the html - `<span style='font-weight:700;color:${ink};'>...</span>`,
  struck-through price `<span style='text-decoration:line-through;'>...</span>`. Line break `<br>`, do NOT nest `<p>`.
- **Gradient-filled text**: `<span style='background:linear-gradient(...);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;'>`.
  This is HTML sitting INSIDE `specials.text` so it runs normally; quite different from the `styles.background` of the whole text block.
- **Colors**: in the form `rgba(r,g,b,a)` or a `$name` token. Use a gradient for the standout button.
- **Images**: Webcake loads by public URL. Local/base64 images -> WARN the user they need to upload and then replace `src`,
  otherwise the image will be empty (the lint also catches this error).
- **Text measuring**: the engine uses a table of the width of EACH Montserrat character measured for real from Chromium (accurate for Vietnamese too,
  UPPERCASE, emoji, digits), accounting for `line-height`/`letter-spacing`/spans that change font size, plus a 1.5% safety margin.
  Fonts other than Montserrat are less accurate - always run the preview to check.
- **Dynamic script/CSS**: `extraScript` / `extraCss` map into Webcake's Settings > HTML/JavaScript;
  they ONLY run on Preview / Publish, NOT inside the editor - tell the user to press Preview to see them.
- **Do NOT use the em dash character** anywhere (text, spec, report) - use "-".

## Advanced route (build the page_source yourself, then encode)

When you need deep control (nested groups, popups, product radio/checkbox), build the whole `source` object yourself
(`{settings, popup, page, options, cartConfigs}`) in the correct Webcake node schema, write it to JSON, then:
`node tools/webcake-pke.js encode source.json out.pke` (add `--name` `--owner` if needed).

With a **Webcake Landing MCP** connection there is a second route: build the page directly on the account through
`create_page` / `add_section` / `validate_page`. This `.pke` route is for when the MCP is not connected yet,
or when the user wants a file to upload themselves.

## Limitations to state plainly to the user

The layout is rebuilt on a vertical grid + multi-column rows, not a copy of the original HTML's exact pixel positions.
Animated background effects (canvas, blurred orbs, svg) cannot be carried into the editor. `:hover` effects must be added back
by hand in Settings > CSS. Product-selection radio/checkbox (tied to Pancake's `product_id`/`variation`)
cannot be generated automatically - the user adds them in Webcake after uploading.
We encourage uploading the `.pke` file as a trial first, adjusting the spec wherever it differs, and building again.
