# 01 - Direction

Loaded at G2. Purpose: turn a brief into **one committed visual world**, chosen from a menu instead of invented from nothing. Close this file when the direction contract is written.

Why a menu: a model asked to "invent a beautiful aesthetic" lands on the same two or three clusters every time. A model asked to "pick the right world from fourteen and execute it fully" produces work that looks decided. Selection is a much easier task than invention, and the result is better.

## 1. Set the four dials

Range 1 to 5. Write the values down; they change real decisions later.

| Dial | 1 | 3 | 5 |
|---|---|---|---|
| `EXPRESSION` | invisible, system-default look | confident but calm | the design is the message |
| `DENSITY` | airy, one idea per screen | balanced | information-rich, everything close |
| `MOTION` | state changes only | entrances plus feedback | motion carries the narrative |
| `ORNAMENT` | flat, no material | subtle depth, one texture | layered material, glass, grain, glow |

Defaults by mode. Move a dial only for a reason you can name in a sentence.

| Mode | EXPRESSION | DENSITY | MOTION | ORNAMENT |
|---|---|---|---|---|
| `LAND` | 4 | 2 | 3 | 3 |
| `APP` | 2 | 4 | 2 | 2 |
| `READ` | 2 | 3 | 1 | 1 |
| `SHOW` | 5 | 2 | 4 | 3 |

Hard couplings, no exceptions:

- `MOTION >= 3` means the page must actually move on load and on scroll. A still page that claims motion 4 is broken.
- `MOTION <= 2` means no scroll-triggered reveals at all. Instant is a feature in `APP` and `READ`.
- `ORNAMENT >= 4` requires a solid fallback for `prefers-reduced-transparency` and a documented reason.
- `DENSITY >= 4` bans decorative cards. Data breathes in plain layout with hairlines, not in boxes.
- `EXPRESSION >= 4` bans the system font stack as the display voice. Source a real face.

Two more dials, which nobody writes down and which decide more than the four above: **who this is for** and **what they should feel**. Write the audience as a scene, not a segment: "dispatcher at 6am, one hand, cold yard, phone at 40% brightness", not "logistics professionals". Write the feeling as one word you are willing to be judged on. Both go into the contract, and both come back at G6, where the squint test is answered as that audience rather than as you.

## 2. Pick the world

One world per project. Read the whole menu once, then choose. Each world is a complete package: palette id (from `05-color.md`), type register (from `04-typography.md`), radius family, depth model, composition bias.

| # | World | Feels like | Palette | Type register | Radius | Depth | Composition bias | Best for | Wrong for |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Swiss Utility** | precise, quiet, adult | `graphite` | neutral grotesque, tight display | sharp 0-4px | hairlines only | strict 12-col grid, flush left, big empty right | `APP` `READ`, B2B, tools | brands selling emotion |
| 2 | **Software Craft** | dense, technical, expensive | `nightshift` | grotesque + mono for real data | soft 6-10px | 1px inner light on panels | panel-in-panel, product screenshots framed dark | devtools, infra, `APP` and its `LAND` | consumer wellness, kids |
| 3 | **Cinematic Product** | premium, physical, desirable | `oxide` or `graphite` dark | large grotesque, generous tracking negative | soft 8-14px | photographic depth, no card borders | full-bleed image, type overlaid, one action | hardware, fashion, `LAND` consumer | data-heavy screens |
| 4 | **Editorial Broadsheet** | authored, literate, slow | `editorial` | serif display + workhorse sans body | sharp 0-2px | rules and columns | asymmetric columns, drop lines, real measure | long-form `READ`, journals, essays | dashboards, onboarding |
| 5 | **Bauhaus Poster** | bold, primary, structural | `bauhaus` | heavy geometric sans, huge scale | sharp 0 | flat color blocks | color fields, off-grid geometry, diagonal | events, culture, `SHOW` `LAND` | regulated, medical |
| 6 | **Technical Blueprint** | measured, engineered | `blueprint` | grotesque + mono labels on real values | sharp 2px | grid lines that organize content | modular grid visible, dimension lines, axes | engineering, analytics `APP` | lifestyle, luxury |
| 7 | **Botanical Calm** | grown, unhurried, human | `forest` | humanist sans, optional soft serif | round 12-20px | soft ambient shadow | wide margins, single column, breathing room | wellness, food, sustainability | urgency-driven sales |
| 8 | **Nordic Clinical** | trustworthy, careful, clean | `clinic` | neutral humanist sans | soft 8-12px | flat with one elevation step | generous forms, clear zones, no drama | health, fintech, gov, `APP` | nightlife, hype |
| 9 | **Industrial Signal** | rugged, loud, functional | `oxide` | condensed or wide grotesque, stencil energy | sharp 0-2px | flat plus signal stripes | edge-to-edge bands, hazard rhythm | hardware, logistics, sport | children, finance trust |
| 10 | **Terminal Modern** | insider, fast, exact | `terminal` | mono-first, sans only for prose | sharp 2-4px | none, use hairlines | fixed measure, log-like rhythm, keyboard-first | dev CLI-adjacent, `APP` | mass consumer |
| 11 | **Glass Depth** | layered, tactile, modern OS | `slate-glass` | neutral grotesque, medium weights | round 14-22px | real translucency, inner border | stacked planes, floating panels over content | consumer premium, media | text-heavy, low-end devices |
| 12 | **Gallery White** | the work leads | `gallery` | small quiet sans, huge images | sharp 0 | none | image grid with real air, captions as hairline meta | portfolio `SHOW` | conversion pages |
| 13 | **Kinetic Type** | alive, confident, loud | `mono-pop` | one expressive display face, extreme scale | sharp 0 | none, motion is the depth | type as layout, marquee and mask, few images | agencies, launches, `SHOW` | anything task-based |
| 14 | **Solar Optimist** | warm, energetic, friendly | `solar` | rounded or soft grotesque | round 14-24px | soft colored shadow | large color fields, playful offsets | consumer apps, education | enterprise, legal |

### Choosing well

1. Write the audience's real scene in one sentence: who, where, on what device, under what light, in what mood. Dark or light comes from that sentence, never from category habit.
2. Name the arrangement this category always ships. That one is out unless the user pinned it.
3. Pick the world whose **material** carries the product's actual mechanism, not the one whose adjectives match the brief's adjectives. "Calm coaching" does not mean pale beige; it means the surface must not shout, which many worlds can do.
4. State the world by name in the contract. A direction you cannot name is a direction you did not choose.

### Rotation rule

If `DESIGN.md` history or the repo shows the previous surface used a world, do not reuse it for a materially different subject. Two unrelated projects in the same world means the world was a default, not a choice.

## 3. Anti-default calibration

Where the brief leaves the look free, these clusters are already spent. Landing in one means the choice was skipped, not made.

- Cream or bone ground, high-contrast serif display, terracotta or signal-red accent, lamplight photography.
- Near-black ground, one neon or violet accent, glowing edges, radial mesh gradient behind the hero.
- Broadsheet hairlines, italic serif display, tracked mono micro-labels on everything.
- Beige plus brass plus oxblood plus espresso for anything premium or artisan.
- Purple-blue gradient buttons with an outer glow for anything AI-related.

All five are legitimate **when pinned**. None is legitimate as a reflex. The test: if a stranger could guess your palette from the category alone, rework it.

Method, not vibes: write down the first direction that came to mind, then set it aside. The first instinct is the category default arriving disguised as taste, because it is the most represented arrangement in everything the model has read. Choose deliberately from the menu instead. If you land back on the first instinct, keep it, but write the one line that says why it is right rather than automatic.

Subject association is not a reason. Books wanting a serif, coffee wanting cream, tech wanting mono, finance wanting navy: those are the associations this list exists to break. A book subject can be bookcloth green, thread red, or jacket cyan; cream paper is the smallest corner of that world.

## 4. Write the direction contract

Two places, same content.

**A. `DESIGN.md` in the project root.** Copy `assets/DESIGN.template.md`, fill it, keep it under 120 lines. This is the memory that lets a later session skip G2 entirely. See `12-design-md.md` when you need the full field reference.

**B. A comment at the top of the main artifact** (root layout, `index.html`, or the page component), so the decision survives next to the code:

```html
<!--
  THESIS: scheduling that survives a bad day at the port. Refuses the centered-hero-plus-three-cards
  arrangement this category ships.
  WORLD: Software Craft / nightshift. Near-black ground, hairline panels, one indigo accent on actions only.
  SILHOUETTE: a dark page with one bright horizontal ledger through the middle, readable at 20% and blurred.
  FEELING: relief, because the mechanism is visible before anything is promised.
  AUDIENCE: operations leads who already run three tools. They will not read a paragraph before a screenshot.
  TYPE: Schibsted Grotesk display / Geist Mono for real values. Display tracking -0.03em.
  DIALS: expression 4, density 4, motion 2, ornament 2.
  FIRST VIEWPORT: left column states the mechanism in 7 words, right column is a live product panel,
  primary action sits under the headline, nothing below the fold pretends to be above it.
  SIGNATURE: the ledger draws its accent rule once on load, 520ms, and never again.
-->
```

Seven blocks, 150 words maximum, named exactly as `SKILL.md` names them: `THESIS`, `WORLD`, `SILHOUETTE`, `FEELING`, `AUDIENCE`, `FIRST VIEWPORT`, `SIGNATURE`. If a block reads like a mood board ("modern, clean, sleek") the direction is not decided yet. Rewrite it with nouns: materials, positions, scales. `SILHOUETTE`, `FEELING`, and `AUDIENCE` are the three that get skipped, and they are the three that G6 checks.

## 5. Redesign specifics

- Keep product truth: content, function, claims, constraints, brand commitments the user named.
- Treat the old look as evidence of what the thing is, not as authority over what it becomes.
- Never split the difference. Polishing a look you decided to replace produces the worst of both.
- Before touching code, list in three lines what the old design got right. Those are the things a redesign most often destroys by accident.

## Output of this gate

One marker line, the contract written to both places, nothing else. Then close this file and go to G3.

`G2 direction: Software Craft / nightshift / expression 4 density 4 motion 2 ornament 2`

## Raw material for this gate

The direction is yours to commit to. The catalog only supplies parts:

```
node scripts/pick.mjs "<product type> <audience> <feeling>" --system
```

It answers with a palette, two type pairings, two styles including what each one is wrong
for, a landing pattern with its section order, and a motion tier. Add `--cyrillic` when the
copy is Russian. If the script cannot run, `reference/16-catalog.md` carries the offline
digest and the routing table.

The worlds above outrank anything the catalog returns. A row is a starting point, never a
direction: it has no thesis, no signature and no opinion about this product.
