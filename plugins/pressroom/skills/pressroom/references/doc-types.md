# Document types

| Template | For |
|---|---|
| `report` | reports, analyses, reviews, memos longer than a page: title block, summary figures, sections, tables, SVG chart |
| `letter-nl` | Dutch business letter (zakelijke brief) for a window envelope |
| `letter` | international business letter, block format |
| `quote` | quotes, offers (offerte), proposals with a price: parties, line items, totals, terms, signatures |
| `one-pager` | handouts, flyers, fact sheets, instructions that must fit one page |
| `cv` | CV or résumé, two columns |
| `cover-letter` | cover letter (sollicitatiebrief) matching the `cv` header |

A proposal without prices starts from `report`; an invoice starts from `quote` with invoice number, invoice date, due date and payment details in place of validity and signatures.

## Letters

- Write the letter in the recipient's language and follow that country's conventions for date format, salutation and closing.
- The recipient address sits in the envelope window: from 45mm below the top edge and 25mm from the left, at most 85×40mm. That matches DIN 5008 type B and the usual Dutch left-window envelopes. Keep the letterhead height and first-page top margin in the template unchanged so the address stays in the window.
- Folded in three for a DL or EA5/6 envelope. Fold marks cannot be printed (Chromium clips the page margins).
- Letters longer than one page number from page 2 onward ("Pagina 2 van 3" / "Page 2 of 3"); page 1 carries no number.

### Dutch business letter

- Return line (retouradres) in small type directly above the address in the window.
- Address: company, then "t.a.v." with the person, street or Postbus, postcode (4 digits, space, 2 capitals) and place in capitals or as written; no country line for domestic post.
- Reference line under the address: Datum, Uw kenmerk, Ons kenmerk, optionally Bijlage(n). Date as "2 november 2026", month lowercase.
- Onderwerp on its own line, bold, no "Betreft:" in modern style. No full stop at the end.
- Salutation "Geachte heer De Vries," or "Geachte mevrouw Hendriks," (surname prefix capitalised without the first name); "Geachte heer, mevrouw," when unknown. The first body sentence starts with a capital.
- Closing "Met vriendelijke groet," followed by signature space, name and role. Never "Hoogachtend" unless the user asks for a very formal tone.
- Company details required on business letters (KvK-nummer, btw-id, IBAN, registered seat when it differs) go in the first-page footer. Amounts as "€ 243,60" with a non-breaking space, comma decimals and dots for thousands.

### International letter

- Sender block top right or in the letterhead, recipient in the window, date on its own line, then subject in bold.
- British: "2 November 2026", "Dear Ms Jensen," … "Kind regards,". American: Letter paper, "November 2, 2026", "Dear Ms. Jensen:" … "Sincerely,". Mention enclosures under the signature.

## Quotes and invoices

- Every amount right-aligned with tabular figures (`class="num"`); unit price × quantity must equal the line amount, the lines must add up to the subtotal, and the tax line must be the stated rate of the subtotal. Recompute before rendering.
- State the currency once in every amount, the validity date on a quote, and the payment term.
- Keep the totals table and the terms with `keep`; a long line-item table may split across pages and repeats its header.
- Dutch offerte or factuur: btw 21% (or 9%) as a separate line, the client's and your KvK and btw numbers, factuurnummer and factuurdatum; amounts in "€ 1.234,56".

## One-pager

- It must stay one page: check reports a page count of 1. Cut text before shrinking type below 9pt.

## CV and cover letter

- One page for under ten years of experience, at most two otherwise. Most recent first, results with numbers, no photo unless the user asks (common in the Netherlands, discouraged in the US and UK).
- Each job block stays whole (`break-inside: avoid` in the template). If a second page is needed, it continues the main column; the sidebar ends on page 1.
- The cover letter repeats the CV's name header so both look like one set. Address it to a named person when known, and name the vacancy and its reference number in the subject line.
