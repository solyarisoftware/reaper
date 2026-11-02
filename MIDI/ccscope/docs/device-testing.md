# Device testing with CCScope

**Status: Proposal — not implemented.** Updated: 2026-11-02.
No release date or implementation commitment. This document separates current capabilities
from possible extensions to evaluate in the roadmap.

## Purpose and limits

CCScope observes MIDI output, not the physical position of a fader. It can help test a device
and inform calibration performed elsewhere; it cannot establish physical accuracy from MIDI
alone. Preserve its core capability: message rate per (CC, channel).

The graph already helps users spot oscillating values and sudden jumps visually. The existing
Timing metric measures irregular message spacing, not value noise. Motion does not distinguish
an intended gesture from noise or a discontinuity. Neither metric diagnoses hardware faults.

## Current live metrics

Keep Messages, Motion and Timing in the compact display. Explain Timing as **Timing jitter**
in documentation and, in a future verified patch, in the hover panel. Do not change the
algorithms merely to change the terminology.

- **Messages:** count of received messages in the rolling one-second window, including
  repeated identical values. It is not a count of distinct values or physical movements.
- **Motion:** sum of absolute CC value changes associated with messages in that window,
  expressed in CC units/s. It measures MIDI value travel, not physical speed or accuracy.
- **Timing jitter:** standard deviation of accepted inter-message intervals, in milliseconds.
  The current implementation excludes intervals longer than four times the shortest interval
  in the window and requires at least four usable intervals. This is a gap heuristic, not a
  guarantee that every excluded interval was a pause. It does not measure value fluctuations.

The one-second measurement window is independent of the graph's 1–30 s time window. Buffer
capacity limits and the source's transmission policy must accompany any interpretation.

## Proposed Device test mode

Add an explicit Start / Stop / Reset session, separate from the live one-second metrics.
Select one (CC, channel) pair and record duration, message count and test settings. A session
must not silently combine different pairs, filters or resolutions. Freeze, Clear and changing
selection need defined session semantics before implementation.

### Hold test — keep the fader stationary

Report:

- observed minimum and maximum;
- peak-to-peak range, in CC units;
- value standard deviation around the session mean;
- elapsed time and received message count.

Peak-to-peak is the first, accessible result: “63–65 while stationary”. Standard deviation is
the RMS deviation from the mean, not the raw RMS value. Samples are received messages, not
uniform samples of physical position: a device that sends only on change biases this view.
No messages means **no observations**, not proof of zero noise. One sample cannot establish
stability; show insufficient data rather than a reassuring score. Even repeated identical
values establish only stability of the reported MIDI output.

Do not automatically infer that the fader is stationary: the operator declares the test.

### Sweep test — move slowly across the full travel

Report:

- observed minimum and maximum;
- distinct values observed, for example 119/128 for a 7-bit CC;
- maximum absolute step between consecutive messages;
- value-direction reversals during an operator-declared monotonic sweep.

Use a session, not a per-second distinct-value count. Distinct codes observed are **coverage**,
not effective resolution or effective number of bits. A faster sweep or a lower message rate
can skip codes without indicating a faulty sensor. Mean absolute step can be considered as
secondary information, but depends on gesture speed and message rate as well.

Specify sweep direction and reset between passes; reversals are observations, not automatic
fault diagnoses. A meaningful comparison repeats the same protocol and reports the rate.
Currently CCScope handles independent 7-bit streams; 14-bit interpretation depends on the
separate paired-CC feature, not on merely changing a denominator to 16384.

## Later: Large steps

Consider a configurable threshold N and a count of transitions with abs(delta CC) > N,
alongside the maximum observed step and optional graph markers. Call them **Large steps**,
not faults: a deliberate fast movement, sparse transmission or missing messages can produce
large steps too. Preserve raw observations and state threshold, duration and sample count.

This follows Hold/Sweep rather than replacing a test protocol with an ambiguous counter.

## Outside scope without an independent physical reference

- **Linearity:** needs known physical position versus reported CC. R-squared alone is not an
  accuracy measure; a high value can coexist with systematic error.
- **Dead zone:** a MIDI plateau does not prove that physical movement went unreported.
- **Hysteresis:** needs matched physical positions approached from opposite directions.

A later external measurement protocol could make these testable; MIDI alone cannot.

## Evaluation and acceptance before implementation

1. First clarify the existing metrics in the README, then review the on-screen wording in a
   separately verified patch; keep the compact Timing label to preserve column geometry.
2. Evaluate Hold/Sweep using repeated-value, no-message, constant-ramp, oscillating and
   isolated-step streams with known expected results. Verify minimum-sample handling.
3. Compare slow and fast sweeps and different message rates: reports must not label reduced
   code coverage or large steps as hardware defects.
4. Verify pass-through, session controls, bounded memory and processing cost in REAPER;
   preserve the existing live monitor and its per-pair message-rate measurements.
5. Decide how to save or export results separately; a readable on-screen summary is enough
   for the first evaluation. Do not add more columns to every live row by default.

## Related work

- ../README.md — current capabilities and metric interpretation
- ../TODO.md — active bugs and roadmap
- https://github.com/solyarisoftware/reaper/issues/5 — history capacity
- https://github.com/solyarisoftware/reaper/issues/6 — 14-bit CC pairs
