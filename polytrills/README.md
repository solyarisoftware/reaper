# PolyTrills

Turns the notes you hold into trills. Hold two keys and they alternate; hold one and it passes
through untouched; hold three and the lowest becomes a drone; hold four and you get two parallel
trills. Written for REAPER's JSFX engine, so it runs anywhere REAPER runs and costs nothing.

The point is not to repeat notes quickly. A trill is a gesture, and a metronome playing 16ths is
not one — it is a string ripple. PolyTrills is calibrated on measurements taken from real piano
performances, and the defaults are those measurements, not a taste.

## Install

In REAPER: *Extensions → ReaPack → Import a repository*, paste this URL, then synchronize:

```
https://github.com/solyarisoftware/reaper/raw/master/index.xml
```

The package installs as `Effects/polytrills/polytrills.jsfx` and appears as **PolyTrills** in the
FX browser. Manual install: copy `polytrills.jsfx` into the same folder inside your REAPER
resource directory.

Put it **before** the instrument in the track's FX chain: it generates MIDI, it does not make
sound.

## The six controls

| Control | What it does | Default |
|---|---|---|
| **Rate (notes/s)** | Alternation speed in notes per second. Not tied to the tempo: change the BPM and the trill does not move. | `12` |
| **Humanize (%)** | Makes it human: each note gets its own length, the rate wanders slowly, the first notes start softer and slower. At 0 it is a metronome. | `70` |
| **Balance** | Gives one of the two notes a little more time than the other. Even by default; the range is ±15 %, not an arpeggio. | `50` |
| **Ramp Up (s)** | How long the trill takes to reach its final rate: it starts sparse and settles. | `0` (off) |
| **Ramp Down (s)** | How long the trill takes to die away after you lift the keys. It keeps alternating and slows down across the window, then stops. | `0.1` |
| **Ramp Depth (%)** | How sparse the two ends of the ramp are. | `60` |

`Ramp Up` and `Ramp Down` are the one expressive part of the plugin, not a measured one: see
[What the defaults mean](#what-the-defaults-mean) below.

## How the notes come out

- **Each note ends before the next one starts.** About 25 ms of gap at the default rate. A trill
  is separated notes, not a smear: this is the single most audible difference from a MIDI
  arpeggiator.
- **The two notes of a pair share one MIDI channel**, the channel of the base note. A pair held on
  two channels therefore plays on one of them, and two identical pitches on two channels cannot
  trill — they are sustained instead, because repeating a note-off and a note-on of the same pitch
  at 12 notes a second is a machine gun, not an ornament.
- **Each voice keeps the channel it was played on**: the drone on channel 3 stays on 3 while the
  trill stays on 1.
- **Everything that is not a note passes through untouched** — CC, pitch bend, aftertouch,
  program change, and the sustain pedal, which the plugin deliberately does not read. The
  articulation it sends is the finger's; the pedal is the player's.
- **Transport stop is handled.** If the transport stops while notes are held, every voice is
  silenced at once instead of hanging until the next block; when it starts again with the keys
  still down, the trill restarts from the held set.
- **A locate is deliberately ignored**: events are block-local, so a jump of the playhead cannot
  orphan one, and flushing on a jump would cut a good note on every loop pass.

## What the defaults mean

The same detector was applied to a reference set of recorded piano performances and to trills
played on a keyboard for this project. The numbers below are the medians of the reference set,
which is not redistributed with this repository:

| Feature | Reference | Where it lands in the plugin |
|---|---|---|
| rate | **12.2 notes/s** | `Rate` default 12 |
| unevenness, CV of the intervals | **0.20** | `Humanize` 70 → 0.21 |
| onset, first interval vs the body | **1.11×** | part of `Humanize` |
| release of a note vs the next attack | **−25 ms** (a gap) | every note sounds 72 % of its period — fixed |
| balance, upper vs lower duration | **1.00** | `Balance` 50 |
| accent, upper vs lower velocity | **0.0** | no accent |

The corpus, the method, the measuring tool and the reference values are in
[`corpus/`](corpus/): the dataset is published as training data, so that the model can be
re-derived and improved instead of trusted.

`Ramp Up` and `Ramp Down` are the exception. A real trill starts only 11 % slower than its body,
so a trill that begins at a third of its rate is an effect you ask for, not fidelity. Both default
to near-off, and `Ramp Down 0.1` with `Ramp Depth 0` reproduces a plain constant-rate tail.

## Requirements and limits

Written and tested against REAPER 7.85 with a sampled piano (Spitfire Audio Intimate Grand
Piano). No JSFX compiler exists outside the DAW, so the offline test suite in the private
development repository is what stands behind the arithmetic; the sound is judged by ear.

- A sampled instrument may not retrigger as fast as the plugin asks. If a trill smears above a
  certain rate, that is the library's limit — lower `Rate` and see where it recovers.
- `Rate` above 16 notes/s is faster than most of the reference performances.
- Latency of your audio device adds to the perceived timing, as with any MIDI generator.

## Licence and feedback

MIT, like the rest of this repository. Bugs and defined changes: an issue with the steps that
reproduce it. Ideas and design questions: a discussion in *Ideas*. Both are the roadmap; there is
no separate roadmap file.
