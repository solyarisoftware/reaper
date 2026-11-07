# Changelog

Notable changes only — what someone using the plugin would notice. One entry per release, one
line per change; the reasoning and the measurements behind each one live in `git log`, in the
corpus next to this package, or in the linked issue.

## 0.1.0 — 2026-11-07

- **First release.** One key passes through, two alternate, three give a drone plus a trill, four give two parallel trills.
- **Rate is in notes per second and does not follow the tempo.** A trill is a gesture; a metrical subdivision is what turned it into a string ripple.
- **The defaults are measured, not chosen.** Rate 12, unevenness ~20 %, and every note ending about 25 ms before the next attack — the medians of a reference set of recorded piano performances.
- **Humanize** makes the alternation breathe: per-note jitter with a heavy tail, a slow drift and a softer, slower onset. At 0 it is a metronome.
- **Ramp Up / Ramp Down / Ramp Depth** let the trill lean in and die away. The ramp-down extends the sound after the keys are released, because the end of a trill cannot be known in advance.
- **Five-note and larger chords** are ignored: four notes is the limit and the fifth is dropped.
- **Same pitch on two channels is sustained, not trilled**, instead of retriggering the same note at the trill rate.
- **Transport stop silences everything at once**; a restart with the keys still down brings the trill back.
- **The sustain pedal is not read.** The articulation sent is the finger's; the pedal stays the player's, and CC passes through untouched.
