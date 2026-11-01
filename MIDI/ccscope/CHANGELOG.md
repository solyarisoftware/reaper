# Changelog

Notable changes only — what someone using the plugin would notice. For the full
history, including every intermediate step, `git log`.

## 0.7.3 — 2026-11-01

- **The bar sits on the window's own black**, not on a lighter strip: the cells are what carry
  an edge, and the plot's margins and the bar are now the same surface. A hairline under the
  bar keeps the two apart without drawing a second frame.
- **The first cell starts on the plot's left edge** (`PLOT_LEFT`, 35 px — measured: the cell
  border and the plot frame land on the same pixel column). One vertical line runs from the
  bar through the plot's frame, and the bar no longer starts 27 px to the left of everything
  else.
- **The caret brightens with its cell.** It is the part that promises a list, so it now answers
  the pointer instead of staying dim while the cell lights up.
- **A hairline separates selectors from buttons**: five cells open a list, two act. The gap
  alone did not say that.

## 0.7.2 — 2026-11-01

- **The metrics are three columns, not a sentence.** `Messages`, `Motion` and `Timing` start
  at fixed x, and inside each field the number is aligned at its right edge: `6`, `16` and
  `123` end on the same pixel, and `fast`/`moderate`/`erratic` sit in a fixed-width field of
  their own instead of pushing everything after them. The old rows were one `sprintf` with
  double spaces, and in a proportional font no number of spaces aligns anything.
- **Each number travels with its unit** (`250 u/s`, `±20.7ms`) and is right-aligned as one
  string. The suffix has a constant width, so the digits line up by construction — no
  per-digit padding, and nothing that can shift a column when a value grows.
- **The four forms are unchanged, and now chosen by measurement.** Labels + quality words,
  labels only, values only (the column beside the plot), count only: the width of the reserved
  fields decides, once per layout, instead of the text of one row deciding per row — which is
  what used to make the same row change shape when a value crossed 99.
- **A value wider than its reserve grows left**, into the gap, without moving the columns after
  it: alignment is what has to hold, not the gap.

## 0.7.1 — 2026-11-01

- **No behavioural change: a packaging fix.** The ReaPack index publishes the `@changelog`
  block inside the JSFX, not this file, and that block still started at 0.6.4 when 0.7.0 was
  indexed — so 0.7.0 was published with the previous version's notes. The block is correct
  now; this release exists so the index can carry it. (`reapack-index` does not re-index a
  version it has already published: it reported `Nothing to do!`.)

## 0.7.0 — 2026-11-01

- **The sliders are gone; the plugin draws its own controls.** Every slider is declared with a
  leading `-` in its name, which hides REAPER's strip and keeps the parameter alive: still
  automatable, still saved in presets, still listed by the FX window's **Param** button. In
  their place a bar of seven cells sits at the top of the canvas: `CC`, `CH`, `WIN`, `DOTS`,
  `ROWS`, `FREEZE`, `CLEAR`.
- **Measured: the strip was costing 190 px of window height** (REAPER 7.84, 1016 px wide) — about
  eleven rows of pairs, or 37 rows instead of 26 at the same window size. Hiding it hands the
  space to the plot and the list.
- **Interaction without a keyboard**, because a JSFX cannot ask for one: click a cell with a
  caret to open its list, the wheel steps the value (one notch = one step: the raw host delta
  is 120 per notch, which took the time window from 10 s to 30 s in a single turn), a right
  click restores the default.
- **The bar degrades instead of clipping**: in a narrow window the cell labels are dropped
  first — `FREEZE` and `CLEAR` keep theirs, because their text *is* the button.
- **Two EEL2 traps, found the hard way.** `loop()` is not reentrant, so a hit test written as a
  loop inside the loop that draws the cells corrupts the counter and the frame stops halfway;
  the hit test is now a chain. And two arrays (`g_ctl_x[8]` / `g_ctl_w[8]`) were given the same
  memory — every cell was placed at its own width — so the geometry lives in `mem[]`, in the
  two ranges the memory-map checker verifies.

## 0.6.5 — 2026-11-01

- **The `now` edge is one line again.** The right border of the plot was solid, as it should
  be, but the time ruler also drew a tick there — one pixel to its right, dashed. At "now"
  the two read as a straight line with a broken line beside it. The ruler now skips the ticks
  that land on the frame, at both edges: the border *is* the line, so the tick that would sit
  on it has nothing to add. A 10 s window still shows its nine interior ticks.

## 0.6.4 — 2026-11-01

- **Slider 7, `Pair list layout`: the list can sit beside the plot.** Requested in the
  forum thread (*"a mode to list the chart on the right of the graph, this will leave you
  plenty of vertical room for a lot of CC"*). The column takes the right edge, the rows keep
  the 16 px they have below the plot, and the plot keeps the whole window height. Measured on
  the 20-pair demo at 1016×600: **10 pairs visible with the list below, 18 beside** — which
  is the point, because with the list below it is the plot's floor that caps the rows.
- **The metrics in the column are the compact form** (`125 msg/s   247 mot   ±20.7ms`).
  Two-line rows were measured and rejected: at 34 px per row the column would show *fewer*
  pairs (19 instead of 41 at 1016×958) than the layout it replaces.
- **A narrow window falls back and says so.** The column needs ~717 px of width to leave the
  plot at least 240 px; below that the rows go back under the plot and the status line reads
  `rows beside need a wider window`, instead of the plugin quietly ignoring the slider.
- Row geometry now has one definition: `calculate_layout()` computes where the label, the
  bar, the value and the metrics start, and the bars, the tooltip hit test and both layouts
  read those coordinates instead of recomputing them.

## 0.6.3 — 2026-11-01

- **A taller window shows more pairs.** The bar area used to be capped at 35% of the
  height, a percentage: extending the window grew the plot and the bars together, so the
  number of visible (CC, channel) rows never increased and the rest were unreachable. The
  constraint is now a **floor on the plot** — the graph keeps at least 35% and the rows take
  the rest — so the rows grow with the window until every pair has one. Measured on a
  20-pair session in a 1016×958 window: 12 rows before, 20 after.
- When rows still do not fit, the status line says so and says what to do:
  `showing 8 of 20 pairs (taller window fits more)`.

## 0.6.2 — 2026-11-01

- **Channel filter (slider 6)**: `All` or one of the 16 channels, combining with the CC
  filter — *CC1 on channel 3*, *every CC on channel 3*, or *CC1 on every channel*. The two
  filters are applied while the visible (CC, channel) list is built, so the graph, the bars
  and the `showing N of M pairs` line all read the same list and cannot disagree — the
  failure mode of 0.5.2, when the bars ignored the CC filter.
- The status line says what it is waiting for, channel included.

## 0.6.1 — 2026-11-01

- **Fixes the packaging of 0.6.0**, which could not load: the package file was renamed
  before the two includes, so the release pointed at a `ccscope.jsfx` that imports
  `ccscope_utils.jsfx-inc` while the files were still `midi_cc_*.jsfx-inc`. Everything
  is renamed consistently from this version on. **Use 0.6.1.**

## 0.6.0 — 2026-11-01

- **Renamed to CCScope** (was "MIDI CC Visualizer"). Everything is new: the package
  file, the two includes (`ccscope_utils.jsfx-inc`, `ccscope_metrics.jsfx-inc`) and the
  screenshot. No path is shared with 0.5.2, so the old package can be uninstalled when
  convenient — ReaPack will offer to do it, since 0.5.2 is no longer in the repository.
- **One colour per (CC, channel)**: the hue belongs to the CC, the channel changes the
  shade, so two channels of the same CC are no longer drawn identically.
- **Readable at a glance**: labelled time axis, the grid is a scale (0 / 64 / 127 on the
  frame, dashed guides at the quarters), metrics that shorten instead of running off the
  edge, the value printed next to each bar, and a hover panel that explains the numbers.
- **Numbers named for what they mean**: Messages, Motion, Timing, with words a musician
  reads (slow … fast, steady … erratic) instead of engineering terms.
- **Metrics corrected**: the window is exactly one second (counts were up to 10% high),
  up to 500 events/s per pair instead of 200, jitter ignores gaps and declares how many
  intervals it used, `n/a` when there are too few to mean anything.
- **Freeze and Clear**: Freeze stops acquisition while MIDI keeps flowing; Clear resets
  history and metrics and keeps the rows.
- **Dots on the traces** are a choice: Auto (one every 12 px), Every event, None.

## 0.5.2 — 2026-10-27

Correctness pass, no new features:

- the (CC, channel) key no longer overflows its memory range — from CC 10 upwards it was
  writing into the active flags, colours, history and metrics areas
- slider 1 filters the graph and the bars together; a filtered CC with no data says so
- bars cannot be drawn under the status line
- the metrics block is sized from its layout instead of being typed by hand
- events carry their own timestamp on the audio-sample clock: jitter was quantised to the
  audio block, and offset by the audio callback's scheduling

## 0.5.1 — 2026-10-25

- cleaner bar layout: explicit `Events` / `Rate` / `Jitter` labels, no pipe separators

## 0.5 — 2025-11-22

- multi-channel support: CC data, colours and metrics tracked per (CC, channel)

Releases before 0.5 predate this repository.
