# Themes

A theme is one CSS file: optional `@font-face` rules, then a `:root` block that overrides `--pr-*` tokens, then optional extra rules (letterhead details, heading treatment). `new <template> <out.html> --theme <file.css>` inlines it in its own `<style data-pr="theme">` element after the base and template styles, so it wins. For an existing document, replace the contents of that element (or add it right before `</head>`).

## Which theme applies

1. A theme or styling the user asks for in the conversation.
2. A document theme defined by another loaded skill or a CLAUDE.md, for example a brand or house-style skill that says it supplies the pressroom theme. Use its CSS file as `--theme`, or build the file from the tokens it gives.
3. Otherwise no theme file: the base stylesheet is the neutral default (Public Sans body, Newsreader headings, deep blue accent, fonts bundled).

## Tokens

| Token | Role | Default |
|---|---|---|
| `--pr-paper` | page background | `#ffffff` |
| `--pr-desk` | screen background around the sheet | `#e6e8ec` |
| `--pr-ink` | body text and headings | `#1b1f27` |
| `--pr-ink-soft` | secondary text, table headers | `#424a57` |
| `--pr-muted` | captions, meta, labels | `#6b7380` |
| `--pr-rule` | hairlines, table row rules | `#d5d9e0` |
| `--pr-rule-strong` | header rules, table head and totals rules | `#1b1f27` |
| `--pr-surface` | tinted panels, zebra rows, tags | `#f3f5f8` |
| `--pr-accent` | eyebrows, chart marks, links, hero fill | `#1d4f6e` |
| `--pr-accent-soft` | callout background | `#e3edf4` |
| `--pr-accent-ink` | text on an accent fill | `#ffffff` |
| `--pr-good` / `--pr-warn` / `--pr-bad` | semantic status text | green / amber / red |
| `--pr-font-body` | running text | Public Sans stack |
| `--pr-font-display` | headings, big figures | Newsreader stack |
| `--pr-font-mono` | code | IBM Plex Mono stack |
| `--pr-size` | base type size, in pt | `10.5pt` |
| `--pr-leading` | body line height | `1.5` |
| `--pr-scale` | heading scale ratio | `1.25` |
| `--pr-heading-weight` | heading weight | `600` |
| `--pr-radius` | corner radius of panels | `2mm` |
| `--pr-logo` | logo image, `url(...)`, shown by every `.pr-logo` box | `none` |
| `--pr-logo-width` / `--pr-logo-height` | logo box size | `38mm` / `12mm` |

Margin-box text (page numbers, running titles, the letter footer) takes its font and color from these tokens too.

## Fonts

Ship static (non-variable) `.woff2`, `.ttf` or `.otf` files next to the theme CSS and declare them with `@font-face` and a relative `src: url("fonts/name.woff2")`, one rule per weight and style the documents use. `new` embeds each referenced file as a `data:` URI, so the HTML needs no network and the PDF embeds real TrueType or CFF fonts. Variable fonts, including what Google Fonts serves, end up as Type 3 fonts in the PDF; Latin-subset static files from Fontsource are a good source. Include each font's license (OFL) beside the files. The default theme bundles Public Sans, Newsreader and IBM Plex Mono this way.

## Logo and letterhead

Give the logo as a `data:` URI (SVG or PNG) in `--pr-logo`, so the HTML stays self-contained. Every template has a `.pr-logo` box where a letterhead or title block starts; it is empty while `--pr-logo` is `none`. Fixed letterhead text (company name, address, registration numbers in the letter footer) is document content: fill it in the HTML, not the theme.

## Writing a theme for another skill

A skill that owns a brand supplies its theme by shipping a CSS file in the shape above and saying, in its own body, that it is the pressroom document theme. Map the brand's design tokens onto the `--pr-*` roles; leave out any role the brand does not define. Documents are light and printed, so pick the brand's light values and check that `--pr-muted` text stays readable on white. [example-theme.css](example-theme.css) is a complete theme to copy from.
