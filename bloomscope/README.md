# BloomScope

*See how your instrument's sound unfolds in relation to MIDI notes.*

> [!WARNING]
> **ALPHA** — experimental audio-envelope analysis with optional MIDI context.
> Parameters, file layout and saved-project compatibility may change without a
> migration path. Try a disposable project first and read the limitations below.
> Maturity levels: [CONTRIBUTING.md](../CONTRIBUTING.md#maturity-levels).

Study how a sample-based instrument's sound develops through attack, sustain and
release. BloomScope plots Peak and RMS level history in dBFS, with optional MIDI
note bars and note-on/off guides on the same timeline.

## One output, not one curve per note

BloomScope measures the **combined audio signal** at its position in the FX chain:
a single note, a chord, overlapping notes or a sampled ensemble. Earlier release
tails can continue beneath later notes; a note-off is not necessarily the end of the sound.

The plot is **not a separate envelope for each note**. Detectors measure the resulting
audio, not a sum of independently extracted note envelopes. MIDI provides timing
context, not voice separation or individual-note amplitude measurements.

**MIDI is optional.** Other instruments, recorded audio, microphone signals, buses
and the master mix can also be inspected, while the transport is playing.

## Install

In REAPER: *Extensions → ReaPack → Import a repository*, paste this URL, then synchronize:

```text
https://github.com/solyarisoftware/reaper/raw/master/index.xml
```

Install **BloomScope** from category `bloomscope`. The package installs the JSFX and
its nine includes in `Effects/bloomscope/`, and registers the optional
`bloomscope_loop_companion.lua` action in the Main Action List. Installing does not
start the action. No MCP server, external Python runtime or startup hook is required.

For manual installation, copy `bloomscope.jsfx` and all nine `bloomscope_*.jsfx-inc`
files into `Effects/bloomscope/` inside your REAPER resource directory. If desired,
copy the Lua companion into `Scripts/bloomscope/` and load it with
*Actions → Show action list → New action → Load ReaScript…* in the Main section.

Use REAPER 7.86 or newer for this alpha. Windows 11 / REAPER 7.86 is the tested
setup; macOS/Linux execution has not been verified.

## Placement and MIDI delivery

Place BloomScope **after the instrument**. Any effects between the instrument and
BloomScope also affect the measured signal. The reading is taken at the analyzer's
FX-chain position, **before the track fader**, not necessarily at the final track output.

The MIDI strip shows only note events actually received by BloomScope. Some
instruments consume MIDI or replace their MIDI output with an empty stream. If
audio arrives but notes do not, check the instrument's MIDI-output setting; in
REAPER, disabling the instrument's MIDI output can allow its input events to pass
to downstream FX. This is instrument-dependent, not a universal requirement.
No notes means the strip disappears and the space returns to the audio plot.

## Controls and readings

| Control | Meaning |
|---|---|
| Window | Visible history in seconds, up to 30 s; changing it preserves capture. |
| Detect | Peak, RMS or both. Peak is the largest absolute sample per 32-sample hop; RMS is the square root of mean sample power. |
| Floor | Bottom of the dBFS scale; 0 dBFS is at the top. Values below the floor are clamped. |
| RMS | Draw-time smoothing: one hop, 30, 100 or 300 ms; Peak is not smoothed. |
| View | Linked Stereo, Stereo Overlay or Stereo Split, using the same stored data. |
| Grid | Full, Levels or Off; axis labels and MIDI guide settings remain independent. |
| Freeze | Hold captured audio/MIDI history; audio and MIDI keep passing. |
| Clear | Discard history, including a frozen window. |

Linked Stereo uses the louder channel for Peak and mean L/R power for RMS. It is
not a waveform sum or mono fold-down. Overlay draws L/R on one axis without fill;
Split draws aligned Left/Right panels. A Peak fill extends to the floor: it is not
a third measurement or a difference band. Equal envelopes do not prove phase identity.

Hidden parameters remain available under REAPER's **Param** menu, including reset
on play and MIDI guides. Right-click the plot/strip for **Off / Plot only / Linked
to MIDI** guides. Note-on heads point up in red; note-off heads point down in orange.
Hover a control or note bar for help. Pitch labels use MIDI 60 = C4, independently
of REAPER's octave-display preference. Velocity is received event data, not a dBFS prediction.

## Optional loop companion

Standalone capture has a known limitation: a note-on arriving at an intra-block
loop wrap can be assigned to the preceding iteration, leaving an unmatched note-off.
For corrected loop context:

1. Select exactly one normal track containing exactly one BloomScope instance.
2. Run the included `bloomscope_loop_companion.lua` Main action once.
3. Enable Repeat and set a loop range longer than one audio block.

`loop ready` means the context, range and rate are valid. With Repeat off, the
status is `loop unavailable` and ordinary capture continues. Re-running the same
action stops it. Restart it after recompiling the JSFX; recompilation clears history.

The standalone limitation is tracked at https://github.com/solyarisoftware/reaper/issues/34.

The action binds to one project, track and FX instance. It supports normal tracks'
top-level FX, not master/input/container FX. Project switches, bypass/offline,
invalid audio-device sample rate and non-unit playrate suspend correction. It never
changes audio-device settings. It does not repair previously captured history.
Technical contract: [docs/loop-companion.md](docs/loop-companion.md).

## Requirements and limits

- **Playback-only acquisition:** no capture while stopped, paused or recording,
  even when input is passing. This is not a stopped-transport live-input monitor.
- **Project playrate 1** is required for timing interpretation. Other rates have
  not been validated; the companion explicitly disables correction for them.
- Audio channels 1/2 are analyzed. MIDI note references are captured on bus 0;
  other MIDI is not visualized. MIDI routing remains instrument-dependent.
- No per-note envelope separation, automated attack/release or latency measurement,
  negative-delay recommendation, CC lanes or Bars window. This is not a waveform,
  LUFS or true-peak meter, nor an envelope generator.
- Storage is bounded: 4096 note records, 256 segments, a 4096-event loop queue and
  a 2048-column plot. Capped histories are flagged. At 192 kHz the audio storage
  fits the default memory budget; higher rates may disable capture explicitly.
- Capture is transient: Clear, reset-on-play, rate changes or recompilation can
  discard history. It is not a saved measurement archive.
- Standalone loop wrapping retains the defect above. Broad multi-instance stress,
  live loop/rate edits, sample-rate reinitialization, SysEx/nonzero-bus host checks,
  CPU targets and the complete dense/small-window layout matrix remain unverified.
  Passing offline models is not evidence of those host behaviors.

## Feedback and development

- Bugs: https://github.com/solyarisoftware/reaper/issues
- Ideas and design questions: https://github.com/solyarisoftware/reaper/discussions/categories/ideas

Start titles with **BloomScope -** and include version, REAPER/OS, routing and
reproduction steps. Issues and Discussions are the roadmap, not promises of delivery.
See [CHANGELOG.md](CHANGELOG.md) for releases, and
[../tests/bloomscope/README.md](../tests/bloomscope/README.md) for test scope.

Follow-up topics:
- Host-validation matrix: https://github.com/solyarisoftware/reaper/issues/35
- Response landmarks and negative-delay guidance: https://github.com/solyarisoftware/reaper/discussions/31
- Tempo-map-aware Bars windows: https://github.com/solyarisoftware/reaper/discussions/32
- Velocity/CC dynamics context: https://github.com/solyarisoftware/reaper/discussions/33

MIT licensed; see [../LICENSE](../LICENSE).
