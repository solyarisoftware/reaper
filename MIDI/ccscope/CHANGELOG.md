# Changelog

Notable changes only — what someone using the plugin would notice. One entry per release, one
line per change; the reasoning and the measurements behind each one live in the linked issue or
discussion, or in `git log`.

## 0.7.9 — 2026-11-04

- Documentation release, no change in behaviour: a shorter README aimed at the user, one-line
  changelog entries, and a ReaPack description that no longer describes sliders (hidden since
  0.7.0). The roadmap is now Issues and Discussions only, so `TODO.md` is gone.

## 0.7.8 — 2026-11-03

- **CC ramps draw as straight diagonals** instead of an artificial staircase; genuine peaks,
  troughs and clipped boundary envelopes are still visible. History format, memory, metrics and
  MIDI pass-through unchanged.

## 0.7.7 — 2026-11-03

- **Nothing visible changed**: the plugin is now one conductor plus five library files, so a
  change touches one file. Update through ReaPack — copying `ccscope.jsfx` alone gives a plugin
  that will not load.

## 0.7.6 — 2026-11-03

- **History now spans the whole chosen time window** at any event rate, and changing `WIN` no
  longer erases what was already retained. Spikes are kept as an envelope, with up to 100 ms of
  timing uncertainty at a bucket boundary.
- Validation and limits: [#5](https://github.com/solyarisoftware/reaper/issues/5).

## 0.7.5 — 2026-11-03

- **Less work per frame**, same picture: cheaper redraws on busy sessions and on large windows.
  Capacity and GUI refresh rate unchanged. [#23](https://github.com/solyarisoftware/reaper/issues/23)

## 0.7.4 — 2026-11-01

- **The control bar spans the plot**, flush left and right, with cut corners; the engaged button
  turns amber, border included. In a narrow window the two buttons follow the selectors.

## 0.7.3 — 2026-11-01

- **The bar sits on the window's own black**, aligned with the plot's left edge: one vertical
  line through the whole plugin.

## 0.7.2 — 2026-11-01

- **The metrics no longer shift while the numbers change**: three fixed columns, numbers
  right-aligned, so `6`, `16` and `123` end on the same pixel.

## 0.7.1 — 2026-11-01

- **No change in behaviour: a packaging fix.** 0.7.0 was published with the previous release
  notes.

## 0.7.0 — 2026-11-01

- **The plugin draws its own controls**: seven cells (`CC`, `CH`, `WIN`, `DOTS`, `ROWS`,
  `FREEZE`, `CLEAR`) replace REAPER's slider strip, which cost 190 px of window height — about
  eleven more rows of pairs. The parameters stay automatable, in presets and under **Param**.

## 0.6.5 — 2026-11-01

- The `now` edge of the graph is a single line: the ruler no longer stacks a tick on the frame.

## 0.6.4 — 2026-11-01

- **The pair list can sit beside the plot** instead of below it, which roughly doubles the pairs
  a short, wide window shows. Too narrow a window falls back to the list below and says so.

## 0.6.3 — 2026-11-01

- **A taller window shows more pairs**, not just a taller graph. When rows still do not fit, the
  status line says how many are on screen and that a taller window fits more.

## 0.6.2 — 2026-11-01

- **Channel filter**, combining with the CC filter. Graph, bars and the `showing N of M` line all
  read the same filtered list, so they cannot disagree.

## 0.6.1 — 2026-11-01

- **Packaging fix**: 0.6.0 could not load. **Use 0.6.1 or newer.**

## 0.6.0 — 2026-11-01

- **Renamed to CCScope** (was "MIDI CC Visualizer"): uninstall the old package, ReaPack offers
  to remove it.
- One colour per (CC, channel), a labelled time axis, the value next to each bar, a hover panel,
  **Freeze** and **Clear**, and `DOTS` as a choice.
- **Metrics corrected**: exactly one second, 500 events/s per pair instead of 200, jitter that
  ignores gaps and says how many intervals it used, `n/a` when there are too few.

## 0.5.2 — 2026-10-27

Correctness pass, no new features: CC values above 9 no longer corrupted each other's data, one
filter for the graph and the bars, bars cannot be drawn under the status line, and jitter is
measured on the audio-sample clock instead of being quantised to the audio block.

## 0.5.1 — 2026-10-25

Cleaner bar layout: explicit `Events` / `Rate` / `Jitter` labels, no pipe separators.

## 0.5 — 2025-11-22

Multi-channel support: CC data, colours and metrics tracked per (CC, channel).

Releases before 0.5 predate this repository.
