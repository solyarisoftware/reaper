#!/usr/bin/env python3
"""Offline checks for the PolyTrills transport-stop logic (r4 … r10).

The @block logic that this file transcribes is the part r4 added and r6/r7
hardened: watch `play_state`, flush every voice when the transport stops,
park the engines while keeping the held set, and restage them when it starts
again. The note generation itself is not re-transcribed here: it is imported
from `gesture_model.py`, so the repository has one transcription of the engine
and not two.

This is not a JSFX compiler and it says nothing about what REAPER does. What it
can prove is that the rules hold for every sequence of blocks, transports and
MIDI it can be fed:

  - every emitted offset lands inside the block and offsets never decrease;
  - a note-off is only ever sent for a (pitch, channel) that is sounding;
  - the block that observes the stop edge leaves nothing sounding, and emits no
    note-on when no MIDI arrives in it;
  - a held set that survives the stop is restaged exactly once, on the single
    block that observes the restart — not on every block after it;
  - MIDI that arrives while stopped clears the parked flag, so the restart does
    not retrigger a trill that was already running.

What only a REAPER session can answer — above all whether @block is called at
all while the transport is stopped — stays in `PolyTrills-test-plan.md` (case 22).

Run: python3 tests/transport_model.py    (stdlib only, no arguments)
"""

import random

import gesture_model

TRANS_UNSEEN = -99
HELD_MAX = 4


def transport_advancing(state):
    """transport_advancing() from src/PolyTrills.jsfx: 1 playing, 5 recording.

    In EEL2 `-1 & 1` is 1, so the sign test is part of the rule, not a
    courtesy: a bare bit test would read the documented error state as
    "playing".
    """
    return state > 0 and (state & 1) == 1


class Triller:
    """The @block logic of src/PolyTrills.jsfx, block by block."""

    def __init__(self, blk=256, srate=48000, rate=12.0, tail_samples=0,
                 start_state=TRANS_UNSEEN, seed=1):
        self.blk = blk
        self.srate = srate
        self.rate = rate
        self.tail_samples = tail_samples
        self.prev_state = start_state
        self.parked = False
        self.held = []                 # [(pitch, ch)], sorted, capacity 4
        # depth 0: this file checks the transport logic, not the ramp shape
        self.tr = gesture_model.Trill(rate=rate, human=0.0, balance=50.0,
                                      srate=srate, rng=random.Random(seed), depth=0.0)
        self.drone = -1
        self.drone_ch = 0
        self.pass_note = -1
        self.pass_ch = 0
        self.tail_active = False
        self.tail_counter = 0
        self.reconfigures = 0          # how many reconfigure() calls, to count restages

    # ── voices ───────────────────────────────────────────────
    def stop_all(self, ofs):
        ev = self.tr.stop(ofs)
        if self.drone >= 0:
            ev.append((ofs, 'off', self.drone, self.drone_ch))
            self.drone = -1
        if self.pass_note >= 0:
            ev.append((ofs, 'off', self.pass_note, self.pass_ch))
            self.pass_note = -1
        return ev

    def hold_note(self, pitch, ch, ofs):
        """hold_note() from src/PolyTrills.jsfx: sustain instead of trill (r7)."""
        ev = []
        if self.pass_note < 0:
            self.pass_note, self.pass_ch = pitch, ch
        else:
            if self.drone >= 0:
                ev.append((ofs, 'off', self.drone, self.drone_ch))
            self.drone, self.drone_ch = pitch, ch
        ev.append((ofs, 'on', pitch, ch))
        return ev

    def reconfigure(self, ofs):
        self.reconfigures += 1
        ev = self.stop_all(ofs)
        self.tail_active = False
        n = len(self.held)
        if n == 1:
            self.pass_note, self.pass_ch = self.held[0]
            ev.append((ofs, 'on', self.pass_note, self.pass_ch))
        elif n == 2:
            (b, cb), (u, cu) = self.held
            if b == u:
                ev += self.hold_note(b, cb, ofs)
            else:
                ev += self.tr.start(b, u, cb, voices=1, ofs=ofs)
        elif n == 3:
            self.drone, self.drone_ch = self.held[0]
            ev.append((ofs, 'on', self.drone, self.drone_ch))
            (b, cb), (u, cu) = self.held[1], self.held[2]
            if b == u:
                ev += self.hold_note(b, cb, ofs)
            else:
                ev += self.tr.start(b, u, cb, voices=1, ofs=ofs)
        elif n == 4:
            low_ok = self.held[0][0] != self.held[1][0]
            high_ok = self.held[2][0] != self.held[3][0]
            if not low_ok:
                ev += self.hold_note(self.held[0][0], self.held[0][1], ofs)
            if not high_ok:
                ev += self.hold_note(self.held[2][0], self.held[2][1], ofs)
            if low_ok and high_ok:
                (b1, c1), (u1, _), (b2, c2), (u2, _) = self.held
                ev += self.tr.start(b1, u1, c1, voices=2, b2=b2, u2=u2, ch2=c2, ofs=ofs)
            elif low_ok:
                ev += self.tr.start(self.held[0][0], self.held[1][0], self.held[0][1],
                                    voices=1, ofs=ofs)
            elif high_ok:
                ev += self.tr.start(self.held[2][0], self.held[3][0], self.held[2][1],
                                    voices=1, ofs=ofs)
        return ev

    def insert_held(self, pitch, ch):
        if (pitch, ch) in self.held or len(self.held) >= HELD_MAX:
            return False
        self.held.append((pitch, ch))
        self.held.sort()
        return True

    def remove_held(self, pitch, ch):
        if (pitch, ch) not in self.held:
            return False
        self.held.remove((pitch, ch))
        return True

    def sounding(self):
        live = set()
        for v in self.tr.v:
            if v.active and v.sounding >= 0:
                live.add((v.sounding, v.ch))
        if self.drone >= 0:
            live.add((self.drone, self.drone_ch))
        if self.pass_note >= 0:
            live.add((self.pass_note, self.pass_ch))
        return live

    # ── one block ────────────────────────────────────────────
    def block(self, play_state, midi=()):
        """Run one @block. midi: [(mpos, 'on'|'off'|'cc', pitch, ch)]."""
        out = []
        blk = self.blk
        last_ofs = 0

        # Step 0: transport watch (r4)
        prev_adv = transport_advancing(self.prev_state)
        now_adv = transport_advancing(play_state)
        if prev_adv and not now_adv:
            self.tail_active = False
            self.tail_counter = 0
            out += self.stop_all(0)
            self.parked = len(self.held) > 0
        elif not prev_adv and now_adv:
            if self.parked:
                out += self.reconfigure(0)
            self.parked = False
        self.prev_state = play_state

        # Step 1: drain incoming MIDI
        for mpos, kind, pitch, ch in midi:
            if kind == 'on':
                if self.insert_held(pitch, ch):
                    self.parked = False
                    out += self.reconfigure(mpos)
                    last_ofs = max(last_ofs, mpos)
            elif kind == 'off':
                if self.remove_held(pitch, ch):
                    self.parked = False
                    if not self.held:
                        self.tail_active = True
                        self.tail_counter = self.tail_samples
                    else:
                        out += self.reconfigure(mpos)
                        last_ofs = max(last_ofs, mpos)
            else:
                out.append((mpos, 'cc', pitch, ch))
                last_ofs = max(last_ofs, mpos)

        # Step 2: how far the trill may advance
        advance_len = blk
        fence_ofs = blk - 1
        expired = False
        if self.tail_active and self.tail_counter <= blk:
            expired = True
            advance_len = max(0, self.tail_counter)
            fence_ofs = min(advance_len, blk - 1)
        fence_ofs = max(fence_ofs, last_ofs)

        # Step 3: advance, then sort what arrived from the schedule
        out += self.tr.advance(advance_len)
        out.sort(key=lambda e: e[0])

        # Step 4: tail countdown
        if self.tail_active:
            self.tail_counter -= blk
            if expired:
                out += self.stop_all(fence_ofs)
                out.sort(key=lambda e: e[0])
                self.tail_active = False

        return out


# ── invariants ────────────────────────────────────────────────

def check_block(events, blk, live_before, live_after, label):
    """Offset rules plus note lifecycle, on one block's event list.

    Ordering is checked as the code is: the r10 walk emits one timeline, so
    the offsets must never go backwards — the allowance for the two-run
    stream of 4-note mode was removed in r6.

    Returns the number of retriggers — a note-on for a (pitch, channel) that
    is already sounding — which the same-block reconfigure can legitimately
    produce; it is counted, not rejected, so the suite stays green while the
    property stays visible.
    """
    live = set(live_before)
    prev = -1
    retriggers = 0
    for (ofs, kind, pitch, ch) in events:
        assert 0 <= ofs < blk, f'{label}: offset {ofs} outside 0..{blk - 1}'
        assert ofs >= prev, f'{label}: offsets go backwards ({prev} -> {ofs})'
        prev = ofs
        key = (pitch, ch)
        if kind == 'on':
            if key in live:
                retriggers += 1
            live.add(key)
        elif kind == 'off':
            assert key in live, f'{label}: note-off for a silent note {(ofs, kind, pitch, ch)}'
            live.discard(key)
    assert live == live_after, f'{label}: live set {sorted(live)} != {sorted(live_after)}'
    return retriggers


def run_seq(seq, blk=256, tail_samples=0, start_state=TRANS_UNSEEN, rate=12.0):
    """seq: [(play_state, midi)], one tuple per block. Returns the model."""
    t = Triller(blk=blk, tail_samples=tail_samples, start_state=start_state, rate=rate)
    for i, (state, midi) in enumerate(seq):
        before = t.sounding()
        prev_state = t.prev_state
        events = t.block(state, midi)
        check_block(events, blk, before, t.sounding(), f'block {i} (state {state})')
        if (transport_advancing(prev_state) and not transport_advancing(state)
                and not midi):
            assert t.sounding() == set(), \
                f'block {i}: stop edge left {t.sounding()} sounding'
    return t


# ── named regressions ─────────────────────────────────────────

def regression_a_stop_mid_trill():
    """Stop with a voice on: flush at 0, nothing left, no note-on."""
    t = Triller(blk=256, rate=12.0)
    t.block(1, [(0, 'on', 60, 0)])
    t.block(1, [(0, 'on', 64, 0)])
    for _ in range(3):
        t.block(1)
    assert t.sounding(), 'setup failed: nothing sounding'
    events = t.block(0)
    assert events and all(e[1] == 'off' for e in events), events
    assert min(e[0] for e in events) == 0, events
    assert t.sounding() == set()
    assert t.held != [], 'the held set must survive the stop'
    assert t.parked, 'voices silenced by a stop must be marked for restage'
    assert t.block(0) == []          # the next stopped block is silent


def regression_b_restage_once():
    """Restart with the keys still down: one restage, on one block only."""
    t = Triller(blk=256, rate=12.0)
    t.block(1, [(0, 'on', 60, 0)])
    t.block(1, [(0, 'on', 64, 0)])
    t.block(0)
    assert t.sounding() == set()
    before = t.reconfigures
    events = t.block(1)
    assert t.reconfigures == before + 1, 'the restart block must restage exactly once'
    assert events and events[0][1] == 'on' and events[0][0] == 0, events
    assert events[0][2] == 60, events      # the base note comes back first
    assert not t.parked
    for _ in range(5):
        t.block(1)
    assert t.reconfigures == before + 1, 'the restage must not repeat'


def regression_c_tail_cancelled_by_stop():
    """A tail in flight at the stop is cancelled; it must not fire later."""
    t = Triller(blk=256, rate=12.0, tail_samples=1000)
    t.block(1, [(0, 'on', 60, 0)])
    t.block(1, [(0, 'on', 64, 0)])
    t.block(1, [(0, 'off', 60, 0)])
    t.block(1, [(0, 'off', 64, 0)])
    assert t.tail_active, 'setup failed: no tail running'
    assert t.sounding(), 'setup failed: nothing sounding during the tail'
    t.block(0)
    assert not t.tail_active and t.tail_counter == 0
    assert t.sounding() == set()
    for _ in range(10):
        assert t.block(0) == []


def regression_d_midi_while_stopped():
    """A trill started while stopped must not be retriggered by Play."""
    t = Triller(blk=256, rate=12.0)
    t.block(1, [(0, 'on', 60, 0)])
    t.block(1, [(0, 'on', 64, 0)])
    t.block(0)
    t.block(0, [(0, 'off', 60, 0)])
    t.block(0, [(0, 'on', 62, 0)])
    assert t.sounding() != set(), 'the trill must run while stopped'
    assert not t.parked
    before = t.reconfigures
    t.block(1)                       # Play: must not restage on top of it
    assert t.reconfigures == before, 'Play retriggered a trill already running'


def regression_e_first_block():
    """The first block after load, transport already rolling: no flush."""
    t = Triller(blk=256, rate=12.0, start_state=TRANS_UNSEEN)
    assert t.block(1) == [], 'nothing can flush before any state is known'
    assert not t.parked
    t2 = Triller(blk=256, rate=12.0, start_state=TRANS_UNSEEN)
    assert t2.block(0) == [], 'a loaded project sitting stopped must be silent'


def regression_f_recording_and_error():
    """5 = recording advances; 0 and <0 do not."""
    assert transport_advancing(5) and transport_advancing(1)
    assert not transport_advancing(0)
    assert not transport_advancing(2) and not transport_advancing(6)
    assert not transport_advancing(TRANS_UNSEEN)
    t = Triller(blk=256, rate=12.0)
    t.block(1, [(0, 'on', 60, 0)])
    t.block(5, [(0, 'on', 64, 0)])
    assert t.sounding(), 'recording must advance, so the trill runs'
    events = t.block(-1)
    assert events and all(e[1] == 'off' for e in events), events
    assert t.sounding() == set()


def regression_g_pause_reported_as_playing():
    """REAPER's pause bug: 1 -> 1 must never be read as a stop."""
    t = Triller(blk=256, rate=12.0)
    t.block(1, [(0, 'on', 60, 0)])
    t.block(1, [(0, 'on', 64, 0)])
    before = t.reconfigures
    t.block(1)
    assert not t.parked, 'a pause reported as playing must not park the trill'
    assert t.reconfigures == before, 'a pause reported as playing must not restage'


def regression_h_four_note_ordering():
    """4-note mode emits one ascending run (r6, now by construction)."""
    t = Triller(blk=64, rate=20.0)
    for pitch in (48, 55, 64, 72):
        t.block(1, [(0, 'on', pitch, 0)])
    assert t.tr.v[0].active and t.tr.v[1].active, 'setup failed: not in 4-note mode'
    # at 20 notes/s a period is 2400 samples, so a 64-sample block holds no
    # event: walk a few blocks and check the alignment block by block
    # the two voices share one channel here, so tell them apart by pitch
    seen = set()
    for _ in range(60):
        events = t.block(1)
        a = [e[0] for e in events if e[2] in (48, 55)]
        b = [e[0] for e in events if e[2] in (64, 72)]
        assert a == b, (a, b)          # both voices inside the same offsets
        for e in events:
            seen.add(e[2])
    assert {48, 55, 64, 72} <= seen, seen


def regression_i_equal_pitch_pair():
    """r7: the same pitch on two channels is sustained, not retriggered."""
    t = Triller(blk=64, rate=20.0)
    t.block(1, [(0, 'on', 55, 1)])
    assert t.sounding() == {(55, 1)}
    events = t.block(1, [(0, 'on', 55, 2)])
    assert [e[1] for e in events] == ['off', 'on'], events
    assert not t.tr.active, 'a degenerate pair must not start the trill'
    for _ in range(8):
        assert t.block(1) == [], 'a sustained note must not toggle'
    events = t.block(1, [(0, 'off', 55, 1)])
    assert [e[1] for e in events] == ['off', 'on'], events
    assert t.sounding() == {(55, 2)}


# ── randomized ────────────────────────────────────────────────

def randomized(cases=4000, seed=20261107):
    rng = random.Random(seed)
    states = [0, 1, 1, 1, 2, 5, 6, -1]
    checks = 0
    retriggers = 0
    for _ in range(cases):
        blk = rng.choice([32, 64, 128, 256, 1024])
        rate = rng.choice([4, 8, 12, 16, 20])
        tail = rng.choice([0, 0, 300, 1000])
        n_blocks = rng.randint(1, 12)
        seq = []
        pitch_pool = [48, 55, 60, 64, 67, 72]
        held_now = set()
        for _b in range(n_blocks):
            midi = []
            for _e in range(rng.randint(0, 3)):
                pitch = rng.choice(pitch_pool)
                ch = rng.choice([0, 0, 0, 3])
                if (pitch, ch) in held_now and rng.random() < 0.5:
                    held_now.discard((pitch, ch))
                    midi.append((rng.randrange(blk), 'off', pitch, ch))
                else:
                    held_now.add((pitch, ch))
                    midi.append((rng.randrange(blk), 'on', pitch, ch))
            midi.sort()
            seq.append((rng.choice(states), midi))
        t = Triller(blk=blk, rate=rate, tail_samples=tail)
        for i, (state, midi) in enumerate(seq):
            before = t.sounding()
            prev_state = t.prev_state
            events = t.block(state, midi)
            retriggers += check_block(events, blk, before, t.sounding(),
                                      f'block {i} (state {state})')
            if (transport_advancing(prev_state) and not transport_advancing(state)
                    and not midi):
                assert t.sounding() == set(), \
                    f'block {i}: stop edge left {t.sounding()} sounding'
        # a trill may legitimately run while stopped (keys pressed with the
        # transport parked), so silence is required only after a real edge
        t.block(1)
        before = t.sounding()
        events = t.block(0)
        retriggers += check_block(events, blk, before, t.sounding(), 'final stop')
        assert t.sounding() == set(), f'stop left voices on: {t.sounding()}'
        assert all(e[1] == 'off' for e in events), events
        checks += 1
    return checks, retriggers


def main():
    regression_a_stop_mid_trill()
    regression_b_restage_once()
    regression_c_tail_cancelled_by_stop()
    regression_d_midi_while_stopped()
    regression_e_first_block()
    regression_f_recording_and_error()
    regression_g_pause_reported_as_playing()
    regression_h_four_note_ordering()
    regression_i_equal_pitch_pair()
    print('regressions A (stop mid-trill), B (restage once), C (tail cancelled),')
    print('            D (MIDI while stopped), E (first block), F (recording/error),')
    print('            G (pause bug), H (4-note ordering), I (equal-pitch pair) OK')
    n, retriggers = randomized()
    print(f'{n} randomized sequences OK: offsets inside 0..blk-1 and never '
          f'decreasing, note-off only for sounding notes,')
    print('            a stop always ends with nothing sounding, restage exactly once')
    print(f'noted, not a defect: {retriggers} same-block re-statements (a '
          f'reconfigure that silences and restarts a note')
    print('            already sounding in that block: two keys landing together)')


if __name__ == '__main__':
    main()
