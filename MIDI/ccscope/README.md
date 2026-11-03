# CCScope — MIDI CC oscilloscope and fader bars

A JSFX effect for REAPER 6.37 or newer. ReaPack has no metadata tag for a REAPER version
requirement, so this is a statement, not something the package manager can enforce.

![CCScope in REAPER: a controller being moved, one bar per CC](ccscope.gif)

Recorded in REAPER, real hardware: four faders (CC 1, 11, 17, 21) moved by hand, one colour
per CC, the metrics updating live and the columns staying aligned while the numbers change.
The static screenshot used by ReaPack is [`ccscope.png`](ccscope.png), a frame from the same
take.

Two display modes: a scrolling time graph and one fader bar per active CC. Each CC number is
tracked **per MIDI channel**, so the same CC from different channels is shown and measured
separately — same hue per CC, a different shade per channel, and the row label carries the
colour. The CC filter and the channel filter are independent and combine: one CC, one
channel, or one CC on one channel.

- **The control bar** — the seven parameters have no REAPER sliders: the sliders are declared
  with a leading `-` in their name, which hides them while keeping them automatable, saved in
  presets and listed by the FX window's **Param** button. In their place the plugin draws a bar
  of seven cells at the top of the canvas. Hiding the strip gives back **190 px** of window
  height (measured on REAPER 7.84), which is about eleven rows of pairs.
  - click a cell with a caret to open its list, **the wheel** steps the value, a **right click**
    restores the default;
  - `CC` (`all` or one controller), `CH` (`all` or one channel);
  - `WIN` — the time window, 1–30 s; the time axis is labelled from `-10s` to `now`;
  - `DOTS` — `auto` (one every 12 px), `every point`, `none`;
    points are retained representatives, not every original MIDI event;
  - `ROWS` — `below` or `beside` (see below);
  - `FREEZE` — stops acquisition (MIDI still passes through) so a reading can be examined;
  - `CLEAR` — wipes history and metrics.

  In a narrow window the cell labels are dropped first, and `FREEZE`/`CLEAR` keep theirs; below
  ~460 px of width the last cells are clipped, and at that size the plot is not much of a plot
  either. The bar spans the plot: the selectors start on its left edge and the two buttons sit
  flush with its right edge, so one vertical line runs from the controls down through the frame.
- **Temporal history (0.7.6):** each (CC, channel) owns 301 buckets
  of 100 ms, retaining the full maximum 30 s without competition from other
  pairs or a rate-dependent event limit. Each bucket retains first/last values
  and min/max, in extrema order. Extrema form a time-aggregated envelope, not
  exact event timestamps; a partially visible boundary bucket can include up
  to 100 ms of uncertainty. Changing `WIN` does not erase retained data.
  Empty buckets do not invent events; old tags expire by time. Total declared
  memory fits the default 8M JSFX slots (about 59.5 MB of doubles), so actual
  process memory can increase compared with the previous 2,000-event ring.
- The two filters (which CC, which channel) combine, so *CC1 on channel 3*, *every CC on
  channel 3* and *CC1 on every channel* are all selections; they share one list, and the graph
  and the bars read that list, so they cannot disagree about what is on screen.
- **Where the pair list lives** — **below** the plot (default) or **beside** it, as a column on
  the right. The column uses the whole window height and keeps the same 16 px per row, so one
  window shows more pairs than with the list below — measured at 1016×600: 10 pairs below, 18
  beside. Below ~720 px of window width the plot would be too narrow to be a plot, so the
  layout falls back to the rows below and the status line says
  `rows beside need a wider window`.

One row per (CC, channel) pair. With the list **below**, the rows take the height they need:
the plot keeps a minimum share of the window, so a taller window shows more pairs instead of
only a taller graph. With the list **beside**, the window height feeds the column and the plot
keeps the full height. In both cases, when rows still do not fit the status line says how
many are on screen and what to do about it.

Three numbers per row, named after what they mean rather than how they are computed. Pointing at
them explains them on screen:

| | what it says |
|---|---|
| **Messages** | received MIDI CC messages in the last second, including repeated identical values — not distinct values or physical movements |
| **Motion** | sum of absolute CC value changes associated with messages in the last second, in CC units/s; rated slow, moderate, brisk, fast. This is MIDI value travel, not physical fader speed; intentional movement, noise and jumps can all contribute |
| **Timing** | **Timing jitter:** standard deviation of accepted inter-message intervals, in ms; rated steady, even, uneven, loose, erratic. The hover panel shows the interval count. Intervals longer than four times the shortest interval in the window are excluded by a gap heuristic; `n/a` means fewer than four usable intervals |

They are drawn as **three columns**, not as a sentence: each label starts at a fixed x and each
number is aligned at its right edge, so `6`, `16` and `123` end on the same pixel and the quality
words (`fast`, `moderate`, `erratic`) sit in a fixed-width field of their own instead of pushing
what follows. A number that grows past its reserve grows to the left, into the gap, so the columns
never move. In a narrow window the columns keep their alignment but lose their words, in the same
order: `Messages 16/s   Motion 250 u/s   Timing ±0.0ms`, then `16/s   250 u/s   ±0.0ms`, then the
count alone. The first form is what shows in the default layout; the third is what the column
beside the plot uses, where 190 px hold the three numbers but no words.

The measurement window is one second, filtered on read, independently of the graph's 1–30 s
window. The metrics buffer holds 500 events per pair; readings are bounded by that capacity.

**Timing jitter is not value noise.** The graph can help spot oscillating CC values and sudden
jumps visually, but the plugin does not yet quantify stationary value noise or count large
steps. Timing describes message spacing; Motion cannot tell an intended gesture from a fault.
No incoming messages do not establish that a stationary fader is noise-free: some devices send
only when a value changes. These are observations of MIDI output, not physical calibration.

It was written for testing MIDI hardware: the numbers tell you whether a controller really
transmits at high resolution, whether its timing is stable, and how hard you are actually moving it.

## The hardware it was written for

![A four-fader MIDI controller](controller.jpg)

Four faders and four switches, each fader on its own CC (1, 11, 17, 21): the animation
above is this device. Photo and review are mine —
[Amazon.it](https://www.amazon.it/dp/B0FT2DSFHN).

It answers a question a MIDI logger does not: **how fast, and how regularly, does this
controller actually send?** That is `Messages/s` per CC and per channel, and it is what
makes the plugin useful beyond faders — to check a rate limit in a JSFX of your own, for
example.

## Discussion

Reports, questions and announcements happen in the REAPER forum thread, where the plugin
started: [CCScope — MIDI CC oscilloscope](https://forum.cockos.com/showthread.php?t=304766),
announced at 0.7.4 in
[post #21](https://forum.cockos.com/showpost.php?p=2972028&postcount=21).
Bugs and trackable requests are better as [issues](https://github.com/solyarisoftware/reaper/issues),
because a thread grows and forgets.

## Changelog and roadmap

- [CHANGELOG.md](CHANGELOG.md) — what changed, release by release
- [TODO.md](TODO.md) — what is missing: the issues, the forum requests, the ideas
- [Device testing proposal](docs/device-testing.md) — possible Hold/Sweep sessions for hardware
  evaluation; not implemented, with no release commitment
