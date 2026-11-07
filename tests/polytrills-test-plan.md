# PolyTrills — REAPER validation plan

What only REAPER can answer, for the current release. The offline checks next to this file
(`*_model.py`) cover the arithmetic; this list covers sound, timing feel and stuck notes, which no
model can.

Each case names the behaviour it guards. Run them in a project that is not the live one, with the
plugin **before** the instrument in the FX chain.

## What the offline models do *not* prove

- That the EEL2 compiles and the sections are laid out legally. r2 kept the
  function definitions in the `@init` region, as v1.0 had them and as every JSFX
  measured on this machine does (199 of 199 files that define functions at all);
  only REAPER can confirm the file compiles.
- That `midisend()` offsets behave as intended inside REAPER.
- That `@block` is called at all while the transport is stopped — the whole
  r4 stop flush depends on it (case 22).
- Anything about sound, timing feel, or the synth's release envelope.

## Setup (authorisation required — do not touch the orchestral template)

1. Work on a **separate test project**, e.g. `C:\DAW\COMPOSITIONS\PolyTrills-test.rpp`,
   never `OrchestraTemplateOne.rpp`.
2. Deploy the development copy to
   `<resource>\Effects\solyarisoftware-dev\PolyTrills.jsfx`, with the description
   changed to start with `DEV:` so it is distinguishable from the installed one.
   Compare bytes with `polytrills.jsfx` after copying.
3. Chain: MIDI source → `DEV: PolyTrills` → instrument (ReaSynth is enough) and, in a
   parallel branch, `midi/midi_logger` to record events.
4. Set the interface block size small (64 or 128) *and* then large (1024): the r1
   fixes are visible only at block boundaries.

## Cases

| # | Act | Expect |
| --- | --- | --- |
| 1 | Hold one note | Pass-through, no trill, single note-off after the fade window |
| 2 | Hold two notes, lift one | Trill switches to pass-through of the remaining note, no leftover trill note |
| 3 | Hold two notes, lift both | Trill runs through the fade window, then all voices stop: **no stuck note** in `midi_logger` |
| 4 | Hold three notes | Lowest = drone, upper two trill, drone stops with the others |
| 5 | Hold four notes | Two parallel trills, same rate, both stop together |
| 6 | Hold two notes, change Division mid-trill | Rate changes without a jump beyond one cycle; no dropped or doubled note |
| 7 | Hold two notes, change Balance mid-trill | Ratio changes; no phase inversion, no stuck note |
| 8 | Hold two notes, change project tempo | **Nothing moves**: the plugin no longer reads tempo. A rate that follows the metronome is exactly what made a 16th-note alternation sound like a string ripple. Record it as a pass when the trill keeps its Rate value. |
| 9 | Hold two notes, press Play/Stop repeatedly | On stop, no voice left on; on restart, the engines resynchronise |
| 10 | Hold notes, then bypass or remove the plugin | Notes stop (passthrough of the pending note-offs is not implemented — record what happens) |
| 11 | Same pitch from two different channels | Two separate held notes; a note-off on one channel leaves the other sounding. The trill itself is emitted on the base note's channel — record whether the synth does what you expect |
| 12 | Locate or loop wrap while a trill runs | **Nothing is flushed, by design.** Events here are block-local, so a jump cannot orphan one, and flushing on a jump would cut a good note on every loop pass. The trill keeps alternating; record whether the instrument keeps the sounding note across the jump (it may send all-notes-off itself — the trill then resumes at the next half period). |
| 13 | Redundant note-on on the same pitch and channel | No restart of the trill, no audible glitch, no velocity-ramp reset |
| 14 | Note-off on the wrong channel while a trill runs | Trill keeps running; no voice is stopped by mistake |
| 15 | Fifth note while four are held | Dropped; its later note-off changes nothing and does not stop the trill |
| 16 | Ramp Down 0 | Trill stops exactly at the note-off, no extra alternation, **no stuck note** — this is the ending on the beat. (It is the old `Linger 0`.) |
| 17 | Ramp Down 3, Depth 60 | After the last key lifts the trill keeps alternating and **slows down** for ~3 s, then stops. Depth 0 with the same time must give a flat tail instead — that is the old `Linger`, and the difference between the two is what to listen for. |
| 18 | Accent 0 / 50 / 100 | 0: base and upper equally loud. 100: base clearly stronger, upper still audible (velocity floor is 50) |
| 19 | Ramp 100 / 60 / 0 | 100: full velocity from the first note, mechanical. 60: first note softer, full by the 4th. 0: first note almost inaudible |
| 20 | Play the pair on channel 3 | Every generated note arrives on channel 3, because it keeps the channel of the note that created it. There is no channel control any more. |
| 21 | Play the pair on channel 1 and the drone on channel 3 | Each voice keeps its own channel: the drone on 3, the trill on 1. If they collapse onto one channel the sample library may retrigger instead of alternate — record what the instrument does. |

### Transport stop

| # | Act | Expect |
| --- | --- | --- |
| 22 | Hold two notes, press **Stop** while they are held | Silence at once: a note-off for whatever was sounding, at offset 0 of the first block after the stop, and no note-on after it. Keys still down. **Record first whether REAPER runs `@block` at all while stopped** — put `midi_logger` after the plugin and see whether it logs those note-offs. If it logs nothing, the edge is never observed and the fix cannot act; that is a finding, not a failure. |
| 23 | Hold two notes, press **Pause** | Expected: silence, like Stop — *if* REAPER reports `play_state` 2. A REAPER bug open since 2011 keeps it at 1 while paused; then nothing flushes and the trill keeps running. Record which of the two happens, with the REAPER version. |
| 24 | Hold two notes, Stop, then change the held set while stopped, then Play | Play must **not** retrigger: the trill running while stopped continues, and the restart only resumes the transport. No second note-on for a pitch already sounding in `midi_logger`. |
| 25 | Hold two notes, Stop, Play — twice, at block size 64 and 1024 | Same behaviour at both sizes: the restage note-on lands at offset 0 and the alternation that follows keeps ascending offsets. |
| 26 | Hold four notes and listen | The two trills must sound simultaneous and stay locked together. The stream is now ascending by construction (regression H), so an audible lag would mean a problem downstream, not in the plugin — record it either way. |
| 27 | Play the same pitch on two MIDI channels and hold both | **One sustained note, no trill, no machine gun.** With `Output Channel` 1 the two notes arrive on one channel; before r7 that was a note-off + note-on of the same pitch at every transition. Lifting one of the two keys re-attacks the pitch once, then sustains again. |
| 28 | Three notes where the two upper ones are the same pitch on two channels | Drone on the lowest, the doubled pitch sustained above it, no trill. Same with four notes where a pair repeats a pitch: the pair is sustained on the voice that is free. |
| 29 | Rate 8 vs 12 vs 16 on the same two held notes | 8 = the old `16th` at 120 BPM (the ripple, for comparison), 12 = the median of real performances, 16 = fast. If 16 "smears", it is the sampled instrument's retrigger limit: record which library and which rate it breaks at. |
| 30 | Humanize 0 vs 30 at Rate 12 | 0 is a metronome, 30 breathes. If 30 sounds *wrong* and not *human*, the jitter shape is the problem, not the amount — the corpus (see `corpus/README.md`) says the target is CV ≈ 0.20. |
| 31 | Balance 0 and 100 at Rate 12 | The two notes are ±15% apart in length: the trill leans, it does not become an arpeggio, and the speed does not change. |
| 32 | Rate 12, Humanize 0 then 70 | At 0 the alternation is a metronome — the reference for testing. At 70 it should sound like a player: some notes hesitate, the rate wanders slowly, and the first notes are softer and slower. |
| 33 | Listen for the articulation at Rate 12 | Each note should end *before* the next attack (about 25 ms of gap), not on top of it: a trill is separated notes, not a smear. This is the difference the corpus measured and the reason r10 exists. If it sounds clipped instead of articulated, the instrument's release is the suspect. |
| 35 | Ramp Up 2, Depth 60, two notes | The trill starts at about 1/3 of the Rate and settles over two seconds. With Depth 0 and the same time, nothing changes at all: the ramp is opt-in. |
| 36 | Ramp Up 2 + Ramp Down 3 together, Depth 60 | The gesture has both shapes at once: it leans in over two seconds and dissolves over three. Record whether the two windows feel like one gesture or like two effects glued together — that is the musical question this revision cannot answer offline. |
| 34 | Hold four notes, Rate 20 | Two parallel trills at the fastest setting, still locked together, still ascending in `midi_logger`. If the library smears, note the rate at which it does: that is the library's retrigger limit, not the plugin's. |

Report per case: pass/fail, block size, sample rate, tempo, and the `midi_logger`
line for the final note-off. `midi_logger` does not print sample offsets, so the
offset invariant itself stays covered by `timing_model.py` only.

## Defects

Both were found by `tests/transport_model.py`.

### 1. Four-note mode emitted in two runs — **fixed in r6**

`@block` called `advance_t1()` to exhaustion and only then `advance_t2()`, so a
block whose engines both toggled sent offsets like `10, 20, 10, 20`: ascending
inside each engine, not across the stream. r1 had made the offsets monotonic
*within* one engine; between the two the rule did not hold. It was the normal
case in four-note mode, not an edge — 4960 such blocks in 4000 randomized
sequences.

r6 introduced `advance_engines()`: with both engines running it walks one
timeline and emits engine 1 then engine 2 at the same offset, so a
non-decreasing stream is a property of the construction. `advance_t1()` is
untouched, so the 1–3 note modes keep the code they had. The model now asserts
zero descents in every mode (regression H pins the exact case), and
monkeypatching the old two-call order back into the model makes it fail — the
test has teeth.

### 2. Same pitch on two channels became a trill against itself — **fixed in r7**

Held notes have been identified by (pitch, channel) since r2, but the trill
pair is chosen by index after sorting by pitch then channel, and a pair owns
one channel: 55 on ch 1 plus 55 on ch 2 gave `base == upper`, i.e. a note-off
and a note-on of the same pitch on the same channel at every transition — a
retrigger at the trill rate, not an ornament.

r7 introduces `hold_note()` and guards the three pair sites: when the two
pitches of a pair are equal the pair is **sustained** on the first free
sustained voice (the pass-through voice, else the drone) instead of trilled,
with the first note's velocity, as the 1-note pass-through does. The model
asserts zero engine toggles onto the pitch already sounding (regression I pins
the two-channel case).

What r7 does **not** do is the real feature: emitting each half of the pair on
its own channel (per-note routing). It stops the plugin from doing something
wrong; it does not make a two-channel trill possible.

### 3. Not a defect, worth knowing

In the same full run the model counts ~12 000 `reconfigure` re-statements: a
block in which two keys land together silences a note and restarts it at the
same offset (`off 60`, `on 60`, `on 64`). It is inherent to "reconfigure = stop
everything and restage", it is legal MIDI, and whether it is audible is a
question for case 2 in the DAW. Fixing it would mean not restarting voices that
did not change — a different topic.

