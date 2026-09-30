# Measuring xhtml2pdf

Nothing here is part of the library or runs in CI. These are the tools used to
find out where a render spends its time, and to show that a change to the
pipeline did not change what comes out of it.

```
make perf                  # the fixture corpus, phase by phase
make perf-scaling          # the synthetic ladder, to see how cost grows
make perf-golden-update    # record the current output as the reference
make perf-golden           # check it still renders byte for byte

python tools/perf/bench.py --counters        # work done, not time taken
python tools/perf/bench.py --json after.json
python tools/perf/bench.py --compare after.json
python tools/perf/bench.py --memory               # peak memory, not time
python tools/perf/bench.py --large                # documents that grow until they hurt
python tools/perf/bench.py --large --memory
python tools/perf/bench.py --leak 20              # what 20 renders leave behind
python tools/perf/profile_doc.py test-loremipsum
python tools/perf/profile_doc.py large-table-256
```

## Why there are two kinds of number

A timing on this hardware moves by tens of percent between runs -- a governor
that scales frequency, another process on the machine, a garbage collection
landing mid render. `bench.py` reports the fastest of several renders rather
than the mean, because every source of noise only makes a render slower, but
even so two runs minutes apart are not reliably comparable.

`bench.py --counters` reports units of work instead: how many elements
CSSCollect dressed, how many of those missed its cache, how many times a
ruleset was asked about a property, and how many selectors were evaluated.
Those numbers are exactly reproducible. An optimisation that is meant to do
less work shows up there first and in the clock second, and a change that
moves the clock without moving them is measuring the machine.

To compare two revisions honestly, run them alternately rather than one after
the other, so machine drift lands on both. Note that running `bench.py` as a
script puts `tools/perf` on `sys.path`, not the working directory, so an
editable install wins: measuring a checkout in a git worktree needs
`PYTHONPATH` pointing at that worktree.

## Where the time went

Profiling the pipeline as of this work, the dominant cost was resolving CSS,
and it was **O(elements x properties x rules)**. `CSSCollect`
(`xhtml2pdf/parser.py`) asked the cascade for each of the 60 registered
properties separately; each question rebuilt the list of cascade levels and
scanned every rule in every ruleset. On the fixture corpus that was 30-48% of
the total render time, and roughly half of everything before ReportLab.

The rest of the pipeline was not the problem. Parsing the HTML with html5lib
is 1-8% of a render. Parsing the CSS is 1-3%. What is left over is ReportLab,
and in documents dominated by text or embedded fonts it is nearly all of it.

## What changed

Three things, in `xhtml2pdf/w3c/css.py` and `xhtml2pdf/parser.py`:

1. **Rules are filed under a condition their element must meet** -- its id,
   failing that one of its classes, failing that its tag, with a bucket for
   rules that can apply to anything. A lookup evaluates the few rules in the
   element's own buckets instead of the whole stylesheet. The index only
   narrows the field: `selector.matches` still decides, so the index can cost
   a rule its place in the candidate list but can never give one a match it
   did not have.

2. **An element is resolved in one walk of the cascade**
   (`CSSCascadeStrategy.findStylesForElement`) rather than sixty. Each
   candidate selector is evaluated once, and the rules it brings are spread
   across whichever properties they declare.

3. **`CSSAttrs` carries no Python-level method in front of a lookup.** The
   warning about reading an unregistered property, which used to run on every
   access, moved to `_CheckedCSSAttrs` behind `XHTML2PDF_CHECK_CSS_PROPERTIES`
   -- and what it was really guarding is now a static check in
   `tests/test_parser.py`, which reads the property names this package asks
   for straight out of the source. That catches the unreachable branch without
   needing a document to reach it.

Plus some smaller things in the walker: a `path` argument that was built for
every element and never read, a `reversed()` whose result was discarded, and
three concatenations of the same two frag lists per paragraph.

### Work done, per render

| document | ruleset lookups | | selector matches | |
|---|---:|---:|---:|---:|
| | before | after | before | after |
| css-selectors.html | 3,500 | 0 | 5,402 | 103 |
| test-list.html | 8,712 | 0 | 10,848 | 171 |
| test-tables.html | 6,216 | 0 | 8,694 | 37 |
| test-loremipsum.html | 32,436 | 2,640 | 124,758 | 6,006 |
| utf8.html | 924 | 0 | 1,148 | 5 |

(loremipsum still reaches a ruleset because a value of `inherit` is handed
back to the per-property path; see the note below.)

### Time, fixtures

Fastest of five renders, three rounds, the two revisions run alternately.

| document | before | after | | CSSCollect before | after |
|---|---:|---:|---:|---:|---:|
| test-loremipsum.html | 408.5 ms | 223.7 ms | -45% | 206.9 ms | 30.7 ms |
| list-blocks.html | 45.7 ms | 24.7 ms | -46% | 20.5 ms | 2.7 ms |
| css-selectors.html | 22.2 ms | 13.3 ms | -40% | 10.2 ms | 1.6 ms |
| test-list.html | 56.3 ms | 33.8 ms | -40% | 22.9 ms | 3.0 ms |
| test-table-css.html | 9.6 ms | 5.8 ms | -39% | 4.0 ms | 0.5 ms |
| test-tables.html | 55.3 ms | 37.1 ms | -33% | 18.4 ms | 2.0 ms |
| test-letter.html | 43.5 ms | 37.3 ms | -14% | 6.8 ms | 0.9 ms |
| test-keep-in-frame.html | 98.8 ms | 89.1 ms | -10% | 13.0 ms | 1.7 ms |
| test-keep-with-next.html | 64.6 ms | 63.2 ms | -2% | 4.2 ms | 0.9 ms |
| utf8.html | 222.2 ms | 225.4 ms | +1% | 2.4 ms | 0.4 ms |

CSSCollect itself is 6-9x faster everywhere. How much of the render that is
worth depends on the document: the last three spend their time in ReportLab,
so making the cascade free would barely move them.

### Time, scaling

Each node carries a class of its own, so nothing is answered from
`CSSCollect`'s cache and every element pays the full cascade.

| nodes = rules | before | ms/node | after | ms/node |
|---:|---:|---:|---:|---:|
| 100 | 127.7 ms | 1.28 | 49.2 ms | 0.49 |
| 200 | 335.6 ms | 1.68 | 93.6 ms | 0.47 |
| 400 | 1,068.7 ms | 2.67 | 185.5 ms | 0.46 |
| 800 | 3,649.0 ms | 4.56 | 392.0 ms | 0.49 |

This is the point of the exercise. The cost per element used to grow with the
size of the stylesheet; now it does not. Eight times the input took 29 times
as long before and 8 times as long after.

## How a change is shown to be safe

`reportlab.rl_config.invariant` makes a render repeatable, so two renders of
the same document from the same code are identical byte for byte.
`golden.py` records a sha256 per fixture before a change and re-checks it
after -- which catches one property resolving differently on one element,
where a rasterised comparison would round it away.

Second net, and the one that covers all 30 fixtures rather than 10: build
`testrender`'s reference from the commit *before* the change
(`cd testrender && python testrender.py --create-reference data/reference`),
then `make test-render` after it. `make test-render-all` builds the reference
from the same commit it then compares against, so on its own it only proves
determinism -- the Makefile says as much.

Every step of this work was checked against both, plus `make test`.

### One caveat about golden.py

A rendered PDF is repeatable within one hash seed, not across seeds: ReportLab
names an image XObject after a digest of `'%s%s' % (image, mask)`, and the
image object falls back to a default `repr` carrying its memory address. Two
processes with different `PYTHONHASHSEED` therefore produce different bytes for
the same document. `golden.py` re-executes itself with the seed pinned rather
than compare hashes that were never going to match. It is worth fixing at the
source -- a PDF that is not reproducible cannot be diffed by anyone -- but that
is a change to what is written, not to how fast it is written, so it was left
alone here.

## Embedded fonts

Measured against a gallery of 40 real documents (invoices, tickets, books,
brochures -- the sibling `xhtml2pdf_examples` project, whose `tools/bench.py`
reports the same phases as this one), a second hot spot showed up that the
fixtures here never reach, because almost none of them embed a font.

`parseCSS` was costing a flat 90-115 ms in nearly every document, and 200 ms in
the ones with CJK. Almost all of it was `@font-face`: building a ReportLab
`TTFont` reads and parses the whole file, and a family in four weights pays it
four times.

It was also entirely wasted from the second document onwards.
`pdfmetrics.registerFont` keeps whichever object is already registered under a
dynamic font's name, so every render after the first built its fonts and had
them discarded on arrival -- the document went on using the objects the first
render had registered. `registerTTFont` in `xhtml2pdf/context.py` now asks
before building.

Across that gallery: `parseCSS` 3.71 s -> 0.47 s, of which time inside `TTFont`
went 3.23 s -> 0 s, and the whole run 14.9 s -> 12.6 s. All 39 deterministic
documents came out byte for byte identical (the fortieth carries a signature
timestamp and differs from itself).

The gain is across documents, not within one: a process that converts a single
file still parses each font once, because it has to.

## Second round: memory, and what ReportLab is asked twice

October 2026, after flex, inline-block, positioning, block boxes and two
rounds of findings had landed. Nothing measured memory until then, and the
fixtures are too small to show it, so `bench.py` grew `--memory` (tracemalloc
peak, what is still alive after the render, RSS), `--leak N`, and `--large`:
1,000-10,000 paragraphs, a table of 256-4,096 rows, 200 pages under a header
and footer with `pdf:pagecount`, 200 repeated images.

### Memory

A long document cost about 37 KB a paragraph and 100 KB a table row. Nearly
all of it was frags: each carried all 93 of its attributes, 3.3 KB of dict,
and every element and every run of text clones one. The root frag's values
now live on a class made for each render (`context._with_defaults`), a clone
copies only what its element changed, and `properties.compact_frag` drops the
immutable values an element wrote back unchanged. A text frag holds about 17
attributes. Separately, the DOM outlived the walk -- `context.node` and the
cascade cache's keys, which name each element's parent, kept it reachable
through the whole build -- and is now released and unlinked once the story is
built.

| document | peak before | after |
|---|---:|---:|
| large-text-1000 | 37.4 MB | 14.4 MB |
| large-text-10000 | 371.4 MB | 141.7 MB |
| large-table-256 | 26.2 MB | 14.3 MB |
| large-pages-200 | 32.2 MB | 16.0 MB |
| large-images-200 | 9.0 MB | 5.8 MB |
| gallery, 59 documents summed | 499 MB | 427 MB |

`--leak 20` finds nothing growing across renders: objects, memoized entries
and registered fonts stay flat.

### Time

Four things, each byte for byte the same output:

1. **Each word measured once per render** (`util.stringWidth`, dropped by
   `reset_caches`). `utf8.html` went from 31,566 width computations to 3,780.
2. **A paragraph's lines broken once per width** (`Paragraph._brokenLines`).
   A table sizes and then places each cell, a frame measures what it then
   adds, `multiBuild` lays the story out once per pass: 40% of `breakLines`
   calls in a long table and 59% in the paged document were exact repeats.
3. **Frames, paragraphs, styles and frags deep-copied directly**
   (`DeepCopiedDirectly`). ReportLab deep-copies the current frame for every
   cell it measures, and every page copies each static frame's story;
   through `__reduce_ex__` that was a fifth of a long table's profile.
4. **Glyph coverage asked per set, not per character**, for every fragment.

Fastest of five renders, three rounds, revisions alternated, against the
commit before this round:

| document | before | after | |
|---|---:|---:|---:|
| utf8.html | 229.4 ms | 141.5 ms | -38% |
| test-keep-in-frame.html | 97.7 ms | 60.0 ms | -39% |
| test-keep-with-next.html | 64.2 ms | 39.5 ms | -38% |
| test-letter.html | 39.4 ms | 27.0 ms | -32% |
| test-tables.html | 42.7 ms | 32.5 ms | -24% |
| test-loremipsum.html | 262.3 ms | 228.6 ms | -13% |
| test-list.html | 46.1 ms | 41.4 ms | -10% |
| large-pages-200 | 2,531 ms | 1,586 ms | -37% |
| large-table-1024 | 4,980 ms | 3,412 ms | -31% |
| large-text-10000 | 14,362 ms | 10,948 ms | -24% |
| large-images-200 | 468 ms | 375 ms | -20% |

### Checking the gallery

Byte comparison does not work there: 23 of its documents differ from
themselves between two processes even with `PYTHONHASHSEED` pinned (an image
XObject is named after an object's address, see the caveat above). They were
compared as rasters at 60 dpi instead, page by page, and only
`security-limits` differs -- from itself as well.

## What is still on the table

**Left after the second round, each changing bytes on purpose:** ReportLab
encodes every stream in ASCII85, in pure Python -- `rl_config.useA85 = 0`
was 3-12% faster and 12-20% smaller in a trial, but it is a process-wide
switch. A static frame with no page number is laid out and drawn again on
every page, where it could be drawn once into a form XObject. And a
`<pdf:nextpage />` is not a void element to html5lib, so everything after
it nests one level deeper; 200 of them made `elementInScope` a tenth of the
parse.

**ReportLab is now the ceiling.** In `utf8.html` 213 ms of 225 ms is
ReportLab, and in `test-keep-in-frame.html` 70 ms of 89 ms. Inside it the cost
is `breakLines` in `xhtml2pdf/reportlab_paragraph.py` calling `stringWidth`
once per word per wrap attempt. ReportLab 5.0.1 ships no C accelerator here --
`_rl_accel` is absent and the pure-Python `_py_instanceStringWidthT1` runs
instead -- so each of those calls encodes the string and sums a width table in
Python. A cache keyed by (text, font, size) in that fork is the obvious next
move. It shares no files and no tests with the cascade, so it belongs in its
own change.

**Two bugs found while measuring, both left alone deliberately**, because
fixing either changes rendered output and this work was meant not to:

- `getCSSAttr` in `xhtml2pdf/parser.py` resolves `inherit` from the parent
  element and then raises `LookupError` regardless, which `CSSCollect` logs at
  debug and moves past, so the property is simply dropped: `em { color:
  inherit }` leaves `color` unset on the em. Often invisible, because a frag
  takes its parent's value anyway -- but an `inherit` written to override a
  more specific rule does nothing at all.
- Nothing checks that a font-family name refers to the same file it did last
  time. A process that renders one document declaring `@font-face { font-family:
  Body; src: url(a.ttf) }` and then another declaring the same family from
  `b.ttf` draws the second with `a.ttf`. That is ReportLab's global registry
  and predates any of this work; `registerTTFont` documents it rather than
  changing it.
- Neither the CSS parser nor `CSSSelectorBase.matches` lowercases a tag name,
  while the HTML parser lowercases them in the DOM, so `DIV { color: red }` never
  reaches a `<div>` while `div { ... }` does. `tests/test_selectors.py`
  records this as it stands rather than as it ought to be.
