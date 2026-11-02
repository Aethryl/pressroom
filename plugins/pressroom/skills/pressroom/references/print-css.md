# Print rules

`base.css` (inlined by `new`) already applies the rules below. This file is for writing new components and for fixing what the contact sheet shows.

## Page

- Set size and margins in `@page`. A4 is the default; Letter is `size: letter` (or `--format Letter` at render time). Starting margins: report `16mm 16mm 18mm`, letter `25mm 20mm 22mm 25mm` with a smaller first-page top margin, CV `14mm 14mm 16mm`, one-pager `12mm`.
- Page numbers come from CSS margin boxes: `@page { @bottom-right { content: counter(page) " / " counter(pages) } }`, and `@page :first { @bottom-right { content: none } }` to hide it on a cover or first page. A running title goes in `@bottom-left` the same way. `pdf --footer-numbers` adds Chromium's own footer instead; use it only when the document has no margin boxes, or the numbers print twice.
- Chromium clips everything outside the page content box. Content placed in the margin with negative offsets, `position: fixed` or an `@page` background does not print, so fold marks and edge-bleed decorations cannot be made. Text in the margin must be a margin box `content` string.
- `position: fixed` elements repeat on every page. Use them only for something that really belongs on every page.

## Screen and print

- The HTML is also viewed on screen. `.doc` shows the page as a sheet on a grey desk; under `@media print` the sheet's padding, width and shadow go away so `@page` margins rule. A template that changes `.doc` padding for screen also resets it to 0 in print.
- The document is light only: `color-scheme: light`, no dark-mode token blocks. `print-color-adjust: exact` is set on the root, so fills and tinted rows print; the renderer prints backgrounds.
- Print type runs about 3% smaller than screen. Body text sits near 10–11pt, footers and captions at 7.5–8.5pt.

## Breaks

- Prefer flow. A forced `break-before: page` (class `page-break`) is for a real new part, like an appendix or a cover page; used to fix a layout it leaves half-empty pages.
- Headings carry `break-after: avoid`, but Chromium honours it only loosely. Wrap a heading and the block that follows it in an element with class `keep` when the pair must stay together, and wrap a short paragraph with its figure the same way.
- `break-inside: avoid` is on figures, callouts, list items, table rows, signature blocks and `.keep`. Put `keep` on a short table or list that must not split. A long table splits by rows and repeats its `thead` on the next page; that is correct.
- A `keep` block taller than a page still breaks. Cap images and SVG in print with `max-height` in mm (base: 120mm) so no figure exceeds a page.
- Amounts, phone numbers and dates that must not wrap get `&nbsp;` between their parts (`€&nbsp;186,00`).

## Figures

- Inline SVG charts take `viewBox` and no fixed width; color their marks from `--pr-*` tokens so a theme recolors them. Every label must name a value the scale actually reaches.
- Images live next to the HTML and are referenced by relative path, or embedded as `data:` URIs when the HTML must travel alone (an artifact always needs `data:` URIs).
- Fonts are embedded in the HTML as static files, so the PDF gets real TrueType fonts. Web fonts from Google Fonts are variable fonts, which Chromium embeds as Type 3 fonts and which need the network; use static font files instead (see theming.md).
- Remote images need the network at render time; `pdf` warns about each image or font that failed.

## Reading the check output

`check` reports, per page, how much of it carries ink and where its content ends. It flags blank pages and non-final pages whose content ends above 55% of the height, which almost always means a `keep` block or forced break pushed a large block to the next page. Shrink, split or reorder that block, or drop the forced break.
