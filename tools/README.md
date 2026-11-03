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
python3 tools/ccscope_rendering_probe.py --reference <reference.jsfx> --source MIDI/ccscope --output <resource>/Effects/CCScopeGraphTest
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
python3 tools/ccscope_rendering_probe.py --grid --source MIDI/ccscope --output <resource>/Effects/CCScopeGridTest
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

## Native UI, MIDI and audio-thread acceptance (Windows)

`ccscope_acceptance_probe.py` builds instrumented copies of an unmodified baseline
and the candidate, a synthetic MIDI generator, and input/output observers. Copy the
whole baseline package to a temporary directory first: the `--reference` argument is
the baseline `ccscope.jsfx`, and the includes listed in its `@provides` block are
taken from the same directory:

```text
python3 tools/ccscope_acceptance_probe.py --reference <baseline>/ccscope.jsfx --candidate MIDI/ccscope/ccscope.jsfx --output <resource>/Effects/CCScopeAcceptance23
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
intercepting only `gfx_line`/`gfx_circle` to capture its output. It tests a 40,000
message/s synthetic history across 20 pairs for 32 s, all 2048 dense keys, sparse
pairs, spike endpoints/ordered extrema, same-tick Clear, duplicate markers,
partially visible boundary envelopes and expired bucket tags. Geometry regressions
also require two rising/falling events in one bucket to produce a single diagonal,
not horizontal/vertical/horizontal steps, in every `DOTS` mode. They check the
segment endpoints, constant-value segments, retained interior peaks/troughs, and
both clipped boundaries. These are independent expected-geometry assertions: an
A/B comparison alone would pass if both versions shared the same rendering bug.
Results are in `CCScopeHistory5` gmem: `[0]` checks, `[1]` failures, `[2]` completed. A green result
requires completed=1 and failures=0; loading an FX alone is not a compile oracle.
Native loops test deterministic storage logic, not real-time schedulability.

The general acceptance builder seeds positive clock times and populates both raw
and temporal history when present. `instrument(..., seed_history=False)` is available
for real live-acquisition tests: it must not inject synthetic history into a
30-second retention measurement. Exact MIDI input/output and audio-block timing
remain independent checks. `DOTS` refers to retained representatives under temporal
aggregation; extrema have bucket-level timing rather than original event offsets.

## Performance is a separate check

These probes test correctness, not speed. Measure `@gfx` execution duration and
inter-callback intervals separately with identical inputs/settings. Keep baseline
and candidate copies isolated; do not infer an FPS multiplier from a traversal
count reduction. Native probes require REAPER and do not run in the Linux CI job.

Tracking: https://github.com/solyarisoftware/reaper/issues/23
