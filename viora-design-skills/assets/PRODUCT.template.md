# PRODUCT.md

What is true about this product. `DESIGN.md` decides how it looks; this file decides what it
is allowed to say. Loaded at G1 when it exists, and `check.mjs unsourced-number` measures the
copy against it: a number in shipped copy that does not appear here is a warning.

Copy this file to the project root, fill it in, delete the guidance lines.

## Audience scene

One sentence: who, where, on what device, under what light, in what mood, with what already
open on the screen. Not "users" and not a persona card.

> A dispatcher at 6am in a cold yard, one hand on the phone, checking whether the 7:15 run
> has a driver.

## What it actually does

Three to five lines, mechanism first. What happens, triggered by what, producing what. No
adjectives. If a line could describe a competitor, it is not specific enough yet.

## Truth claims

Every number and every superlative that may appear in the interface, with where it came
from. A claim that is not in this table does not ship.

| Claim | Exact wording allowed | Source | Measured when |
|---|---|---|---|
| draft speed | 3 min median | own telemetry, 340 workspaces | 2026-Q1, 12 months |
| adoption | 340 workspaces | billing export | 2026-03-01 |

## Constraints

What the design cannot change: brand commitments, legal wording, existing tokens, platform
requirements, the one integration the product is built around, the browsers that matter.

## Forbidden claims

Written as the exact phrases, so they are greppable. Anything a competitor could sue over,
anything unmeasured, anything the team disagrees about.

- "the fastest"
- "enterprise grade"
- "99.9% uptime"
- any number not in the table above
- any customer name without written permission
