# TODO — what is missing

Bugs and concrete requests are GitHub [issues](../../issues); this page is the map,
including the ideas that are not issues yet.

## From the Cockos forum thread

The plugin began as a post in the REAPER forum
([thread 304766](https://forum.cockos.com/showthread.php?t=304766)): four faders, and the
need to see what they actually send. What came back from there:

- **14-bit CC pairs** — MSB/LSB, CC 0–31 paired with CC 32–63. Today the two halves are
  drawn as two independent 7-bit streams, so a 14-bit value change reads as two jumps.
  → [#6](../../issues/6)
- **the bottom of the window was covered by a bar**, reported by X-Raym: fixed in 0.5.2.

## Open issues

| issue | what it is |
|---|---|
| [#4](../../issues/4) | channel filter — the natural companion of per-channel tracking |
| [#5](../../issues/5) | history is fixed at 2000 events; size it from the time window |
| [#6](../../issues/6) | 14-bit CC pairs |

## Ideas, not issues yet

- **peak hold / min-max per pair** — the instant tells you little when you are measuring
  resolution; the extremes of the last second tell more.
- **export** — JSFX cannot write files. Publishing the metrics on `gmem` and shipping a
  small ReaScript that writes a CSV would turn the display into an instrument.
- **bar area** — a background or zebra rows, so the rows read as a table instead of
  floating text on black.
- **presets** — none today. Two starting points (*hardware test*, *gesture analysis*)
  would save the first five minutes.
- **vertical bars as an alternative layout** — discussed and not done: it decouples the bar
  height from the number of pairs (the plot would stop shrinking as CCs arrive) but needs
  two-line labels and a three-line metric block per column.
