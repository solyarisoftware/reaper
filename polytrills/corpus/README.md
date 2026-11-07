# PolyTrills gesture corpus

Notes played by humans, kept as **training data for the gesture model behind [PolyTrills](../)**
— and published so that the model can be re-derived, re-measured and improved instead of trusted.

A take is one sample of a population, not a repertoire: the `contributor` field identifies who
played it, and adding a take requires no code change. The measuring instrument is next to the
data, [`trill_corpus.py`](trill_corpus.py): it reads a take or a MIDI source and reports the
features the synthesis model needs.

## What is here

```text
corpus/
├── README.md              # this file: method, reference values, licences
├── manifest.csv           # one row per take: who, when, how, licence, file
├── takes/
│   └── c01-2026-11-07.csv # played by the author on a MIDI keyboard
└── trill_corpus.py        # the instrument: detector and feature extraction
```

A take is a plain CSV, one row per note, seconds:

```csv
t,pitch,dur,vel,chan
14.018750,71,0.597917,5,0
```

- `t` — onset, in seconds, on one monotonic timeline for the whole take
- `pitch` — MIDI note number
- `dur` — sounding duration, key-down to key-up, seconds (not to silence)
- `vel` — MIDI velocity as received
- `chan` — MIDI channel

A take is text and small: the first one is 33 KB for 1163 notes, i.e. 251 s of playing. It is the
author playing trills on purpose, semitone and tone, with pauses between them — not a performance,
and not meant to be one: it is a sample of one pair of hands, which is exactly what a corpus is
made of.

## How a take is made

Measured on REAPER 7.85, which is where the trap is: **MIDI from a keyboard reaches only
record-armed tracks**, so the source track must stay armed or nothing is recorded at all — while
its record mode must not create takes of its own. The procedure that works:

1. arm the track that holds the MIDI input, record mode *input*;
2. keep record monitoring **on** on that track, or the live MIDI never reaches its sends and the
   player hears nothing while recording;
3. record the raw MIDI with the plugin bypassed, in an otherwise silent project;
4. export `t, pitch, dur, vel` from the recorded take.

Do **not** set a track to `Record: output (MIDI)` over an existing MIDI item: measured on 7.85,
the pass splits the item and destroys its notes.

## What the detector counts as a trill

`trill_corpus.py` is deliberately conservative, so that "trill" means the same thing in every
source:

- at least **8 notes** of alternation between exactly **two pitches**;
- interval no wider than **4 semitones**;
- consecutive onsets between **25 ms and 300 ms** apart — faster than 40 notes/s is not a hand,
  slower than 3.3 is not an alternation;
- onsets closer than 12 ms are treated as one chord, and an onset is accepted when it contains the
  pitch the alternation expects: accompaniment chords do not break a trill.

For each episode it reports: **rate** (1 / median inter-onset interval), **irregularity** (the
coefficient of variation of those intervals), **onset** (first interval divided by the body),
**release gap** (a note's end minus the next attack; negative means a gap, positive means the
notes overlap), **balance** (upper/lower sounding duration), **accent** (upper minus lower
velocity), and the interval in semitones.

## Reference values

The plugin's defaults sit on these numbers, measured with the same detector on a **reference set
of recorded piano performances** that is not redistributed with this repository:

| feature | p10 | median | p90 |
|---|---|---|---|
| rate, notes/s | 8.2 | **12.2** | 14.5 |
| irregularity, CV of intervals | 0.09 | **0.20** | 0.40 |
| onset, first interval / body | 0.78 | **1.11** | 2.15 |
| release gap, ms | −43 | **−25** | −5 |
| balance, upper/lower duration | 0.74 | **1.00** | 1.37 |
| accent, upper − lower velocity | −7.7 | **0.0** | 8.0 |
| length, notes per episode | 8 | **11** | 22 |

Two caveats that were measured rather than assumed, and that matter before trusting any MIDI
source as a performance:

- **In 85 % of the reference episodes the sustain pedal is down**, so the key gap is not the
  audible gap — a released key with the pedal down does not stop the string. Restricted to the
  pedal-up episodes the gap is still −27 ms, which is why the conclusion holds. The plugin sends
  note-offs only, so it reflects the key behaviour and leaves the pedal to the instrument.
- **A MIDI file is not automatically a performance.** Freely available classical MIDI collections
  are step-sequenced or generated from the notation, so their trills are metronomic by
  construction. Only performance-captured sources belong in the reference column.

## Adding a take

1. export the CSV as described above, name it `<contributor>-<date>.csv`, put it in `takes/`;
2. add one row to [`manifest.csv`](manifest.csv) including the licence;
3. run `python3 trill_corpus.py --take takes/<file>.csv` and check the detector finds the episodes
   you expect.

Nothing in the plugin's configuration depends on who contributed: the model is calibrated on the
aggregate, and a new take only moves the aggregate.

## Licences

| What | Licence |
|---|---|
| the takes (e.g. `takes/c01-2026-11-07.csv`) | **CC0 1.0** — copy, modify, use commercially, no permission needed |
| `trill_corpus.py` | **MIT**, with the rest of this repository |

A take added in future must declare its licence in the manifest, and CC0 or CC BY are preferred so
that the corpus can travel.
