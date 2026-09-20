# 20 - Structure

Loaded at G3, after the tokens and before the section plan. Colour and type decide how a
page feels. Structure decides whether it looks like anyone arranged it. A page can obey
every token rule and still read as generated, because the arrangement is the one every
generator ships: centred hero, three equal cards, a band with a button, a four column
footer.

Output of this gate, one line:

`STRUCTURE: <shape> / nav <N> / footer <F>`

Write the same line into `DESIGN.md` under `STRUCTURE`. The next session matches it
instead of re-deciding.

## 1. Six structural axes

Decide each one explicitly. An axis you did not decide is an axis set to its default, and
the defaults together are the generated page.

| Axis | Choices | Default to avoid |
|---|---|---|
| Heading placement | centred, left rail, offset into the grid, over the image, in the margin | centred every section |
| Body composition | single column, asymmetric two column, hairline rows, staggered pairs, table | equal card grid |
| Divider language | whitespace only, hairline, ground change, full-bleed image, rule plus number | shadowed card edges everywhere |
| Button voice | one primary per screen, primary plus quiet ghost, text link only, inline in the sentence | two filled buttons side by side |
| Image treatment | full bleed, inset with margin, cropped to a shape, masked to type, none at all | rounded rectangle screenshot with a shadow |
| Reveal | everything present, progressive disclosure, tabbed, accordion, one long scroll | accordion for content that fits |

## 2. Sixteen page shapes

Pick one. The section order is the shape; changing the order makes it a different shape,
not a variation.

| Shape | Section order | Wrong for |
|---|---|---|
| Ledger | claim, hairline rows of facts, one image, price, close | emotional or visual products |
| Broadsheet | masthead, lede paragraph, two column body, pull quote, index | task-driven apps |
| Console | status strip, primary table, detail panel, footer meta | persuasion, first-touch marketing |
| Gallery wall | one image full bleed, caption grid, statement, contact | data-heavy products |
| Manual | table of contents rail, numbered procedure, diagrams, glossary | short campaign pages |
| Storefront | offer band, product rows, trust strip, cart close | services with no catalogue |
| Case file | subject line, evidence blocks alternating sides, outcome, next case | product feature pages |
| Terminal | prompt-style hero, mono spec rows, code sample, install line | non-technical audiences |
| Invitation | date and place, one image, one paragraph, RSVP | ongoing products |
| Dossier | cover statement, numbered sections with hairlines, appendix | quick-decision purchases |
| Timeline | anchor date, chronological rows, present state, what is next | products with no history |
| Comparison | position claim, two column against-the-alternative table, caveats, close | category-defining launches |
| Counter | large measured number, how it was measured, method, source, close | products with no numbers |
| Letter | salutation, argument in prose, signature, one action | scanning audiences |
| Specimen | type or colour specimen, usage rules, download, licence | conversion pages |
| Atlas | map or index, region cards of unequal size, detail drill-in, legend | single-offer pages |

## 3. Ten navigation archetypes

| Id | Shape | Fits |
|---|---|---|
| N1 | wordmark only, no links | one-screen surfaces, invitations |
| N2 | wordmark plus one action | single-offer landing |
| N3 | left wordmark, right two links, no button | editorial, docs |
| N4 | inline text links in a sentence | letter, manifesto |
| N5 | sticky rail on the left edge | manual, dossier, long read |
| N6 | segmented control across the top | console, app shell |
| N7 | search field as the primary nav | atlas, storefront, docs |
| N8 | breadcrumb only | deep hierarchies, case files |
| N9 | bottom bar on small screens, rail on large | operating surfaces |
| N10 | no chrome at all, the content is the index | gallery, specimen |

## 4. Six footer archetypes

| Id | Shape | Fits |
|---|---|---|
| F1 | one line: legal, contact, year | most pages |
| F2 | two columns: address block and one link column | services, local businesses |
| F3 | repeated primary action plus one line | single-offer landing |
| F4 | colophon: typefaces, tools, who built it | specimen, portfolio, editorial |
| F5 | index of every page as hairline rows | atlas, docs, large sites |
| F6 | contact form inline in the footer | services, agencies |

## 5. Not by default

These three arrangements are the arrangement a generator reaches for. They are not banned,
they are unavailable by default: use one only when the brief names it, and write the reason
into `DESIGN.md`.

- **Wordmark plus centred links plus a filled button** as the navigation. It signals nothing
  and it is the header on every template. Take N1, N3, N5 or N7 instead.
- **Four column link footer with a social icon row.** Most of those columns hold one link.
  Take F1 unless the site actually has that many destinations, and then take F5.
- **Hero, then three equal cards, then a CTA band.** The card row is a layout stub that
  survived. Take hairline rows, staggered pairs, or two unequal blocks.

`check.mjs` enforces the last two mechanically: `stock-footer` and `template-rhythm`.

## 6. Choosing

1. Read the mode. `LAND` can take an expressive shape; `APP` takes Console or Atlas and
   very little else; `READ` takes Broadsheet, Manual or Dossier; `SHOW` takes Gallery wall
   or Specimen.
2. Take the shape whose section order matches the argument the page actually makes. If you
   cannot say what the second section proves, the shape is wrong.
3. Check the "wrong for" column against the audience. One match there ends the choice.
4. Pick the nav and the footer from the tables, by id. An archetype you cannot name is the
   default one.
5. If the previous surface in `.viora/design-log.json` used this shape, take another one.
   Two unrelated surfaces in one shape means the shape was a habit.
