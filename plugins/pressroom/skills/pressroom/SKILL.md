---
name: pressroom
description: Use when the user asks for a document, letter, report, CV, proposal, quote, handout or a PDF of something.
---

# Making documents

You are the document's author and typesetter. Write the document as a print-ready HTML file, render it to PDF with this skill's renderer, look at every page, and fix what you see until the pages are clean.

The renderer is `${CLAUDE_SKILL_DIR}/scripts/pressroom.py`. Run every command below as `python3 -I ${CLAUDE_SKILL_DIR}/scripts/pressroom.py <command> ...`; add `--help` after a command for its flags. It is an internal tool: tell the user about the documents, not the commands.

## Steps

1. **Settle the content.** Know the audience, the language, the paper size (A4 unless the user or their country says Letter) and what the document must achieve. Ask only when the answer changes the document; otherwise decide and say what you assumed.

2. **Pick the theme.** The user's own words win. Next, a document theme defined by another loaded skill or a CLAUDE.md: use it. Otherwise use the neutral default theme built into the templates. A theme is a CSS file of token overrides; [references/theming.md](references/theming.md) defines the tokens and how a theme is supplied.

3. **Start from a template.** `new --list` lists them; `new <template> <file.html> [--theme theme.css]` writes a self-contained HTML file with the base print stylesheet, the fonts and the theme inlined. Pick the closest template and rewrite it completely: the sample text, names and numbers in it are placeholders. For a type with no template, start from `report` or `one-pager`. Conventions per document type (letter layouts, the Dutch business letter, quotes, CVs) are in [references/doc-types.md](references/doc-types.md).

4. **Write for paper.** Follow the print rules in [references/print-css.md](references/print-css.md): page size and margins in `@page`, `keep` wrappers around a heading and its first block, figures capped in height, flow rather than forced page breaks. Real content only. Check every number that is a sum, share or total.

5. **Render.** `pdf <file.html>` writes the PDF next to the HTML and prints its page count and any font or image that failed to load. Fix load failures before looking further.

6. **Look at every page.** Run `check <file.pdf>` (blank and underfilled pages) and `sheet <file.pdf>`, then Read the contact sheet PNG it prints. Read a hi-res page with `page <file.pdf> <n>` wherever the sheet is too small to judge: tables, small type, the letter address block. Fix cut figures or tables, headings stranded at a page bottom, large gaps, blank pages, overflow past the margin, wrong numbers. Re-render and look again. The loop is done when a fresh contact sheet shows nothing left to fix.

7. **Deliver.** Give the absolute paths of the HTML and the PDF. The HTML is the source; edit it and re-render for changes.

## Local file, artifact only on request

The document is a local file by default. Publish it with the Artifact tool only when the user explicitly asks for an artifact, and then publish the same HTML file. The PDF always comes from `pdf` on the local file: printing the claude.ai artifact viewer prints the viewer frame, ignores page-break rules and adds the browser's header and footer.

## When rendering fails

The renderer needs Python 3.10+, a Chromium-family browser, and poppler (`pdftoppm`, `pdfinfo`) for `sheet`, `page` and `check`. Its error message names what is missing and how to install it; relay that to the user instead of switching to another PDF route. The environment variable `PRESSROOM_CHROME` points it at a specific browser binary.
