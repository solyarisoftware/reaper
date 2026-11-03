# Changelog

Notable changes only — what someone using the plugin would notice. For the full history,
including every intermediate step, `git log`.

## 0.7.6 — 2026-11-03

- **History spans the requested time window:** a per-pair 100 ms temporal ring
  retains up to 30 s independently of aggregate event rate. First/last values
  and ordered min/max survive aggregation; spikes are retained as an envelope,
  not exact timestamped events. A partially visible boundary bucket has up to
  100 ms of temporal uncertainty.
- `DOTS` now explicitly refers to retained points. Freeze stops acquisition;
  Clear invalidates all temporal history in constant time, and changing `WIN`
  does not erase previously acquired data. Metrics and MIDI pass-through are
  unchanged. Declared memory fits the default 8M-slot JSFX capacity.
- Native retention/renderer checks and live validation:
  https://github.com/solyarisoftware/reaper/issues/5

## 0.7.5 — 2026-11-03

- **Less per-frame graph work**: one history traversal builds the per-pair point lists,
  the static grid is cached, and count-only rows skip undisplayed metric calculations.
  Pair draw order, coordinates and dot spacing are preserved; oversized canvases draw
  the grid directly.
- History capacity and the requested GUI refresh rate are unchanged. Measurements,
  native validation and coverage limits: https://github.com/solyarisoftware/reaper/issues/23

## 0.7.4 — 2026-11-01

- **The bar spans the plot**: the first cell starts on the plot's left edge and `FREEZE`/`CLEAR`
  sit flush with its right edge (measured: cell border and frame land on pixel columns 43 and
  991 in a 1016 px window). In a narrow window the two buttons follow the selectors instead.
- **Cut corners and one amber state**: a two-pixel chamfer for the rounded corner JSFX cannot
  draw, and the engaged button turns amber including its border.
- Less chrome: the rule under the bar and the hairline between selectors and buttons are gone;
  with labels on, the value sits against the caret, so a cell whose value grows keeps its text.

## 0.7.3 — 2026-11-01

- **The bar sits on the window's own black**, and its first cell starts on the plot's left edge:
  one vertical line through the whole plugin (measured: same pixel column).
- A hairline separates the five selectors from the two buttons, and the caret brightens with its
  cell.

## 0.7.2 — 2026-11-01

- **The metrics are three columns**: each label starts at a fixed x, each number is right-aligned,
  so `6`, `16` and `123` end on the same pixel and a changing value never moves the row. The four
  forms (labels with quality words, labels only, values only, count only) are chosen by the width
  of the reserved fields, not by the text of a row.
- A value wider than its reserve grows left, into the gap: alignment holds, the gap gives.

## 0.7.1 — 2026-11-01

- **No behavioural change: a packaging fix.** The index publishes the JSFX header block, which
  still started at 0.6.4 when 0.7.0 was indexed, so 0.7.0 shipped with the previous notes.

## 0.7.0 — 2026-11-01

- **The sliders are gone and the plugin draws a control bar**: seven cells (`CC`, `CH`, `WIN`,
  `DOTS`, `ROWS`, `FREEZE`, `CLEAR`). Click opens a list, the wheel steps, a right click resets.
  The parameters stay automatable, saved in presets and listed under **Param**.
- **Measured: the strip cost 190 px of window height** — 37 rows instead of 26 at the same window
  size (REAPER 7.84, 1016 px wide).
- In a narrow window the cell labels are dropped first; `FREEZE` and `CLEAR` keep theirs.

## 0.6.5 — 2026-11-01

- **The `now` edge is one line**: the ruler skips the ticks that would land on the frame, at both
  edges. A 10 s window still shows its nine interior ticks.

## 0.6.4 — 2026-11-01

- **Slider 7: the pair list can sit beside the plot**, for windows that are wide and short.
  Measured on the 20-pair demo at 1016×600: **10 pairs visible below, 18 beside**.
- **Two-line rows were measured and rejected**: at 34 px per row the column would show *fewer*
  pairs (19 instead of 41 at 1016×958), so the column keeps one line and the compact metrics.
- **A narrow window falls back and says so**: the column needs ~717 px of width to leave the plot
  240 px; below that, `rows beside need a wider window`.

## 0.6.3 — 2026-11-01

- **A taller window shows more pairs.** The bar area was capped at 35% of the height; the
  constraint is now a floor on the plot, so the rows grow with the window until every pair has
  one. Measured on a 20-pair session at 1016×958: 12 rows before, 20 after.
- When rows still do not fit, the status line says so: `showing 8 of 20 pairs (taller window fits
  more)`.

## 0.6.2 — 2026-11-01

- **Channel filter** (slider 6), combining with the CC filter. Both are applied while the visible
  pair list is built, so the graph, the bars and the `showing N of M` line cannot disagree.

## 0.6.1 — 2026-11-01

- **Packaging fix**: 0.6.0 pointed at renamed includes it did not ship, so it could not load.
  Every file is consistent from this version on. **Use 0.6.1.**

## 0.6.0 — 2026-11-01

- **Renamed to CCScope**, with a new package file and includes: uninstall the old "MIDI CC
  Visualizer". No path is shared with 0.5.2, so ReaPack offers to remove it.
- **One colour per (CC, channel)**, a labelled time axis, a scale on the frame, the value next to
  each bar, a hover panel, and the numbers named **Messages / Motion / Timing**.
- **Metrics corrected**: exactly one second (counts were up to 10% high), 500 events/s per pair
  instead of 200, jitter that ignores gaps, says how many intervals it used, and `n/a` when there
  are too few.
- **Freeze, Clear**, and `DOTS` as a choice (auto, every event, none).

## 0.5.2 — 2026-10-27

Correctness pass, no new features: the (CC, channel) key no longer overflows its memory range
(from CC 10 upwards it wrote into flags, colours, history and metrics); slider 1 filters the graph
and the bars together; bars cannot be drawn under the status line; events carry their own
timestamp on the audio-sample clock, so jitter is no longer quantised to the audio block.

## 0.5.1 — 2026-10-25

- Cleaner bar layout: explicit `Events` / `Rate` / `Jitter` labels, no pipe separators.

## 0.5 — 2025-11-22

- Multi-channel support: CC data, colours and metrics tracked per (CC, channel).

Releases before 0.5 predate this repository.
