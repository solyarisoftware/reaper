# CCScope — MIDI CC oscilloscope and fader tester

A JSFX for REAPER 6.37 or newer. It shows what a MIDI controller actually sends: the shape of
the movement over time, one fader bar per active CC, and how fast and how regularly each CC
transmits — on each MIDI channel separately.

![CCScope in REAPER: a controller being moved, one bar per CC](ccscope.gif)

Recorded in REAPER with real hardware: four faders (CC 1, 11, 17, 21) moved by hand, one colour
per CC, the metrics updating live. The static screenshot used by ReaPack is
[`ccscope.png`](ccscope.png), a frame from the same take.

## What it does

- **Two display modes**: a scrolling time graph (1–30 s window, labelled axis) and one fader bar
  per active CC with its current value.
- **Per (CC, channel)**: the same CC number on different channels is shown and measured as its
  own row — same hue per CC, a different shade per channel. The CC filter and the channel filter
  are independent and combine: one CC, one channel, or one CC on one channel.
- **Three measurements per row**, over exactly the last second: **Messages**, **Motion**,
  **Timing**. Pointing at them explains what they mean on screen.
- **Rows below or beside the plot**, so a window that is wide and short can still show every
  pair. In a narrow window the labels go first and the status line says what does not fit.
- **FREEZE** stops acquisition (MIDI keeps passing through) so a reading can be examined;
  **CLEAR** wipes history and metrics.
- **A status line under everything** says what the plugin is observing — `Waiting`,
  `Receiving`, `Idle` or `Frozen` — with the streams, channels and messages per second of the
  current selection, and the warnings when rows or the beside layout do not fit. The state word
  brightens while messages are arriving and dims when nothing has ever come. The package version
  sits at the right edge.
- **A control bar instead of REAPER's sliders** — `CC`, `CH`, `WIN`, `DOTS`, `ROWS`, `FREEZE`,
  `CLEAR` at the top of the canvas. Click a cell to open its list, the wheel steps the value, a
  right click restores the default. The parameters stay automatable, saved in presets and listed
  under **Param**.

### What the numbers mean

| | what it says |
|---|---|
| **Messages** | received MIDI CC messages in the last second, including repeated identical values — not distinct values or physical movements |
| **Motion** | sum of absolute CC value changes associated with messages in the last second, in CC units/s; rated slow, moderate, brisk, fast. This is MIDI value travel, not physical fader speed; intentional movement, noise and jumps can all contribute |
| **Timing** | **Timing jitter:** standard deviation of accepted inter-message intervals, in ms; rated steady, even, uneven, loose, erratic. The hover panel shows the interval count. Intervals longer than four times the shortest interval in the window are excluded by a gap heuristic; `n/a` means fewer than four usable intervals |

These are observations of MIDI output, not physical calibration. Timing describes message
spacing; Motion cannot tell an intended gesture from a fault. No incoming messages do not
establish that a stationary fader is noise-free: some devices send only when a value changes.

## The hardware it was written for

![A four-fader MIDI controller](controller.jpg)

Four faders and four switches, each fader on its own CC (1, 11, 17, 21): the animation above is
this device. Photo and review are mine —
[Amazon.it](https://www.amazon.it/dp/B0FT2DSFHN).

It answers a question a MIDI logger does not: **how fast, and how regularly, does this
controller actually send?** That is `Messages` per CC and per channel, and it is what makes the
plugin useful beyond faders — to check a rate limit in a JSFX of your own, for example.

## Install

Via ReaPack: *Extensions → ReaPack → Import a repository*, paste
`https://github.com/solyarisoftware/reaper/raw/master/index.xml`, then synchronize. The package
is in the `ccscope` category. Install it from ReaPack rather than copying `ccscope.jsfx`
alone: the plugin is one conductor plus its `.jsfx-inc` companions, and a missing include is a
plugin that will not load.

## Feedback, roadmap and history

- **Bugs and defined changes** — [issues](https://github.com/solyarisoftware/reaper/issues):
  a bug report with reproduction steps, or an `enhancement` issue with completion criteria.
- **Ideas and design questions** — [Discussions › Ideas](https://github.com/solyarisoftware/reaper/discussions/categories/ideas).
  That is where the roadmap is: what is being considered, what was decided and why. How to
  report is in [Discussion #16](https://github.com/solyarisoftware/reaper/discussions/16), the
  full guidelines in [CONTRIBUTING.md](../../CONTRIBUTING.md).
- **Forum** — the plugin started in the REAPER forum thread
  [CCScope — MIDI CC oscilloscope](https://forum.cockos.com/showthread.php?t=304766), announced
  at 0.7.4 in [post #21](https://forum.cockos.com/showpost.php?p=2972028&postcount=21).
- **History** — [CHANGELOG.md](CHANGELOG.md), one line per notable change.
- **Proposal, not implemented** —
  [Device testing](docs/device-testing.md): possible Hold/Sweep sessions for hardware
  evaluation, discussed in [Discussion #11](https://github.com/solyarisoftware/reaper/discussions/11).
