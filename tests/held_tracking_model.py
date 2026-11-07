#!/usr/bin/env python3
"""Offline checks for the PolyTrills held-note tracking (dev revision r2).

Transcribes `insert_held()` / `remove_held()` from `src/PolyTrills.jsfx` and checks
the invariants the @block depends on:

- a held note is identified by ``(pitch, channel)``, not by pitch alone;
- the array stays sorted ascending by pitch, ties broken by channel;
- no ``(pitch, channel)`` pair appears twice, and never more than 4 entries;
- both functions report whether the held set changed, which is what stops a
  redundant note-on from restarting the engines.

Like `timing_model.py`, this is a model of the algorithm, not a JSFX compiler and
not a test inside REAPER.

Run: python3 tests/held_tracking_model.py    (stdlib only, no arguments)
"""

import random

CAPACITY = 4


class Held:
    """insert_held()/remove_held() from src/PolyTrills.jsfx, transcribed."""

    def __init__(self):
        self.notes = []    # held_notes[]
        self.vels = []     # held_vels[]
        self.chans = []    # held_channels[]

    @property
    def count(self):
        return len(self.notes)

    def keys(self):
        return list(zip(self.notes, self.chans))

    def insert(self, pitch, vel, ch):
        """Returns 1 if the held set changed, 0 otherwise."""
        if (pitch, ch) in self.keys():
            return 0
        if self.count >= CAPACITY:
            return 0
        i = 0
        while i < self.count and (self.notes[i] < pitch or
                                 (self.notes[i] == pitch and self.chans[i] < ch)):
            i += 1
        self.notes.insert(i, pitch)
        self.vels.insert(i, vel)
        self.chans.insert(i, ch)
        return 1

    def remove(self, pitch, ch):
        """Returns 1 if an entry was removed, 0 otherwise."""
        if (pitch, ch) not in self.keys():
            return 0
        i = self.keys().index((pitch, ch))
        del self.notes[i], self.vels[i], self.chans[i]
        return 1


class Oracle:
    """Independent statement of what the held set should be."""

    def __init__(self):
        self.held = []

    def insert(self, pitch, ch):
        if (pitch, ch) in self.held or len(self.held) >= CAPACITY:
            return 0
        self.held.append((pitch, ch))
        return 1

    def remove(self, pitch, ch):
        if (pitch, ch) not in self.held:
            return 0
        self.held.remove((pitch, ch))
        return 1


def check_sequence(events):
    held, oracle = Held(), Oracle()
    for n, (kind, pitch, ch) in enumerate(events):
        if kind == 'on':
            got = held.insert(pitch, 64 + n % 60, ch)
            want = oracle.insert(pitch, ch)
        else:
            got = held.remove(pitch, ch)
            want = oracle.remove(pitch, ch)
        assert got == want, (n, kind, pitch, ch, got, want)

        assert held.count == len(oracle.held), (n, held.keys(), oracle.held)
        assert held.count <= CAPACITY
        keys = held.keys()
        assert len(set(keys)) == len(keys), ('duplicate entry', n, keys)
        assert keys == sorted(keys), ('not sorted by (pitch, channel)', n, keys)
        assert sorted(keys) == sorted(oracle.held), (n, keys, oracle.held)
        assert len(held.vels) == len(held.chans) == held.count


def main():
    random.seed(11)
    cases = 0
    for _ in range(3000):
        events = []
        for _ in range(random.randrange(1, 40)):
            kind = random.choice(['on', 'on', 'off'])
            pitch = random.choice([60, 62, 64, 67])
            ch = random.choice([0, 0, 1, 2])
            events.append((kind, pitch, ch))
        check_sequence(events)
        cases += 1

    # A: same pitch on two channels is two notes; a note-off removes only its own.
    h = Held()
    assert h.insert(60, 100, 0) == 1
    assert h.insert(60, 90, 1) == 1
    assert h.count == 2 and h.keys() == [(60, 0), (60, 1)]
    assert h.remove(60, 1) == 1 and h.keys() == [(60, 0)]
    assert h.remove(60, 1) == 0, 'second note-off must be a no-op'

    # B: redundant note-on on the same (pitch, channel) changes nothing, so
    #    @block does not reconfigure and the engines are not restarted.
    assert h.insert(60, 55, 0) == 0
    assert h.keys() == [(60, 0)]

    # C: ordering. Ties on the same pitch are ordered by channel.
    h = Held()
    for pitch, ch in [(67, 2), (60, 1), (60, 0), (72, 3)]:
        assert h.insert(pitch, 80, ch) == 1
    assert h.keys() == [(60, 0), (60, 1), (67, 2), (72, 3)], h.keys()

    # D: capacity. The fifth note is dropped, and its later note-off is a no-op.
    assert h.insert(75, 80, 0) == 0 and h.count == 4
    assert h.remove(75, 0) == 0 and h.count == 4

    # E: two identical note-ons from a controller that retriggers must not
    #    change the set after the first one.
    h = Held()
    assert [h.insert(60, 100, 0) for _ in range(3)] == [1, 0, 0]

    print(f'{cases} randomized sequences OK: (pitch, channel) identity, sorted '
          f'order, no duplicates, capacity 4, return values match the oracle')
    print('regressions A (two channels), B (redundant note-on), C (ordering), '
          'D (capacity), E (retrigger) OK')


if __name__ == '__main__':
    main()
