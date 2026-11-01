# Changelog

Notable changes only — what someone using the plugin would notice. For the full
history, including every intermediate step, `git log`.

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
