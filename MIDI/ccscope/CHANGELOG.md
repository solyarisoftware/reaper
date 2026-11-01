# Changelog

Notable changes only — what someone using the plugin would notice. For the full
history, including every intermediate step, `git log`.

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
