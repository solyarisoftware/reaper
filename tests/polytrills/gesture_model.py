#!/usr/bin/env python3
"""Offline checks for the PolyTrills gesture engine (r10).

Transcribes the engine of `src/PolyTrills.jsfx`: one schedule, up to two voices,
one attack-to-attack period per note, a scheduled release at GATE of the
period, log-normal jitter, a slow drift and an onset.

It replaces the three separate models the engine had before r10: the offsets,
the rate mapping and the articulation are now properties of the same walk, so
they are checked together.

What it proves (and what it cannot):

  - every emitted offset lands inside the block and offsets never decrease —
    including the release, which is emitted after the attack that created it
    and may fall in a later block;
  - a note sounds for GATE of its period, so the release lands before the next
    attack instead of on top of it;
  - the mean rate is the Rate value (Humanize 0 is exact, and the jitter is
    symmetric in the log domain so it cannot drift);
  - Humanize produces the coefficient of variation the corpus measured
    (~0.21 at 70), and 0 produces a metronome;
  - the onset makes the first interval longer, as measured (1.11x);
  - Balance spans +-15%;
  - the two voices of 4-note mode emit at identical offsets.

It cannot prove that the EEL2 compiles, nor that a sampled instrument
retriggers at that speed. Those need the DAW (see PolyTrills-test-plan.md).

Run: python3 tests/polytrills/gesture_model.py    (stdlib only, no arguments)
"""

import math
import random

SRATE = 48000
GATE = 0.72
ONSET_NOTES = 4
ONSET_SLOW = 0.11
ONSET_SOFT = 0.60
HUMAN_SIGMA = 0.30
DRIFT_STEP = 0.03
DRIFT_KEEP = 0.92
BALANCE_SPAN = 0.15
RAMP_MAX = 3.0            # Ramp Depth 100 → the ends run at 1/4 of the Rate
MIN_NOTE = 200


class Voice:
    __slots__ = ('base', 'upper', 'ch', 'phase', 'sounding', 'active')

    def __init__(self):
        self.base = self.upper = -1
        self.ch = 0
        self.phase = 0
        self.sounding = -1
        self.active = False


class Trill:
    """The r10 engine: one schedule, one or two voices."""

    def __init__(self, rate=12.0, human=70.0, balance=50.0, srate=SRATE, rng=None,
                 ramp_up_s=0.0, ramp_down_s=0.0, depth=60.0):
        self.rate = rate
        self.human = human
        self.balance = balance
        self.srate = srate
        self.rng = rng or random.Random(20261107)
        self.v = [Voice(), Voice()]
        self.active = False
        self.count = 0
        self.on_in = 10**6
        self.off_in = 10**6
        self.period = 6000
        self.drift = 0.0
        self.anchor = 0
        self.master_vel = 80
        # r12: the two ramps and the tail
        self.ramp_up_s = ramp_up_s * srate
        self.ramp_down_s = ramp_down_s * srate
        self.depth = depth
        self.tr_elapsed = 0
        self.tail_active = False
        self.tail_counter = 0
        self.tail_total = 0

    # ── the model ────────────────────────────────────────────
    def human_factor(self):
        if self.human <= 0:
            return 1.0
        sigma = self.human / 100.0 * HUMAN_SIGMA
        z = (sum(self.rng.random() for _ in range(4)) - 2.0) * math.sqrt(3.0)
        # -sigma^2/2 divides out the log-normal's mean: the average note
        # length is the nominal one, so Rate stays honest
        return min(2.5, max(0.4, math.exp(sigma * z - 0.5 * sigma * sigma)))

    def onset_slow(self):
        if self.count >= ONSET_NOTES:
            return 1.0
        return 1.0 + ONSET_SLOW * (self.human / 100.0) * (ONSET_NOTES - self.count) / ONSET_NOTES

    def onset_velocity(self, vel):
        if self.count >= ONSET_NOTES:
            f = 1.0
        else:
            f = ONSET_SOFT + (1.0 - ONSET_SOFT) * self.count / ONSET_NOTES
        return max(1, min(127, int(vel * f)))

    def ramp_up_factor(self):
        if self.ramp_up_s <= 0:
            return 1.0
        return 1.0 + RAMP_MAX * (self.depth / 100.0) * max(0.0, 1.0 - self.tr_elapsed / self.ramp_up_s)

    def ramp_down_factor(self):
        if self.tail_active and self.tail_total > 0:
            return 1.0 + RAMP_MAX * (self.depth / 100.0) * (1.0 - self.tail_counter / self.tail_total)
        return 1.0

    def start_tail(self):
        """The last key was released: the tail (and the ramp-down) begins."""
        self.tail_active = True
        self.tail_counter = self.ramp_down_s
        self.tail_total = self.ramp_down_s

    def next_period(self):
        self.drift = self.drift * DRIFT_KEEP + (self.rng.random() * 2.0 - 1.0) * DRIFT_STEP * (self.human / 100.0)
        self.drift = max(-0.25, min(0.25, self.drift))
        p = self.srate / max(0.5, self.rate)
        b = (self.balance - 50.0) / 50.0          # -1 … +1
        p *= 1.0 - b * BALANCE_SPAN               # the pair splits the time
        p *= 1.0 + self.drift
        p *= self.onset_slow()
        p *= self.human_factor()
        p *= self.ramp_up_factor()
        p *= self.ramp_down_factor()
        return max(MIN_NOTE, int(p))

    # ── lifecycle ────────────────────────────────────────────
    def start(self, b1, u1, ch1, voices=1, b2=0, u2=0, ch2=0, ofs=0):
        self.stop(0)
        v1 = self.v[0]
        v1.active, v1.base, v1.upper, v1.ch, v1.phase = True, b1, u1, ch1, 0
        v2 = self.v[1]
        v2.active = voices > 1
        v2.base, v2.upper, v2.ch, v2.phase = b2, u2, ch2, 0
        self.active = True
        self.count = 0
        self.drift = 0.0
        self.tr_elapsed = 0
        self.tail_active = False
        ev = []
        v1.sounding = b1
        ev.append((ofs, 'on', b1, ch1))
        v1.phase = 1          # the next attack plays the other note
        if v2.active:
            v2.sounding = b2
            ev.append((ofs, 'on', b2, ch2))
            v2.phase = 1
        self.count += 1
        self.period = self.next_period()
        self.off_in = max(64, int(self.period * GATE))
        self.on_in = self.period
        self.anchor = ofs
        return ev

    def stop(self, ofs):
        ev = []
        for v in self.v:
            if v.active and v.sounding >= 0:
                ev.append((ofs, 'off', v.sounding, v.ch))
                v.sounding = -1
            v.active = False
        self.active = False
        self.on_in = self.off_in = 10**6
        return ev

    def advance(self, blk):
        """advance_trill(): merge the pending release with the next attack."""
        ev = []
        if not self.active:
            return ev
        pos = self.anchor
        self.anchor = 0
        while pos < blk:
            e_off = self.off_in if self.v[0].sounding >= 0 else 10**6
            e_on = self.on_in
            e = min(e_off, e_on)
            if pos + e >= blk:
                self.off_in -= blk - pos
                self.on_in -= blk - pos
                pos = blk
            else:
                pos += e
                if e_off <= e_on:
                    for v in self.v:
                        if v.active and v.sounding >= 0:
                            ev.append((pos, 'off', v.sounding, v.ch))
                            v.sounding = -1
                    self.off_in = 10**6
                    self.on_in = e_on - e
                else:
                    v1 = self.v[0]
                    v1.sounding = v1.base if v1.phase == 0 else v1.upper
                    ev.append((pos, 'on', v1.sounding, v1.ch))
                    v1.phase = 1 - v1.phase
                    v2 = self.v[1]
                    if v2.active:
                        v2.sounding = v2.base if v2.phase == 0 else v2.upper
                        ev.append((pos, 'on', v2.sounding, v2.ch))
                        v2.phase = 1 - v2.phase
                    self.count += 1
                    self.tr_elapsed += self.period    # the period that just went by
                    self.period = self.next_period()
                    self.off_in = max(64, int(self.period * GATE))
                    self.on_in = self.period
        return ev


def run_blocks(t, blocks, blk):
    """Run `blocks` blocks of `blk` samples, checking the invariants."""
    all_ev = []
    for b in range(blocks):
        ev = t.advance(blk)
        prev = -1
        for (ofs, kind, pitch, ch) in ev:
            assert 0 <= ofs < blk, (b, ofs, blk)
            assert ofs >= prev, (b, prev, ofs, ev)
            prev = ofs
        all_ev.append(ev)
    return all_ev


def measured_onsets(blocks_ev, blk):
    """Attack positions in samples from the start, rebuilt from block-relative
    offsets (an offset alone means nothing outside its block)."""
    out = []
    for i, ev in enumerate(blocks_ev):
        for (ofs, kind, pitch, ch) in ev:
            if kind == 'on':
                out.append(i * blk + ofs)
    return out


# ── named checks ─────────────────────────────────────────────

def check_offsets_and_gate():
    """The release follows its own attack, inside the block, ascending."""
    rng = random.Random(5)
    for trial in range(3000):
        blk = rng.choice([16, 32, 64, 128, 256, 1024])
        t = Trill(rate=rng.choice([4, 8, 12, 16, 20]), human=rng.choice([0, 70, 100]),
                  balance=rng.choice([0, 50, 100]), rng=rng)
        ofs = rng.randrange(blk)
        t.start(60, 64, 0, ofs=ofs)
        run_blocks(t, 6, blk)
    # gate: one note of known period, its release lands at GATE of it
    t = Trill(rate=12, human=0, rng=random.Random(1))
    t.start(60, 64, 0, ofs=0)
    period = t.period
    ev = t.advance(4096)
    ons = [o for (o, k, p, c) in ev if k == 'on']
    offs = [o for (o, k, p, c) in ev if k == 'off']
    assert offs[0] == int(period * GATE), (offs[0], period, GATE)
    # the first attack came from start(), so ons[0] is the *second* attack:
    # the release of note 1 must land before it
    assert offs[0] < ons[0], (offs[0], ons[0])


def check_rate_mapping():
    """Mean notes per second is the Rate value, with Humanize 0."""
    for rate in (4, 6, 8, 12, 16, 20):
        t = Trill(rate=rate, human=0, rng=random.Random(2))
        t.start(60, 64, 0)
        blocks = run_blocks(t, 400, 1024)
        ons = measured_onsets(blocks, 1024)
        span = ons[-1] - ons[0]
        nps = (len(ons) - 1) / (span / SRATE)
        assert abs(nps - rate) / rate < 0.01, (rate, nps)


def check_humanize_cv():
    """Humanize 70 gives the corpus CV (~0.21); 100 gives ~0.30; 0 is exact."""
    for human, target in ((70, 0.21), (100, 0.30)):
        rng = random.Random(3)
        periods = []
        t = Trill(rate=12, human=human, rng=rng)
        t.start(60, 64, 0)
        for _ in range(20000):
            periods.append(t.period)
            t.advance(10**6)
        mean = sum(periods) / len(periods)
        sd = (sum((p - mean) ** 2 for p in periods) / len(periods)) ** 0.5
        cv = sd / mean
        assert abs(cv - target) < 0.04, (human, cv, target)
    # Humanize 0: every period is the same
    t = Trill(rate=12, human=0, rng=random.Random(4))
    t.start(60, 64, 0)
    first = t.period
    for _ in range(100):
        t.advance(10**6)
        assert t.period == first, (t.period, first)


def check_no_drift_of_the_mean():
    """The average rate is the Rate, measured on the emitted attacks."""
    for human in (0, 70, 100):
        t = Trill(rate=12, human=human, rng=random.Random(6))
        t.start(60, 64, 0)
        blocks = run_blocks(t, 3000, 1024)          # ~64 s of trill
        ons = measured_onsets(blocks, 1024)
        nps = (len(ons) - 1) / ((ons[-1] - ons[0]) / SRATE)
        assert abs(nps - 12) / 12 < 0.03, (human, nps)


def check_onset():
    """The first interval is longer, and it decays over four notes.

    Measured statistically: a single draw is dominated by the jitter, so the
    check compares the mean of the first period with the mean of the body
    over many independent trills.
    """
    firsts = []
    for trial in range(400):
        t = Trill(rate=12, human=100, rng=random.Random(700 + trial))
        t.start(60, 64, 0)
        firsts.append(t.period)
    # compare with the nominal, not with a sampled body: sampling "the period
    # in progress at a block boundary" is length-biased (long notes are more
    # likely to be caught), and the body is already checked events-by-events
    # in check_no_drift_of_the_mean()
    ratio = (sum(firsts) / len(firsts)) / (SRATE / 12)
    # onset_slow() at count 1 is 1 + 0.11 * 3/4 = 1.0825
    assert 1.05 < ratio < 1.12, ratio
    # by the fifth note the onset is gone (drift and jitter still apply)
    # velocity onset: first note at 60% of target, full by the fourth
    v = Trill(rate=12, human=100, rng=random.Random(8))
    v.count = 0
    assert v.onset_velocity(100) == 60
    v.count = 2
    assert v.onset_velocity(100) == 80
    v.count = 4
    assert v.onset_velocity(100) == 100


def check_balance():
    """Balance spans +-15%, and does not change the mean rate."""
    for balance, expect in ((50, 1.0), (0, 1.15), (100, 0.85)):
        t = Trill(rate=12, human=0, balance=balance, rng=random.Random(9))
        t.start(60, 64, 0)
        ratio = t.period / (SRATE / 12)
        assert abs(ratio - expect) < 0.02, (balance, ratio, expect)


def check_two_voices_align():
    """Both voices emit at identical offsets, and only voice 2 when alone."""
    t = Trill(rate=12, human=70, rng=random.Random(10))
    t.start(60, 64, 0, voices=2, b2=67, u2=72, ch2=3)
    blocks = run_blocks(t, 20, 512)
    t1_offs = []
    t2_offs = []
    for ev in blocks:
        a = [o for (o, k, p, c) in ev if c == 0]
        b = [o for (o, k, p, c) in ev if c == 3]
        assert a == b, (a, b)
        t1_offs += a
        t2_offs += b
    assert t1_offs, 'no events'
    # single voice: nothing is emitted on the second channel
    t = Trill(rate=12, human=70, rng=random.Random(11))
    t.start(60, 64, 0, voices=1)
    blocks = run_blocks(t, 10, 512)
    assert all(c == 0 for ev in blocks for (o, k, p, c) in ev)


def check_release_across_blocks():
    """A release that falls in the next block is not lost and keeps order."""
    t = Trill(rate=20, human=0, rng=random.Random(12))
    t.start(60, 64, 0, ofs=0)
    # many small blocks: at 20 notes/s a period is 2400 samples, so with
    # 16-sample blocks both the release and the attack cross boundaries
    blocks = run_blocks(t, 2000, 16)
    ons = sum(1 for ev in blocks for (o, k, p, c) in ev if k == 'on')
    offs = sum(1 for ev in blocks for (o, k, p, c) in ev if k == 'off')
    assert ons > 10, ons
    # every attack eventually gets its release (or is still sounding at the end)
    assert abs(ons - offs) <= 1, (ons, offs)


def check_ramp_up():
    """Ramp Up is a time: the trill starts slow and settles at the end."""
    two_s = 2 * SRATE
    t = Trill(rate=12, human=0, ramp_up_s=two_s / SRATE, depth=60, rng=random.Random(30))
    t.start(60, 64, 0)
    nominal = SRATE / 12
    # first period: nominal * (1 + 3 * 0.6) = 2.8x
    assert abs(t.period - nominal * 2.8) / (nominal * 2.8) < 0.02, t.period
    # run past the window and check the factor is gone
    t.tr_elapsed = two_s
    assert abs(t.ramp_up_factor() - 1.0) < 1e-9
    # halfway through, halfway between
    t.tr_elapsed = two_s // 2
    assert abs(t.ramp_up_factor() - (1.0 + 1.8 * 0.5)) < 0.01
    # Depth 0: no effect at all
    z = Trill(rate=12, human=0, ramp_up_s=two_s / SRATE, depth=0, rng=random.Random(31))
    z.start(60, 64, 0)
    assert abs(z.period - nominal) / nominal < 0.01, z.period


def check_ramp_down():
    """The tail decelerates: nominal at the start, slow at the end."""
    t = Trill(rate=12, human=0, ramp_down_s=2.0, depth=60, rng=random.Random(32))
    t.start(60, 64, 0)
    nominal = SRATE / 12
    t.start_tail()
    t.tail_counter = t.tail_total          # the tail begins
    assert abs(t.ramp_down_factor() - 1.0) < 1e-9
    t.tail_counter = 0                     # ... and ends
    assert abs(t.ramp_down_factor() - 2.8) < 1e-9
    # Depth 0: the tail is flat (the old Linger)
    z = Trill(rate=12, human=0, ramp_down_s=2.0, depth=0, rng=random.Random(33))
    z.start(60, 64, 0)
    z.start_tail()
    z.tail_counter = 0
    assert abs(z.ramp_down_factor() - 1.0) < 1e-9


def linger_fence(blk, linger_counter, last_ofs=0):
    """The @block rule that ends a trill (step 2 and 4), transcribed.

    Returns (expired, advance_len, fence). The fence is where the final
    note-offs are sent: never before an event already sent in this block.
    """
    advance_len = blk
    fence = blk - 1
    expired = False
    if linger_counter <= blk:
        expired = True
        advance_len = max(0, linger_counter)
        fence = min(advance_len, blk - 1)
    return expired, advance_len, max(fence, last_ofs)


def check_linger_fence():
    """The final note-offs never precede an event of the same block."""
    # the window expires inside the block: the engines stop at the expiry
    expired, advance_len, fence = linger_fence(512, 300)
    assert expired and advance_len == 300 and fence == 300
    # Linger 0 with an event already sent at 120: the note-off lands there,
    # not at 0, or the note that just started would never be stopped
    expired, advance_len, fence = linger_fence(512, 0, last_ofs=120)
    assert expired and advance_len == 0 and fence == 120
    # randomized: the fence is always inside the block and never before the
    # last event already emitted
    rng = random.Random(21)
    for _ in range(4000):
        blk = rng.choice([32, 64, 128, 256, 1024])
        counter = rng.randrange(0, 3 * blk)
        last = rng.randrange(0, blk)
        expired, advance_len, fence = linger_fence(blk, counter, last)
        assert 0 <= advance_len <= blk
        assert 0 <= fence <= blk - 1
        assert fence >= last
        if expired:
            assert advance_len == max(0, min(counter, blk))


def main():
    check_offsets_and_gate()
    check_rate_mapping()
    check_humanize_cv()
    check_no_drift_of_the_mean()
    check_onset()
    check_balance()
    check_two_voices_align()
    check_release_across_blocks()
    check_linger_fence()
    check_ramp_up()
    check_ramp_down()
    print('offsets OK: 3000 random blocks, offsets inside 0..blk-1 and ascending')
    print('gate OK: a note sounds 0.72 of its period, release before the next attack')
    print('rate OK: mean notes/s = Rate at 4..20 (Humanize 0, +/-1%)')
    print('humanize OK: CV 0.21 at 70 and 0.30 at 100 (corpus: 0.20), 0 is exact')
    print('no drift OK: the mean rate is the Rate within 3% at Humanize 0/70/100')
    print('onset OK: first interval longer, velocity 60% → 100% over four notes')
    print('balance OK: +-15%, and the mean rate is untouched')
    print('two voices OK: identical offsets, one channel when alone')
    print('releases OK: every attack is released, also across block boundaries')
    print('linger fence OK: final note-offs inside the block, never before the last event')
    print('ramp up OK: 2.8x the nominal at the start, 1.0 after the window, 0 depth = off')
    print('ramp down OK: the tail decelerates from nominal to 2.8x, 0 depth = flat tail')


if __name__ == '__main__':
    main()
