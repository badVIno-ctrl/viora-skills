# 12 - DESIGN.md

Read when writing or maintaining a project's `DESIGN.md`. Purpose: persist the design decision so no future session has to re-derive it. This is the mechanism that keeps context small across sessions.

## Why it exists

Without it, every session re-invents the direction, and the interface drifts: three shades of grey, four radii, two type pairs, a second accent. `DESIGN.md` turns taste into a contract that any model, however weak, can follow by lookup instead of judgement.

With it, G2 is skipped entirely. That is a large context saving on every subsequent session, which matters most on the weakest models.

## Rules

1. Lives at the project root, next to `README.md`.
2. Under 120 lines. It is a contract, not a design essay. If it grows past that, it is being used as a scratchpad.
3. Written once at G2, then updated whenever a real decision changes. Never rewritten from scratch.
4. It **overrides this skill's defaults**. If `DESIGN.md` says the accent is `#B45309`, that is the accent, even if the palette table suggests otherwise.
5. Every value is concrete: hex, px, ms, font names, curve values. No adjectives in the token section.
6. The prose section is allowed exactly one paragraph, and it must contain nouns: materials, positions, scales. Not "modern and clean".
7. Keep a two-line changelog at the bottom so drift is visible.

## Structure

Copy `assets/DESIGN.template.md`. Sections in order:

| Section | Contains |
|---|---|
| Frontmatter | machine-readable tokens: colors, typography, radius, motion |
| Direction | world name, what arrangement it refuses, dial values |
| Palette | every colour role with hex, both themes |
| Type | families, sources, scale decisions, tracking |
| Space and shape | radius family, spacing base, shadow scale |
| Motion | easing tokens, duration table, what animates |
| Components | the decisions that are project-specific: button heights, card usage rule, icon set |
| Voice | how copy sounds, with two real examples |
| Do not | project-specific bans on top of the skill's bans |
| Changelog | date, what changed, why |

Three sections look optional and are not:

- **Do and do not**: two short columns of project-specific rules, five lines each. This is the section a weak model actually obeys, because it needs no interpretation.
- **Responsive behaviour**: what each section does at 640 and at 1024, named per section. Without it every session re-decides the collapse and the page drifts.
- **Known gaps**: what is still undecided, so the next session adds a decision instead of inventing one silently. An empty gaps list on a half-built product is a lie.

The YAML frontmatter matters: it is the part a weak model can apply without understanding the prose, and it is the part other design-to-code tools already know how to read. Keep these key names exactly:

```yaml
---
version: 1
name: Halyard
description: Cargo scheduling for mid-size freight forwarders.
colors:
  canvas: "#FFFFFF"
  surface: "#F6F6F7"
  ink: "#16171A"
  ink-muted: "#5B5E66"
  hairline: "#E4E4E7"
  control-border: "#8A8C95"
  accent: "#1D4ED8"
  accent-ink: "#FFFFFF"
typography:
  display: Geologica 600
  body: Inter 400
  mono: JetBrains Mono 400
  scale: [12, 14, 16, 17, 20, 24, 36, 56]
rounded: [6, 10, 14, 18]
spacing: [4, 8, 12, 16, 20, 24, 32, 40, 48, 64]
motion:
  ease: cubic-bezier(0.23, 1, 0.32, 1)
  durations: [100, 150, 200, 300]
components:
  button-heights: [32, 40, 48]
  card-radius: 14
  icon-set: Phosphor 1.5px
---
```

## Reading it at G1

When `DESIGN.md` exists:

1. Read it fully. It is short by design.
2. Print `G1 read: DESIGN.md found, world <name>, skipping G2`.
3. Do not load `01-direction.md` at all.
4. Do not load `05-color.md` unless a new colour role is genuinely needed.
5. Build against its values exactly. If something is missing, add it to `DESIGN.md` in the same commit rather than deciding it ad hoc in a component.

## Updating it

Update when: a token changes, a component rule is established, a ban is added, or the direction is deliberately revised. Do not update for one-off tweaks that are not rules.

When updating, change the value **and** add the changelog line. A token that changed without a changelog line will be changed back by the next session.

## Multi-surface projects

One `DESIGN.md` per design system, not per page. If a marketing site and a product app genuinely have different visual systems, use `DESIGN.md` for the shared foundation and add a short `DESIGN.marketing.md` for the divergence, listing only what differs. Never fork the whole file.

## Extracting it from something that already exists

When the user pins a brand, a screenshot, or a live URL, do not describe it in adjectives. Extract it into the same file:

1. Sample the real values: grounds, ink, accent, hairline, radius, and the two type families. Devtools or a screenshot dropper, not memory.
2. Write them into the palette and type sections, and mark each inherited value `pinned`. Pinned beats every default in this skill.
3. Measure the sampled pairs with `scripts/contrast.mjs`. Inherited brands routinely fail 4.5:1, and the fix is a documented light or dark variant of the brand colour, recorded in `DESIGN.md`, not a silent decision to ignore it.
4. Write down what you deliberately did **not** inherit, and why. A redesign that keeps the old radius by accident keeps the old feeling by accident.

## Handing it to other tools

The format is deliberately close to the `DESIGN.md` convention used by design-to-code tools, so it can be pasted into another agent, another editor, or a design tool and still be understood. Keep the frontmatter valid YAML so it stays machine-readable.

If the project already has `AGENTS.md`, `CLAUDE.md`, or `.cursor/rules`, add one line there pointing at `DESIGN.md`:

```md
UI work follows DESIGN.md. Read it before changing any visual code.
```

That single line is what makes the contract survive contact with tools that never load this skill.
