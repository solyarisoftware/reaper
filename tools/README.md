# CCScope rendering checks

These are developer tools, not ReaScripts for installation or ReaPack packages.
They use Python 3 and its standard library. Generated JSFX files are temporary test
copies; never overwrite a working CCScope installation with a probe.

## Offline checks

From the repository root:

```bash
python3 tools/check_ccscope_memory.py
python3 -m unittest discover -s tests -v
```

The memory checker includes every production range, including the six GUI-owned
point-index ranges. Tests verify that deliberate overlap, an enlarged history
without relocated ranges, and narrower/wider pair keys are rejected. These checks do not
execute EEL2 or establish thread safety.

## Native graph-command regression

Export the baseline `ccscope.jsfx` to a temporary reference file, then build a probe
into its own temporary directory under REAPER's `Effects/`. The probe copies the
package files (read from the plugin's `@provides` block) and instruments the plot
panel it imports:

```text
python3 tools/ccscope_rendering_probe.py --reference <reference.jsfx> --source ccscope --output <resource>/Effects/CCScopeGraphTest
```

With the operator's permission, load `ccscope_rendering_probe.jsfx` in an empty,
disposable REAPER project and open its UI. Do not connect MIDI input or put a MIDI
generator before this probe: the fixture owns its history for the test.

The tool extracts the actual baseline and candidate graph functions and intercepts
only their line/circle calls. It checks command order, coordinates, radius/fill and
RGBA, with a 1e-7 numeric tolerance. The 630 cases cover empty/partial/full/wrapped
rings, persistent pairs without retained events, all dot modes, combined
CC/channel filters including an empty selection,
1/10/30 s windows and both layouts. No Python reimplementation of rendering is
used as the oracle.

The UI reports completion. Namespace `CCScopeRenderingTest23` also exposes:

| gmem index | Meaning |
|---|---|
| 20 | 0 running, 1 passed, -1 failed |
| 21 | Completed case count |
| 22 | Failing command index |
| 23 / 24 | Expected / actual command count |

To verify the test can fail, add `+ 1` to the generated candidate's
`x = mem[MEM_CC_SORTED + pair]` assignment. The test must fail. Regenerate the
unmodified probe afterward. Never apply this mutation to production sources.

## Native grid-pixel regression

Build to a **different** temporary effects directory:

```text
python3 tools/ccscope_rendering_probe.py --grid --source ccscope --output <resource>/Effects/CCScopeGridTest
```

Load the generated probe alone and open its UI. It compares cached output against
direct drawing pixel-for-pixel, and checks cache-hit/rebuild counts and restored
destination/blend mode. Eighteen cases include logical canvas changes, layout,
time window, font/scale invalidation, and 2048/2049 dimension transitions. It reads
all pixels in the visible comparison area, including a nonblack sentinel in the
control band that must survive the cache blit. Oversize logical canvases are
checked only where they intersect the actual framebuffer.

Status and completed case count use the same gmem indices 20/21. On failure,
22/23 identify pixel coordinates and 24 the RGB discrepancy; 25 counts compared
pixels. Logical size/scale changes are not a substitute for actual OS-window
resize, embedded-display and real HiDPI testing. For a red-capability check,
change only the generated probe's cache-blit `top` to zero: erasing the sentinel
must fail. Regenerate the normal probe afterward.

## Native status-line decisions (#17)

Build to a **third** temporary effects directory:

```text
python3 tools/ccscope_rendering_probe.py --status --source ccscope --output <resource>/Effects/CCScopeStatusTest
```

Load the generated probe alone and open its UI. The status line is a decision before
it is a drawing: which metric form fits, whether the version still fits beside it, and
which warnings the width can hold. The probe drives `calculate_layout()` and the real
`draw_status_info()` over 180 cases — nine widths from 180 to 1016 px, five flow states,
rows below and rows beside, five or sixty pairs — and compares each decision with the
same policy re-derived from `status_build()` and `status_measure()`. The warnings are
checked against the geometry that produces them, not forced: hidden rows come from
`g_visible_bars`, the beside warning from the real fallback. It also asserts that
content which fits never draws past the right margin, that a drawn version ends exactly
on it, and that the state word carries the intensity its state declares.

After the cases it measures the selection summary in its worst case — 2048 pairs, 500
events each in the window — and prints the elapsed milliseconds. That is the only work
this feature added to a frame, and it runs on the prune cadence rather than per frame.

Status and completed case count use gmem indices 20/21; on failure 22 is the case and
23/24, 25/26 are the expected/actual form and version flag. It reads globals
(`g_st_form`, `g_st_ver`, `g_st_w`, `g_st_ver_w`), and refuses to build when
`draw_status_info()` changes signature or those globals disappear — a probe that
silently measures the wrong thing is worse than no probe.

Red-capability check: change one width in the generated probe's `probe_width()` so a
case can no longer fit its richest form, and the run must fail. Regenerate afterwards.

## Native row and metric tooltip checks (#18)

Build in a **new temporary Effects subdirectory**, never over an installed plugin:

```text
python3 tools/ccscope_tooltip_probe.py --source ccscope --output <sandbox-resource>/Effects/CCScopeTooltip18
```

This command only builds text files; it does not start REAPER. After explicit operator
permission, load `tooltip_checks.jsfx` alone in a disposable REAPER project and open its UI.
No MIDI input/generator: this fixture owns the metrics buffers. It calls the actual layout,
row hover/content, dwell, metrics and generic tooltip functions, with native font measurements.
It checks all four tiers, field gaps/right edges and half-open row boundaries, zero/n/a,
pair/subject changes, identity and bar/value targets (including their gaps and stable anchors),
399/401 ms dwell and menu suppression, 3/4/19/20 intervals, the gap
filter, scratch-output caching, threshold endpoints/rounding, fixed geometry across content
variants (including Frozen), narrow/full/compact/suppressed panels, and restored font/colour/blend.

Results use `CCScopeTooltip18` gmem: `[0]` checks, `[1]` failures, `[2]` completed, `[3]` first
failed check. Require completed=1 and failures=0, not merely successful loading. For a
red-capability check, change the generated fixture's first expected Motion threshold word;
it must fail. Regenerate the unmodified fixture afterward.

The Linux tests exercise source arithmetic/boolean expressions and package/content invariants;
they do **not** execute EEL2, validate fonts or establish pixel correctness. The fixture must
still be run natively. Manual acceptance additionally checks real pointer dwell/exit in both
layouts, Freeze preserving row/help readings, real resize/OS scaling, opaque compositing over
moving traces, text containment and subsequent menu rendering. A native deterministic fixture
is not a substitute for those observations.

## Native UI, MIDI and audio-thread acceptance (Windows)

`ccscope_acceptance_probe.py` builds instrumented copies of an unmodified baseline
and the candidate, a synthetic MIDI generator, and input/output observers. Copy the
whole baseline package to a temporary directory first: the `--reference` argument is
the baseline `ccscope.jsfx`, and the includes listed in its `@provides` block are
taken from the same directory:

```text
python3 tools/ccscope_acceptance_probe.py --reference <baseline>/ccscope.jsfx --candidate ccscope/ccscope.jsfx --output <resource>/Effects/CCScopeAcceptance23
```

The output directory must not already exist. Copy `ccscope_acceptance_runner.lua`
to a temporary work directory as `run.lua`. Create `expected-resource.txt` and
`expected-project.txt` there, containing the native Windows resource path and the
full path of an **empty disposable project**. The runner refuses another project,
a nonempty project or additional open tabs. It needs an already-installed
js_ReaScriptAPI extension and does not install one.

Compile `ccscope_ui_input.cs` into that work directory as `ui_input.exe`, using
Windows PowerShell's `Add-Type -OutputType ConsoleApplication -OutputAssembly`.
The executable is a temporary test artifact, never a repository/package file.
Only with explicit operator permission, launch the existing REAPER executable
with `-newinst`, the named empty project and `run.lua` as explicit arguments.
**Leave the mouse unused during the UI phase.** The helper sends real input only
when the target belongs to REAPER and the cursor is inside the supplied FX window;
it activates only that window's top-level ancestor. Test-held buttons and the
saved pointer position are cleaned up on normal exit and manual script termination.
Project save/quit operations are not performed by the exit handler.

Before the interaction test the runner measures the bar twice, once per variant, and
writes `geometry-<variant>.txt`: the canvas, the centre of each cell, the labels tier, the
metrics tier, the layout mode, and for every selector the position, width, row count and
scroll of its open list. Two files that differ by one number mean something moved. A package
from before the panels were split is instrumented in place and gets a compatibility shim, so
the same telemetry asks the same questions of both sides and an A/B run across a refactor is
possible at all.

The runner captures `@gfx` elapsed time and audio-block elapsed time separately,
and compares every delivered input/output MIDI message and sample offset. Input
is observed **after host delivery**, not taken from the generator's pre-host order:
REAPER can canonicalize simultaneous bank/program/note events between FX.
Native clicks cover selectors, wheel/reset, filters, hover, Freeze/Clear and
actual window resizing, including 2048/2049 transitions. Embedded UI is checked
using the host's `gfx_ext_flags` bit 1 on the disposable track, not assumed from
a chunk value. Unverified embedding produces a limitation status, not a plain pass.

An optional `mode.txt` containing `ui` skips timing scenarios and writes separate
`-ui` outputs. Status starts at `RUNNING`, includes a run identifier, and changes
only when the run finishes. Keep logs and raw CSVs outside the repository.
This automation does not create a physical HiDPI display or prove hard-real-time
schedulability. Declare actual display coverage and elapsed-timing limitations.

## Temporal history native checks (#5)

The exact-event graph-command differential is intentionally **not** an oracle
for time-aggregated traces. It refuses the temporal renderer instead of silently
validating the legacy diagnostic function. Grid pixel checks remain separate.

```text
python3 tools/ccscope_history_probe.py --output <new-temporary-effects-dir>
```

Load `history_checks.jsfx` only in an authorized disposable REAPER project.
The probe copies current storage code and extracts the actual production renderer,
intercepting only `gfx_line`/`gfx_circle` to capture its output. It asserts the
drawing the plugin claims to do, not a golden image of what it happens to do:

- a step is a **hold plus a change** -- one horizontal at the previous value, one
  vertical at the new event -- and a diagonal is never drawn, for any `DOTS` state;
- the hold runs at the previous value (`history_fx1/fy1/fx2/fy2` capture the first
  line), and an unchanged value draws the hold with no vertical at all;
- a mark is a circle while successive marks stay `MARK_CIRCLE_MIN` px apart and a
  **tick** below that, and the count never drops: at 4001 events in the window the
  probe expects 4001 marks and `g_segment_stride == 2`;
- only the steps decimate, and at exactly `SEGMENT_BUDGET` commands nothing is
  skipped;
- the coda is dashed, sits at the held value and stops at the right edge; it
  appears only in the mode that asks for it;
- a filter that hides a pair does **not** truncate the window and does not draw it:
  the pair-to-slot map starts at `-1` (shared memory starts zeroed, so a zero
  would read as slot 0), and the renderer walks every event in the window and
  skips the invisible ones, instead of walking as many events as it counted as
  visible.

These are independent expected-geometry assertions: an A/B comparison alone would
pass if both versions shared the same rendering bug.
Results are in `CCScopeRing27` gmem: `[0]` checks, `[1]` failures, `[2]` completed. A green result
requires completed=1 and failures=0; loading an FX alone is not a compile oracle.
Native loops test deterministic storage logic, not real-time schedulability.

The general acceptance builder seeds positive clock times and populates the raw
event ring, when present. `instrument(..., seed_history=False)` is available
for real live-acquisition tests: it must not inject synthetic history into a
30-second retention measurement. Exact MIDI input/output and audio-block timing
remain independent checks. `DOTS` is the cell that decides what is drawn around
the events -- points only, points and the step of the held value, points and the
step with the dashed tail of the value still held.

## Timing the renderer

```text
python3 tools/ccscope_draw_timing.py --output <new-temporary-effects-dir>
```

Load `draw_timing.jsfx` in a disposable project and open its window: the probe
works in `@gfx`, because what it times is the drawing. It copies the storage code
and extracts the production renderer, then measures four fixtures -- 4000 and 9600
events over ten traces and over one -- each set up on one frame and timed over 32
with `time_precise()`. The best is kept, because a single frame can be disturbed by
the host. Results are in `CCScopeDrawTiming` gmem, three slots per case: best
microseconds, mean microseconds, marks drawn. `[12]` counts the cases stored, and
4 means the run is complete. Marks drawn must equal the fixture size: a probe that
decimated would be timing a smaller trace than the one it claims.

It measures the time spent inside `@gfx` emitting the commands, not the
rasterisation REAPER does afterwards. That is the same quantity the plugin's own
budget is built on, so the two are comparable; it is not the time to pixels.

## Performance is a separate check

Correctness probes do not measure speed, and the timing probe above does not
measure correctness: keep the two apart. Measure inter-callback intervals
separately with identical inputs/settings. Keep baseline and candidate copies
isolated; do not infer an FPS multiplier from a traversal count reduction. Native
probes require REAPER and do not run in the Linux CI job.

Measured once, 7.85, 1889x1087 window, WIN 30 s, one CC at 320 events/s from a
MIDI item, one copy at a time with the other windows closed (`time_precise()`
around the `@gfx` body, average over ~370 frames):

| build | marks drawn per frame | avg `@gfx` | worst |
|---|---:|---:|---:|
| 0.13.1, bucket aggregate | ~200 | 3.05 ms | 5.46 ms |
| 0.14.0, event ring (decimated 1 in 2) | ~2240 | 3.51 ms | 5.15 ms |

Two numbers to keep: the feature costs **+0.46 ms a frame** for ~11x the marks,
and the isolated probe below overstates a mark's cost — it scatters its points,
so each touches new pixels, while a trace repaints near the previous mark.
That probe reads ~1.4 us a point; on this trace the extra marks cost ~0.2 us
each. Budget on the probe, not on the trace.

Measured with `tools/ccscope_draw_timing.py` on 0.15.0 (renderer only, 1000x720,
best of 32 frames, no event dropped):

| fixture | best | mean |
|---|---:|---:|
| 4000 events, 10 traces | 1.18 ms | 1.64 ms |
| 9600 events, 10 traces | 1.82 ms | 2.60 ms |
| 9600 events, 1 trace | 1.80 ms | 2.43 ms |
| 4000 events, 1 trace | 1.45 ms | 1.80 ms |

The step trace draws two segments per event instead of one, and it is still not
the expensive part: at density the mark became a one-line tick instead of a
five-pixel circle, so what the trace gained in segments it gave back in marks.
9600 events -- 320 events/s over a 30 s window -- cost about 2 ms of a 33 ms
frame, and `SEGMENT_BUDGET` is never reached below 4000.

Tracking: https://github.com/solyarisoftware/reaper/issues/23
