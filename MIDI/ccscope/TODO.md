# TODO — what is missing

Bugs and concrete requests are GitHub [issues](../../issues); this page is the map,
including the ideas that are not issues yet.

## From the Cockos forum thread

The plugin began as a post in the REAPER forum
([thread 304766](https://forum.cockos.com/showthread.php?t=304766)). The 0.6 release was
announced there with the full change list:
[post #21](https://forum.cockos.com/showpost.php?p=2972028&postcount=21).

- **The rate per CC per channel is the reason it exists.** X-Raym, using it to debug a
  DMX-lights JSFX, put it plainly: no MIDI logger shows a MIDI rate per CC per channel, so
  a rate limit in his own script was hard to verify from timestamped logs. That number —
  `Messages/s`, per pair — is the feature to protect when the metrics are touched.
- **14-bit CC pairs.** MSB/LSB, CC n paired with CC n+32, value 0–16383; REAPER supports
  them in the MIDI editor and in ReaControlMIDI. Here the two halves are still drawn as two
  independent 7-bit streams, so a 14-bit change reads as two jumps.
  → [#6](../../issues/6)
- **See every pair when the window grows**: both halves are done. 0.6.3 made the bar area
  grow with the window instead of being a fraction of it; 0.6.4 added the layout where the
  list sits **beside** the plot, for windows that are wide and short, where no amount of
  height helps. The two-line labels the issue expected turned out to be a bad trade —
  measured, two-line rows show *fewer* pairs than the layout they would replace, so the
  column keeps one line and the compact metrics.
- **The buffer could hold more** (200 events per pair was the cap): addressed in 0.6.0,
  500 events/s per pair with an exact one-second window.
- **The bottom row of text overlapped the CC rows**: fixed in 0.5.2.

## Open issues

| issue | what it is |
|---|---|
| [#5](../../issues/5) | history is fixed at 2000 events; size it from the time window |
| [#6](../../issues/6) | 14-bit CC pairs |
| [#8](../../issues/8) | all pairs visible: **done** — rows grow with the window (0.6.3) and the list can sit beside the plot (0.6.4); the issue can be closed |

Closed: [#4](../../issues/4) channel filter — done in 0.6.2, slider 6.

## Ideas, not issues yet

- **peak hold / min-max per pair** — the instant tells you little when you are measuring
  resolution; the extremes of the last second tell more.
- **export** — JSFX cannot write files. Publishing the metrics on `gmem` and shipping a
  small ReaScript that writes a CSV would turn the display into an instrument.
- **bar area** — a background or zebra rows, so the rows read as a table instead of
  floating text on black.
- **presets** — none today. Two starting points (*hardware test*, *gesture analysis*)
  would save the first five minutes.
