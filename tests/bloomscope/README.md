# BloomScope tests

Run from the repository root; Python 3 standard library is sufficient. Lua 5.4
runs the actual companion action against a small host stub; without Lua those
cases skip explicitly. CI installs Lua and executes them.

```bash
python3 tests/bloomscope/lint_header.py
python3 -m unittest discover -s tests/bloomscope -v
python3 tests/bloomscope/test_bloomscope_math.py
```

The separate arithmetic script uses plain assertion functions and must run in
addition to unittest discovery. It covers hop partitioning, detector math, memory
capacity, history ownership, snapshots, smoothing, grid logic and source wiring.
Its isolated-note metric formulas are experimental arithmetic models, not claims
that automated per-note metrics are implemented in the plugin.

Unittest covers bounded note capture/pairing, loop splitting, actual Lua-action
lifecycle under a stub, source contracts for views/guides/help and public packaging.
One standalone first-note loop-wrap reproduction is an intentional expected failure:
valid companion context corrects that case, but standalone capture still does not.
Do not remove the expected failure by weakening the reproduction.

## Native probe

```bash
python3 tests/bloomscope/build_loop_host_probe.py <external-output-directory>
```

The builder copies actual MIDI/capture/loop EEL2 into a deterministic JSFX driver,
substituting host read-only variable names only. Load the result in REAPER on a
disposable track with master muted, outside any working companion session: it
reserves shared-memory slot 63. No native probe is installed through ReaPack.
Read the completion magic and assertion/failure counters described in
`bloomscope/docs/loop-companion.md`. Generation alone is not an executed test.

## Initial ALPHA host smoke — 2026-11-17

REAPER 7.86/x64 on Windows 11, WASAPI Shared at 48 kHz, isolated disposable
project with master muted. No real sampler or external input was required for
these synthetic tests; they do not establish cross-platform/instrument coverage.

- The published source set loaded, and the actual-source native acquisition/loop
  probe completed **113 assertions with zero failures**.
- Matching companion token/nonce handshake succeeded; after the final recompile,
  one sampled run showed **17 completed splits and zero queue overflows**.
- Stereo audio-only and Overlay/Split with a three-note chord were visually
  inspected. Freeze held the plugin's client/plot/status pixels unchanged while
  transport and passthrough continued. Clear discarded the frozen history; the
  audio-only layout recovered without a permanent empty MIDI strip.
- Before/after observers recorded **1699 matching MIDI messages and matching
  rolling hashes**, including a frozen interval. These are bus-0 tests.
- Nonzero stereo audio passed through; the maximum directly observed sample delta
  between observers was **3.0531133177191805e-16**. This is not a claim of live
  double-precision bit identity, nor a newly repeated rendered-null test.

The tests use synthetic signals, not evidence of every articulation or library's
behavior. Screenshots and disposable host fixtures are not shipped with the package.

## Host acceptance still needed

Source assertions, Python models and Lua stubs do not compile JSFX or prove host
callback ordering. A release smoke test must load the packaged source set, exercise
audio/MIDI and all three views, Freeze/Clear, and the matching companion handshake.
Full acceptance additionally needs rate reinitialization, SysEx/nonzero-bus routing,
long storage/seek stress, multiple instances/project tabs, CPU measurement and the
complete narrow/dense layout matrix. See the package's documented ALPHA limits and
repository Issues/Discussions for current follow-up work.
