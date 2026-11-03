# TODO — what is missing

Tracking follows the maturity of the work: **bugs** are issues labelled `bug`; **ideas and
design questions** are Discussions in **Ideas**, without an implementation commitment; **defined
work** is an issue labelled `enhancement`, with completion criteria.

## From the Cockos forum thread

The plugin began as a post in the REAPER forum on 2025-11-17
([thread 304766](https://forum.cockos.com/showthread.php?t=304766)). The 0.5.1 update was
announced there ([post #14](https://forum.cockos.com/showpost.php?p=2905329&postcount=14)); the
0.6–0.7 line was documented in the changelog instead, and the current announcement is
[post #21](https://forum.cockos.com/showpost.php?p=2972028&postcount=21).

- **The rate per CC per channel is the reason it exists.** X-Raym, debugging a DMX-lights JSFX,
  put it plainly: no MIDI logger shows a MIDI rate per CC per channel, so a rate limit in his own
  script was hard to verify from timestamped logs. `Messages/s` per pair is the feature to protect
  when the metrics are touched.

## Proposal for evaluation — device testing

[Device testing proposal](docs/device-testing.md) — **not implemented; no release commitment**.
Feedback and use cases: [Discussion #11](https://github.com/solyarisoftware/reaper/discussions/11).
The proposal holds the protocols, the limitations and the acceptance criteria.

## Feature requests — decided

- **A GUI library was evaluated and not adopted.** Tukan's `tk_gui_tools.jsfx-inc` has no
  dropdowns, which is what the enum parameters need; Geraint Luff's `ui-lib.jsfx-inc` has them but
  declares no license, so it cannot be vendored into this MIT repository. The bar is ~200 lines of
  our own code and needs neither.
- **An overlay panel for the parameters** — `−`/`+` steppers and a value in clear — is the next
  step if the bar starts to feel tight: a JSFX has no text input without a library, and the `CC`
  list can scroll. [Discussion #13](https://github.com/solyarisoftware/reaper/discussions/13)

## Bugs

Current bug reports: https://github.com/solyarisoftware/reaper/issues?q=is%3Aissue+is%3Aopen+label%3Abug

Closed: [#5](https://github.com/solyarisoftware/reaper/issues/5) temporal history
retention, fixed in 0.7.6 with per-pair 100 ms first/last/min/max buckets;
[#7](../../issues/7) rates read up to 10% high; [#3](../../issues/3) jitter over one
interval; [#2](../../issues/2) metrics saturating above 200 events/s; [#4](../../issues/4)
channel filter, done in 0.6.2; [#8](../../issues/8) all pairs visible, done in 0.6.4.

## Enhancement issues — defined work

| issue | what it is |
|---|---|
| [#19](../../issues/19) | vertical CC value bars: a third `ROWS` value (`strips`), so a bank of faders can be read by height. Stays an alternative to the beside rows, which hold more pairs |
| [#18](../../issues/18) | metric names, units and explanatory tooltips |
| [#17](../../issues/17) | recent input activity in the status line |

Completed in 0.7.5: [#23](https://github.com/solyarisoftware/reaper/issues/23),
rendering performance. Validation and measured limits stay in that issue.
History retention was addressed separately in 0.7.6 through #5.

An open issue is not a promise of implementation, priority or a delivery date.

## Feature requests — the roadmap

| discussion | what it is |
|---|---|
| [#10](https://github.com/solyarisoftware/reaper/discussions/10) — Ideas | 14-bit CC pairs (MSB/LSB, CC n with CC n+32). Currently two independent 7-bit streams, so a 14-bit change reads as two jumps |

## Ideas, not decided yet

- **peak hold / min-max per pair** — inside the Hold/Sweep proposal:
  https://github.com/solyarisoftware/reaper/discussions/11
- **export** — JSFX cannot write files; the metrics on `gmem` plus a small ReaScript is one
  approach: https://github.com/solyarisoftware/reaper/discussions/12
- **presets** — useful configurations are not defined yet:
  https://github.com/solyarisoftware/reaper/discussions/14
- **device assessment profiles and scoring** — no universal pass/fail limits are agreed:
  https://github.com/solyarisoftware/reaper/discussions/15
