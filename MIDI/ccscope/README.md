# CCScope — MIDI CC oscilloscope and fader bars

A JSFX effect for REAPER 6.37 or newer.

![CCScope in REAPER: a controller being moved, one bar per CC](ccscope.gif)

Recorded in REAPER: one fader gesture, four CC streams (four shades of colour), the
metrics updating live. The static screenshot used by ReaPack is [`ccscope.png`](ccscope.png).

Two display modes: a scrolling time graph and one fader bar per active CC. Each CC number is
tracked **per MIDI channel**, so the same CC from different channels is shown and measured
separately — same hue per CC, a different shade per channel, and the row label carries the
colour.

- **Slider 1** — CC to monitor (`0` = all CCs, `1-127` = one CC)
- **Slider 2** — Freeze: stops acquisition (MIDI still passes through) so a reading can be examined
- **Slider 3** — time window, 1–30 s; the time axis is labelled from `-10s` to `now`
- **Slider 4** — Clear history and metrics; it returns itself to `0`

Three numbers per row, named after what they mean rather than how they are computed. Pointing at
them explains them on screen:

| | what it says |
|---|---|
| **Messages** | how many times per second the controller sends — its update rate |
| **Motion** | how far the value (0–127) travels per second — how fast the gesture is; rated slow, moderate, brisk, fast |
| **Timing** | how much the spacing between messages wobbles, in ms — rated steady, even, uneven, loose, erratic, and shown with the number of intervals it was computed on. Gaps (a pause, a loop jump) are not counted as jitter, and `n/a` means there were too few intervals to say |

The window is exactly one second, filtered on read, so a rate of 240/s is what the plugin was
measuring and not what happened to be in a buffer.

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

## Changelog and roadmap

- [CHANGELOG.md](CHANGELOG.md) — what changed, release by release
- [TODO.md](TODO.md) — what is missing: the issues, the forum requests, the ideas
