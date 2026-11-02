# TODO — what is missing

Tracking follows the maturity of the work:

- **bugs** live in the GitHub [issues](../../issues), labelled `bug`: something that is
  wrong and has to stay visible until it is fixed;
- **ideas and feature proposals** are outlined below; open design questions belong in GitHub
  Discussions, category **Ideas**, without an implementation commitment;
- **defined implementation work** can become an issue labelled `enhancement`, linked back to
  its discussion.

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
  → [Discussion #10](https://github.com/solyarisoftware/reaper/discussions/10)
  (converted from issue #6; design proposal, not scheduled implementation).
- **See every pair when the window grows**: both halves are done. 0.6.3 made the bar area
  grow with the window instead of being a fraction of it; 0.6.4 added the layout where the
  list sits **beside** the plot, for windows that are wide and short, where no amount of
  height helps. The two-line labels the issue expected turned out to be a bad trade —
  measured, two-line rows show *fewer* pairs than the layout they would replace, so the
  column keeps one line and the compact metrics.
- **The buffer could hold more** (200 events per pair was the cap): addressed in 0.6.0,
  500 events/s per pair with an exact one-second window.
- **The bottom row of text overlapped the CC rows**: fixed in 0.5.2.

## Proposal for evaluation — device testing

[Device testing proposal](docs/device-testing.md) — **not implemented; no release commitment**.
Feedback and use cases: [Discussion #11](https://github.com/solyarisoftware/reaper/discussions/11),
category **Ideas**.
Keep the live Messages / Motion / Timing metrics, explain Timing as **Timing jitter**, and
consider a separate Start / Stop / Reset session:

- **Hold:** observed range, peak-to-peak and value standard deviation while the operator keeps
  the fader stationary; always show duration and message count, never equate silence with zero noise.
- **Sweep:** observed endpoints, distinct-code coverage, maximum step and direction reversals
  during a declared monotonic sweep; coverage is not effective resolution.
- **Later:** configurable Large steps counter and graph markers, not automatic fault detection.

Physical linearity, dead zone and hysteresis require an independent position reference and
remain outside scope. The README now clarifies the current metrics; review hover wording in a
separately verified patch, retaining `Timing` in compact rows. No algorithm changes are proposed
for that terminology update. See the proposal for protocols, limitations and acceptance criteria.

## Feature requests — decided, not written as issues

- **An overlay panel for the parameters.** The control bar (0.7.0) is deliberately one simple
  widget: click opens a list, the wheel steps, a right click resets. What it cannot do is take
  a value typed from the keyboard — a JSFX has no text input without a library — and with 128
  controllers the `CC` list is long enough to scroll. Both point at the same thing: a panel
  with `−`/`+` steppers and the value in clear, opened by a button (the "redbox" idea), to be
  done when the bar starts to feel tight. Feedback:
  https://github.com/solyarisoftware/reaper/discussions/13
- **A GUI library was evaluated and not adopted.** Tukan's `tk_gui_tools.jsfx-inc` is
  permissively licensed (*"free as in free beer… share your plugins for free too"*) but ships
  knobs, buttons and meters — no dropdowns, which is exactly what the three enum parameters
  need. Geraint Luff's `ui-lib.jsfx-inc` does have selectors and text input, but declares no
  license, so it cannot be vendored into this MIT repository without asking him first. The bar
  is ~200 lines of our own code and needs neither.

## Bugs

| issue | what it is |
|---|---|
| [#5](../../issues/5) | history is fixed at 2000 events; size it from the time window |

Closed: [#7](../../issues/7) rates read up to 10% high; [#3](../../issues/3) jitter over one
interval; [#2](../../issues/2) metrics saturating above 200 events/s; [#4](../../issues/4)
channel filter, done in 0.6.2; [#8](../../issues/8) all pairs visible, done in 0.6.4.

## Feature requests — the roadmap

| discussion | what it is |
|---|---|
| [#10](https://github.com/solyarisoftware/reaper/discussions/10) — Ideas | 14-bit CC pairs (MSB/LSB, CC n with CC n+32). Currently two independent 7-bit streams. Design and use cases are under discussion; no implementation commitment |

## Ideas, not decided yet

- **peak hold / min-max per pair** — discuss within the Hold/Sweep proposal:
  https://github.com/solyarisoftware/reaper/discussions/11
- **export** — JSFX cannot write files. Publishing the metrics on `gmem` and shipping a
  small ReaScript is one possible approach. Summaries versus time series, CSV versus JSON and
  acquisition mechanics are under discussion:
  https://github.com/solyarisoftware/reaper/discussions/12
- **presets** — none today. Two starting points (*hardware test*, *gesture analysis*)
  might save setup time; useful configurations still need definition:
  https://github.com/solyarisoftware/reaper/discussions/14
- **device assessment profiles and scoring** — test protocols, explicit thresholds and category
  results before considering an overall score; no universal pass/fail limits are agreed:
  https://github.com/solyarisoftware/reaper/discussions/15
