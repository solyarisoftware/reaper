# Loop companion protocol and acceptance boundaries

This document holds the shared-memory contract and technical acceptance boundaries;
open design and implementation work belongs in repository Issues and Discussions.

## Scope

The optional Main action supplies loop context to one BloomScope instance. Without
it, an intra-block wrapped note-on can be assigned to the previous capture segment.
The action does not supply a tempo map, implement Bars windows, repair history or
transport MIDI between paired analyzers. Normal audio/MIDI passthrough is independent
of companion state. See the package README for installation and operation.

## Shared-memory contract v1

Namespace: `BloomScope_Loop_v1`. There are 64 slots of 32 doubles. Hidden slider11
carries an integer token; token modulo 64 selects the slot. Zero means standalone.
The action allocates a stale/unused slot and random token, then binds the project,
track and FX GUID. JSFX supplies a per-initialization nonce that the action echoes.
Reordering FX is allowed; deletion, changed token/nonce or slot theft ends the action.
A recompile requires an explicit action restart, not an automatic reconnect.

| Offset | Writer | Meaning |
|---|---|---|
| 0 | Lua | Odd during publication; even when complete. |
| 1–3 | Lua | Token, nonce echo, correction enabled. |
| 4–7 | Lua | Loop start/end seconds, device sample rate, loop-start QN. |
| 8–10 | Lua | Configuration revision, heartbeat counter, host clock. |
| 16 | JSFX | Instance nonce, only when the token matches. |
| 17–19 | JSFX | Status, completed split count, queue overflow count. |

Each audio block reads context once and checks publication sequence, token, nonce,
rate, endpoints, heartbeat progress and clock age (less than one second). No retries
or per-sample shared-memory reads are used. Invalid context falls back to standalone.
Duplicate tokens fail closed on nonce disagreement. Project switches, bypass/offline,
non-unit project playrate and invalid device rate suspend correction.

## Joint sample-boundary split

For a continuous playing block crossing a valid loop end, round the boundary to
an integer sample offset. Queue captured note events at/after it in a bounded
4096-entry queue; send received MIDI onward immediately and unchanged regardless
of freeze, capture or capacity. At the boundary, close the segment, discard any
partial detector hop, start the new audio/MIDI segment at loop start and drain
queued notes with wrapped timestamps. Notes cannot own the display until the new
segment publishes a completed audio hop. Reconcile the following host anchor to
avoid a second discontinuity. A split exactly at block end occurs before the next block.

The queue uses 16,384 fixed doubles. Overflow is counted and flagged as capped
history, never an unbounded allocation or a reason to drop output MIDI. Clear resets
the diagnostic. Loops no longer than one audio block and multiple wraps within a
block are unsupported. A backward seek alone never establishes a loop split.

## Acceptance boundaries

The package uses unit project playrate and normal tracks' top-level FX. No
master/input/container action binding is supported. Live loop/rate edits are not
sample-accurate configuration transactions. Broad multi-instance/project-tab stress,
actual device-rate changes, long seeks and endpoint/configuration churn remain open
host-validation work. Offline models and Lua stubs do not establish host ordering,
real-time safety, memory publication guarantees or CPU performance.

The actual-source regression probe is generated from
`tests/bloomscope/build_loop_host_probe.py`; it is not part of the installed package.
Its tests reserve slot 63, so run it only in an explicitly isolated host setup,
never alongside a working companion session. Results use `gmem[10000..10004]`:
completion magic 9173, assertion count, failure count, last failed assertion and clock.

## API references

- https://www.reaper.fm/sdk/reascript/reascripthelp.html
- https://www.reaper.fm/sdk/js/vars.php
- https://www.reaper.fm/sdk/js/midi.php
