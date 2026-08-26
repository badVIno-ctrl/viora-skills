# 15 - Performance as craft

Loaded at G4 when the surface carries images, fonts, animation or long lists, and at G6
before the report. Not a separate discipline: a jumping layout, a late headline and a
laggy tap read as cheap no matter how good the palette is. Speed is the part of the design
the user feels before they see anything.

Origin: the measurement discipline and the budget table come from the Lighthouse and Core
Web Vitals skills by Addy Osmani (`github.com/addyosmani/web-quality-skills`, MIT), reduced
to the decisions a designer actually makes.

## 1. The three numbers, and what each one looks like

| Metric | The user's experience | Good | Poor | The design decision behind it |
|---|---|---|---|---|
| **LCP** | "the page took a while to say anything" | under 2.5s | over 4s | hero image weight, web font blocking, client-rendered first screen |
| **CLS** | "it moved while I was reading" | under 0.1 | over 0.25 | images without dimensions, late fonts, injected banners, animated layout |
| **INP** | "the tap did nothing for a moment" | under 200ms | over 500ms | heavy handlers, unvirtualised lists, controlled inputs, blocking work on click |

Two more that belong to design, not to engineering: the first feedback after a tap must land
under 100ms, and any operation over one second needs a skeleton or progress, never a
spinner alone.

## 2. Budget

Starting guardrails for a content or marketing page. Calibrate to the product's real target
devices and networks. If the project already has a budget, that one wins.

| Resource | Budget | Why it is a design number |
|---|---|---|
| Total page weight | under 1.5 MB | every extra megabyte is a second on a mid-range phone |
| JavaScript, compressed | under 300 KB | parse and execute time is INP |
| CSS, compressed | under 100 KB | render-blocking by definition |
| Above-fold images | under 500 KB | this is almost always the LCP element |
| Fonts | under 100 KB | two families, four weights, subset |
| Third party | under 200 KB | code you cannot fix, on your critical path |

One font family more, one more weight, one more analytics tag: each is a design decision
with a price. Name the price when you take it.

## 3. LCP: make the page say something fast

- The largest element in the first viewport is chosen deliberately: one image, one headline,
  or one real product panel. Decide which, then make that one thing fast.
- The hero image is never lazy. It carries `fetchpriority="high"`, correct dimensions, and a
  `srcset` so a phone never downloads a desktop file.
- Fonts: `preconnect` to the font origin, `preload` only the weights used above the fold,
  `font-display: swap`. A hero headline that appears 900ms late is the most common cause of
  a page that feels slow while every metric except LCP looks fine.
- Never render the first screen on the client when a server or a static build can produce it.
  A skeleton where the headline belongs is not a design, it is a delay with rounded corners.
- Blur-up placeholders and dominant-colour backgrounds are craft, not decoration: they make
  the wait look intentional.
- Video in the hero: poster frame first, `preload="none"`, and never as the LCP element.

## 4. CLS: nothing moves after the first paint

- Every image, video, iframe and ad slot has dimensions or an `aspect-ratio` box.
- Fonts shift text unless the fallback matches: set `size-adjust`, `ascent-override` and
  `descent-override` on the fallback, or accept one small shift and measure it.
- Anything injected after load (cookie bar, banner, toast, promo) either has reserved space
  or is an overlay that pushes nothing.
- Never animate `height`, `width`, `top`, `left`, `margin` or `padding` on scroll. Use
  `transform`, or `interpolate-size: allow-keywords` when a real height animation is needed.
- Sticky headers change size on scroll only with `transform`, never by changing layout.
- A skeleton must have the same box as the content that replaces it. A skeleton that is
  taller or shorter is a shift you built on purpose.

## 5. INP: the interface answers immediately

- Show the state change first, do the work second. Optimistic UI is a design decision.
- Break work over 50ms with `scheduler.yield()` or an equivalent. Move heavy computation to
  a worker.
- Lists over roughly 50 rows: virtualise, or `content-visibility: auto` with
  `contain-intrinsic-size`.
- Controlled inputs must be cheap per keystroke. Debounce the search request, never the
  visible echo of what the user typed.
- No layout reads inside render. Batch reads, then writes.
- `will-change` on at most a couple of elements, and only while they animate. Permanent
  `will-change` is a permanent cost.
- `backdrop-filter` and large `blur()` are the two most expensive effects in modern CSS.
  One glass surface is a highlight. Four is a frame rate problem on a mid-range phone.

## 6. Measure honestly

A ladder. Take the highest rung the environment allows, and say which rung you used.

1. **Field data** (CrUX, real-user monitoring) tells you what users actually get. Page level
   first, origin level only as a labelled fallback.
2. **Lab data** (a browser trace, Lighthouse, a DevTools recording) tells you the cause. State
   the conditions: device profile, network throttle, cold or warm.
3. **Static reading** of the code produces *hypotheses*. Nothing more. Say the word.

Rules that keep a report trustworthy:

- Never present a lab number as a real-user number.
- Never claim a field improvement right after a fix. Field data needs new visits.
- A Lighthouse score of 100 is not proof of anything except that the audits passed.
- Compare like with like: same page, same device profile, same network, three runs, median.

When no page can run, write findings as `hypothesis: <cause> because <evidence in code>`,
and name the one command or browser step that would confirm it.

## 7. The design decisions that usually cost the most

| Decision | Cost | Cheaper version that keeps the look |
|---|---|---|
| Three font families, seven weights | 200 KB and a late headline | two families, four weights, subset to the scripts used |
| Full-bleed photographic hero, unoptimised | LCP over 4s | modern format, `srcset`, dominant-colour ground behind it |
| Scroll-driven animation on the main thread | jank on every mid-range device | `animation-timeline: view()`, or nothing |
| Glass on every surface | frame drops, unreadable text | one glass surface, solid elsewhere |
| Animated GIF | megabytes for a few seconds | muted, looping, `playsinline` video with a still fallback |
| An icon library imported whole | 60 KB of unused paths | import the icons used, or inline the SVG |
| A component library for four components | a build step and a bundle | write the four components |
| Client-rendered marketing page | slow first paint, no crawlability | static output, hydrate only what interacts |

## 8. Verify

```bash
node scripts/wig.mjs .        # missing dimensions, lazy hero, GIFs, layout reads, fonts
node scripts/check.mjs .      # transition: all, layout animation, scroll listeners
```

Then, if a page can run: one trace or one Lighthouse run, cold, mobile profile. Read only
the insight tied to the failing metric. Fix. Re-measure the same way once.

Checklist before the report:

- [ ] The LCP element is named and is not lazy.
- [ ] Every image and embed has a reserved box.
- [ ] Fonts: two families maximum, `preload` for the above-fold weight, `swap` set.
- [ ] Nothing animates layout. Reduced motion honoured.
- [ ] The longest list is virtualised or contained.
- [ ] Numbers in the report carry their measurement rung and conditions.

## Output of this gate

One line in the G7 report when performance mattered: the metric, the number, the rung it
came from. For example: `LCP 1.9s lab, mobile profile, cold, hero preloaded`. No score
badges, no claims about real users you have not observed.
