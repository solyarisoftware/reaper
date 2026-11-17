#!/usr/bin/env python3
"""Stdlib-only C note model and source assertions; not an EEL2/host test."""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
import re
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[2] / "bloomscope"


@dataclass
class Note:
    on: float
    end: float
    pitch: int
    channel: int
    velocity: int
    kind: int  # 0 active, 1 received off, 2 discontinuity truncation
    segment: int
    has_on: bool
    next: int = 0
    prev: int = 0


class BloomScopeMidiModel:
    """Mirror the fixed ring, index+1 FIFO links and capture_block lifecycle."""
    def __init__(self, capacity=4096, segment_capacity=256, rate=48000):
        self.capacity = capacity
        self.segment_capacity = segment_capacity
        self.rate = rate
        self.records = [None] * capacity
        self.first = [0] * 2048
        self.last = [0] * 2048
        self.n = self.head = self.written = self.dropped = 0
        self.segments = []
        self.segment_id = 0
        self.running = False
        self.previous_state = -1
        self.previous_freeze = False
        self.previous_position = 0.0
        self.previous_length = 0
        self.output = []
        self.revision = 0

    def reset_data(self):
        self.revision += 1
        self.n = self.head = self.dropped = 0
        self.first[:] = [0] * 2048
        self.last[:] = [0] * 2048
        self.segments.clear()
        self.running = False
        self.revision += 1

    def unlink(self, idx):
        r = self.records[idx]
        key = r.channel * 128 + r.pitch
        if r.prev:
            self.records[r.prev - 1].next = r.next
        else:
            self.first[key] = r.next
        if r.next:
            self.records[r.next - 1].prev = r.prev
        else:
            self.last[key] = r.prev

    def new(self, t, pitch, ch, velocity, has_on):
        idx = self.head
        if self.n == self.capacity:
            if self.records[idx].kind == 0:
                self.unlink(idx)
            self.dropped += 1
        r = Note(t, t, pitch, ch, velocity, 0 if has_on else 1,
                 self.segment_id, has_on)
        self.records[idx] = r
        if has_on:
            key = ch * 128 + pitch
            r.prev = self.last[key]
            if r.prev:
                self.records[r.prev - 1].next = idx + 1
            else:
                self.first[key] = idx + 1
            self.last[key] = idx + 1
        self.head = (self.head + 1) % self.capacity
        self.n = min(self.n + 1, self.capacity)
        self.written += 1

    def held(self):
        return [self.records[(self.head - self.n + k) % self.capacity]
                for k in range(self.n)]

    def end_segment(self):
        if self.running:
            end = self.segments[-1][2]
            for r in self.held():
                if r.kind == 0:
                    r.kind, r.end = 2, end
            self.first[:] = [0] * 2048
            self.last[:] = [0] * 2048
            self.running = False

    def block(self, t, length, events=(), state=1, freeze=False,
              reset=True, rate=None, clear=False, ready=True, during_drain=None,
              before_drain=None, after_setup=None):
        if clear:
            self.reset_data()
        if rate is not None and rate != self.rate:
            self.rate = rate
            self.reset_data()
            self.previous_state = -1
            self.previous_freeze = freeze
        boundary = state != 1
        if state == 1:
            if self.previous_state == 1:
                expected = self.previous_position + self.previous_length / self.rate
                tol = .5 * self.previous_length / self.rate + .0005
                boundary = abs(t - expected) > tol
            else:
                if reset and not freeze:
                    self.reset_data()
                boundary = True
        boundary |= freeze != self.previous_freeze
        if before_drain:
            before_drain(boundary)
        writing = not freeze and (self.running or (ready and state == 1))
        changed = False
        if writing:
            self.revision += 1
            if (boundary or state != 1 or not ready) and self.running:
                self.end_segment()
                changed = True
            if ready and state == 1:
                if not self.running:
                    self.segment_id += 1
                    self.segments.append([self.segment_id, t, t, 0])
                    self.segments[:] = self.segments[-self.segment_capacity:]
                    self.running = True
                    changed = True
                self.segments[-1][2] = t + length / self.rate
        if after_setup:
            after_setup(changed)
        for offset, msg1, msg2, msg3 in events:
            self.output.append((offset, msg1, msg2, msg3))
            if writing and ready and state == 1 and self.running:
                typ, ch, pitch, vel = msg1 & 240, msg1 & 15, msg2 & 127, msg3 & 127
                time = t + offset / self.rate
                if typ == 144 and vel > 0:
                    self.new(time, pitch, ch, vel, True)
                elif typ == 128 or (typ == 144 and vel == 0):
                    first = self.first[ch * 128 + pitch]
                    if first:
                        r = self.records[first - 1]
                        self.unlink(first - 1)
                        r.end, r.kind = time, 1
                    else:
                        self.new(time, pitch, ch, 0, False)
            if during_drain:
                during_drain(self)
        if writing:
            self.revision += 1
        self.previous_state = state
        self.previous_position = t
        self.previous_length = length
        self.previous_freeze = freeze

    def publish_audio_hop(self, ticket):
        if self.running and self.segments[-1][3] == 0:
            self.revision += 1
            self.segments[-1][3] = ticket
            self.revision += 1

    def snapshot_midi(self, during_copy=None):
        revision = self.revision
        if revision % 2:
            return None
        records = tuple(replace(r) for r in self.held())
        segments = tuple(tuple(s) for s in self.segments)
        if during_copy:
            during_copy()
        if revision != self.revision:
            return None
        return records, segments

    def visible(self, now, window):
        # MIDI-only tests exercise pairing. Joint tests additionally gate on audio.
        return visible_notes(self.held(), self.segments, now, window)


def visible_notes(records, segments, now, window, audio_segment=None, audio_written=None):
    if audio_segment is not None:
        segments = [s for s in segments if s[0] <= audio_segment and 0 < s[3] <= audio_written]
    out = []
    for r in records:
        end = now if r.kind == 0 else min(r.end, now)
        found = any(s[0] == r.segment for s in segments)
        hidden = any(s[0] > r.segment and s[1] <= now and
                     s[1] <= end and s[2] >= r.on for s in segments)
        if found and not hidden and r.on <= now and end >= now - window:
            out.append(r)
    return out


@dataclass(frozen=True)
class AudioSnapshot:
    now: float
    segment: int
    written: int
    points: tuple  # (hop-end time, published segment, real break)


class BloomScopeJointModel(BloomScopeMidiModel):
    """Separate @block/drain, @sample and joint @gfx phases, without modeling DSP."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.epoch = self.cap_revision = self.audio_written = 0
        self.audio_now = 0.0
        self.audio_segment = self.partial = self.sample_offset = 0
        self.break_next = True
        self.audio_points = []
        self.acquiring = False

    def reset_data(self):
        self.cap_revision += 1
        self.epoch += 1
        super().reset_data()
        self.audio_now = 0.0
        self.audio_segment = self.partial = 0
        self.audio_points.clear()
        self.break_next = True
        self.epoch += 1
        self.cap_revision += 1

    def drop_hop(self, boundary):
        if boundary:
            if self.partial or not self.break_next:
                self.epoch += 1
            self.partial = 0
            self.break_next = True

    def segment_setup(self, changed):
        if changed:
            self.epoch += 1

    def block(self, t, length, events=(), process_samples=True, **kwargs):
        super().block(t, length, events, before_drain=self.drop_hop,
                      after_setup=self.segment_setup, **kwargs)
        self.block_time = t
        self.sample_offset = 0
        self.acquiring = (kwargs.get("state", 1) == 1 and not kwargs.get("freeze", False)
                          and kwargs.get("ready", True))
        if process_samples:
            self.samples(length)

    def samples(self, length):
        if not self.acquiring:
            return
        for _ in range(length):
            self.partial += 1
            self.sample_offset += 1
            if self.partial == 32:
                self.cap_revision += 1
                self.audio_written += 1
                self.publish_audio_hop(self.audio_written)
                self.audio_now = self.block_time + self.sample_offset / self.rate
                self.audio_segment = self.segment_id
                self.audio_points.append((self.audio_now, self.audio_segment, self.break_next))
                capacity = math.ceil(30.3 * self.rate / 32) + 2
                self.audio_points[:] = self.audio_points[-capacity:]
                self.partial = 0
                self.break_next = False
                self.cap_revision += 1

    def frame(self, window=2, after_audio=None, during_midi_copy=None):
        epoch, revision = self.epoch, self.cap_revision
        if revision % 2:
            return None
        audio = AudioSnapshot(self.audio_now, self.audio_segment, self.audio_written,
                              tuple(self.audio_points))
        if self.cap_revision != revision:
            return None
        if after_audio:
            after_audio()
        midi = self.snapshot_midi(during_midi_copy)
        if midi is None or epoch != self.epoch:
            return None
        records, segments = midi
        return audio, visible_notes(records, segments, audio.now, window,
                                    audio.segment, audio.written)


@dataclass(frozen=True)
class MidiStripLayout:
    row_budget: int
    strip_rows: int  # 22 px units, not the number of visible semitones
    strip_h: int
    plot_h: int
    panel_h: int
    panels_fit: bool
    row_h: float  # actual per-semitone height; zero when the strip is not drawn
    marker_h: int  # common integer head size, fitting every pitch row


def midi_strip_layout(height, pitches, view=0, visible=True):
    """Mirror calculate_layout and draw_notes height arithmetic, not rendering."""
    top = 6 + 24 + 8
    bottom = height - 24 - 17
    panels = 2 if view == 2 else 1
    audio_min_h = panels * 40 + (panels - 1) * 6
    rows = min(8, max(4, math.floor((bottom - top - audio_min_h - 18) / 22)))
    strip_rows = min(pitches, rows) if visible else 0
    strip_h = 18 + 22 * strip_rows if visible else 0
    h = bottom - top - strip_h
    short_notes = visible and h < audio_min_h
    if short_notes:
        strip_rows = strip_h = 0
        h = bottom - top
    h = max(h, 1) if short_notes else max(h, 40)
    fit = not short_notes
    panel_h = h
    if panels == 2:
        panel_h = math.floor((h - 6) / 2)
        if panel_h < 40:
            fit = False
            panel_h = max(panel_h, 1)
    row_h = (strip_h - 18) / max(pitches, 1) if strip_h else 0
    marker_h = 8 if fit and strip_h else 0
    for row in range(pitches):
        ly = 38 + h + 2 + 17 + 18 + row * row_h
        bar = math.floor(ly + row_h * .75)
        marker_h = max(0, min(marker_h, bar - math.ceil(ly), math.floor(ly + row_h) - 1 - bar))
    return MidiStripLayout(rows, strip_rows, strip_h, h, panel_h, fit, row_h, marker_h)


def note_arrow_primitives(x, base_y, height, left, right, off=False):
    """Model the shared, pixel-mirrored rectangle rows, including boundary cuts."""
    cx = math.floor(x + .5)
    primitives = []
    for i in range(height):
        half = height - 1 - i
        start, end = max(left, cx - half), min(right, cx + half)
        py = base_y + 1 + i if off else base_y - 1 - i
        if start <= end:
            primitives.append(("rect", start, py, end - start + 1, 1))
    return primitives


def note_primitive_extent(primitive):
    """Bounds of a requested primitive, independent of the strip allocation."""
    kind, *args = primitive
    if kind == "circle":
        x, y, r = args
        return x - r, y - r, x + r, y + r
    if kind == "rect":
        x, y, w, h = args
        return x, y, x + w - 1, y + h - 1
    if kind == "line":
        x1, y1, x2, y2 = args
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
    if kind == "polygon":
        return min(args[::2]), min(args[1::2]), max(args[::2]), max(args[1::2])
    raise AssertionError(f"unknown primitive: {kind}")


def strip_note_marker_primitives(layout, row, x, left, right, off=False):
    """Mirror the strip's marker centre/radius and its concrete drawing primitives."""
    if not layout.panels_fit or not layout.strip_h:
        return []
    midi_y = 38 + layout.plot_h + 2 + 17
    row_top = midi_y + 18 + row * layout.row_h
    y = math.floor(row_top + layout.row_h * .75)
    return note_arrow_primitives(x, y - 1 if off else y, layout.marker_h, left, right, off)


def note_heading_candidates(dense, capped, pitches):
    full = f"MIDI: {pitches} pitches; dense rows (labels omitted)" if dense else "MIDI notes"
    if capped:
        full += " (history capped)"
    compact = ("MIDI: dense, capped" if dense and capped else "MIDI: dense (no labels)" if dense
               else "MIDI: history capped" if capped else "MIDI notes")
    short = "dense/capped" if dense and capped else "dense" if dense else "capped" if capped else "MIDI"
    minimal = "D/C" if dense and capped else "D" if dense else "C" if capped else "M"
    return full, compact, short, minimal


def fit_note_heading(dense, capped, pitches, width, measure):
    candidates = note_heading_candidates(dense, capped, pitches)
    for tier, text in enumerate(candidates):
        if measure(text) <= width - 8 or tier == 3:
            return text, tier
    raise AssertionError("bounded heading tiers exhausted")


def on(offset=0, pitch=60, ch=0, velocity=96):
    return offset, 0x90 | ch, pitch, velocity


def off(offset=0, pitch=60, ch=0, zero_on=False):
    return offset, (0x90 if zero_on else 0x80) | ch, pitch, 0


class BloomScopeMidiTests(unittest.TestCase):
    def test_sub_block_time_and_both_off_encodings(self):
        m = BloomScopeMidiModel()
        m.block(3, 512, [on(7), off(300, zero_on=True), on(320, 64), off(511, 64)])
        a, b = m.held()
        self.assertAlmostEqual(a.on, 3 + 7 / 48000)
        self.assertAlmostEqual(a.end, 3 + 300 / 48000)
        self.assertAlmostEqual(b.end, 3 + 511 / 48000)
        self.assertEqual((a.kind, b.kind), (1, 1))
        self.assertEqual((a.velocity, b.velocity), (96, 96))

    def test_channel_aware_polyphony_and_repeated_pitch_fifo(self):
        m = BloomScopeMidiModel()
        m.block(0, 512, [on(0), on(1, ch=1), on(2), on(3, pitch=64),
                         off(20), off(21, ch=1), off(22), off(23, pitch=64)])
        notes = m.held()
        self.assertEqual([n.end for n in notes], [v / 48000 for v in (20, 21, 22, 23)])
        self.assertEqual([n.channel for n in notes], [0, 1, 0, 0])
        self.assertFalse(any(m.first))
        self.assertFalse(any(m.last))

    def test_unmatched_off_is_only_an_off_reference(self):
        m = BloomScopeMidiModel()
        m.block(0, 512, [off(100, ch=3)])
        (r,) = m.held()
        self.assertFalse(r.has_on)
        self.assertEqual(r.kind, 1)
        self.assertEqual(r.on, r.end)
        self.assertEqual(m.visible(200 / 48000, 1), [r])

    def test_all_messages_pass_when_frozen_stopped_full_or_unavailable(self):
        events = [on(), off(2), (4, 0xB5, 11, 99), (6, 0xE1, 0, 64),
                  (8, 0xC0, 4, 0), (10, 0xF8, 0, 0), (12, 0xA2, 60, 33)]
        for settings in ({"freeze": True}, {"state": 0}, {"ready": False}, {}):
            m = BloomScopeMidiModel(capacity=1)
            m.block(0, 512, events, **settings)
            self.assertEqual(m.output, events)
            self.assertLessEqual(m.n, 1)
        m = BloomScopeMidiModel()
        m.block(0, 512, events[2:])
        self.assertEqual(m.n, 0)
        self.assertFalse(m.visible(.005, 1))

    def test_ring_eviction_unlinks_active_without_cross_pairing(self):
        m = BloomScopeMidiModel(capacity=2)
        m.block(0, 512, [on(0), on(1), on(2), off(3), off(4), off(5)])
        self.assertEqual(m.dropped, 2)  # third on and orphan off evict oldest
        self.assertEqual(m.n, 2)
        self.assertEqual([r.has_on for r in m.held()], [True, False])
        self.assertEqual(m.held()[0].end, 4 / 48000)
        self.assertFalse(any(m.first))

    def test_random_ring_fifo_links_match_simple_reference(self):
        import random
        rng = random.Random(164)
        m = BloomScopeMidiModel(capacity=7)
        reference = []
        for i in range(300):
            pitch, ch = rng.randrange(3) + 60, rng.randrange(2)
            is_on = rng.choice((True, False))
            event = on(0, pitch, ch) if is_on else off(0, pitch, ch)
            m.block(i * 512 / 48000, 512, [event], reset=False)
            active = next((r for r in reference if r[1:3] == [pitch, ch] and r[3]), None)
            if is_on or active is None:
                reference.append([i, pitch, ch, is_on])
                reference = reference[-7:]
            else:
                active[3] = False
            self.assertEqual([(r.pitch, r.channel, r.kind == 0) for r in m.held()],
                             [(r[1], r[2], r[3]) for r in reference])

    def test_visibility_active_long_note_ages_completed_history(self):
        m = BloomScopeMidiModel()
        m.block(0, 512, [on()])
        self.assertEqual(len(m.visible(40, 1)), 1)
        m.block(512 / 48000, 512, [off()])
        self.assertEqual(m.visible(40, 1), [])

    def test_future_events_are_clipped_to_audio_snapshot(self):
        m = BloomScopeMidiModel()
        m.block(0, 512, [on(100), off(400), on(500, 64)])
        self.assertEqual(m.visible(99 / 48000, 1), [])
        (r,) = m.visible(300 / 48000, 1)
        self.assertEqual(r.pitch, 60)
        self.assertGreater(r.end, 300 / 48000)  # draw as open, no off guide yet
        self.assertEqual(len(m.visible(512 / 48000, 1)), 2)

    def test_freeze_preserves_notes_through_stop_start_and_incoming_off(self):
        m = BloomScopeMidiModel()
        m.block(0, 512, [on()], reset=False)
        before = repr((m.held(), m.segments))
        m.block(512 / 48000, 512, [off()], freeze=True)
        m.block(0, 512, [on()], state=0, freeze=True)
        m.block(8, 512, [off()], freeze=True)
        self.assertEqual(repr((m.held(), m.segments)), before)
        m.block(8 + 512 / 48000, 512, [off()], reset=False)
        old, orphan = m.held()
        self.assertEqual(old.kind, 2)
        self.assertAlmostEqual(old.end, 512 / 48000)
        self.assertFalse(orphan.has_on)  # no pairing across Freeze acquisition gap

    def test_stop_seek_dropped_block_and_recording_terminate_without_false_off(self):
        for next_time, state in ((10, 1), (-2, 1), (3 * 512 / 48000, 1),
                                 (512 / 48000, 0), (512 / 48000, 5)):
            m = BloomScopeMidiModel()
            m.block(0, 512, [on()], reset=False)
            m.block(next_time, 512, [off()], state=state, reset=False)
            self.assertEqual(m.held()[0].kind, 2)
            if state == 1:
                self.assertFalse(m.held()[1].has_on)

    def test_reset_on_play_clear_and_rate_reset_both_histories(self):
        for action in ("clear", "rate", "restart"):
            m = BloomScopeMidiModel()
            m.block(0, 512, [on()])
            if action == "clear":
                m.block(512 / 48000, 512, clear=True, freeze=True)
            elif action == "rate":
                m.block(0, 512, rate=96000, freeze=True)
            else:
                m.block(0, 512, state=0)
                m.block(2, 512, reset=True)
            self.assertEqual(m.n, 0)
            self.assertFalse(any(m.first))
            self.assertFalse(any(m.last))

    def test_newer_audio_segment_suppresses_overlapped_old_bar(self):
        m = BloomScopeMidiModel()
        m.block(0, 48000, [on(), off(47000)], reset=False)
        m.block(.4, 10000, [], reset=False)
        self.assertEqual(m.visible(.6, 2), [])  # new audio, no invented old note
        # A forward seek retains the old note when the window still contains it.
        m = BloomScopeMidiModel()
        m.block(0, 48000, [on(), off(47000)], reset=False)
        m.block(2, 512, reset=False)
        self.assertEqual(len(m.visible(2.01, 3)), 1)

    def test_segment_retention_is_bounded_and_unowned_notes_are_hidden(self):
        m = BloomScopeMidiModel(segment_capacity=2)
        m.block(0, 512, [on(), off(10)], reset=False)
        m.block(3, 512, reset=False)
        m.block(6, 512, reset=False)
        self.assertEqual(len(m.segments), 2)
        self.assertEqual(m.visible(6, 30), [])

    def test_memory_ranges_fit_and_do_not_overlap_b_audio_map(self):
        base = 122 + 12 + 3 * 2048 + 4096 * 4
        sizes = [4096 * 10, 2048, 2048, 256 * 4, 4096 * 8,
                 256 * 4, 4096, 128, 128]
        note_end = base + sum(sizes)
        self.assertEqual(sum(sizes), 84224)
        pos = base
        for size in sizes:
            self.assertLess(pos, pos + size)
            pos += size
        self.assertEqual(pos, note_end)
        stride = (8388608 - note_end) // 24
        for rate in (44100, 48000, 96000, 192000):
            self.assertLessEqual(math.ceil(30.3 * rate / 32) + 2, stride)
        self.assertGreater(math.ceil(30.3 * 384000 / 32) + 2, stride)
        self.assertLessEqual(note_end + 24 * stride, 8388608)
        midi = (SRC / "bloomscope_midi.jsfx-inc").read_text()
        self.assertIn("midi_ready = MEM_MIDI_END <= __memtop()", midi)

    def test_declared_eel_memory_map_matches_nonoverlapping_model(self):
        midi = (SRC / "bloomscope_midi.jsfx-inc").read_text()
        capture = (SRC / "bloomscope_capture.jsfx-inc").read_text()
        bar = (SRC / "bloomscope_controlbar.jsfx-inc").read_text()
        values = {}

        def arithmetic(expression):
            self.assertRegex(expression, r"^[A-Za-z0-9_ +*]+$")
            return eval(expression, {"__builtins__": {}}, values)

        for name in ("MIDI_CAPACITY", "MIDI_KEYS", "MIDI_SEGMENTS", "MIDI_SEGMENT_FIELDS",
                     "MIDI_FIELDS", "MIDI_RECORD_STRIDE"):
            expression = re.search(rf"^{name} = ([^;]+);", midi, re.MULTILINE)[1]
            values[name] = arithmetic(expression)
        cbm = int(re.search(r"^CBM_ARRAYS_END = (\d+);", bar, re.MULTILINE)[1])
        cols = int(re.search(r"^CAP_MAX_COLS = (\d+);", capture, re.MULTILINE)[1])
        loop_source = (SRC / "bloomscope_loop.jsfx-inc").read_text()
        for name in ("LOOP_QUEUE_CAPACITY", "LOOP_QUEUE_FIELDS"):
            expression = re.search(rf"^{name} = ([^;]+);", loop_source, re.MULTILINE)[1]
            values[name] = arithmetic(expression)
        values["base"] = cbm + 12 + 3 * cols + values["LOOP_QUEUE_CAPACITY"] * values["LOOP_QUEUE_FIELDS"]
        body = midi.split("function midi_init(base)", 1)[1].split("midi_ready =", 1)[0]
        starts = []
        for name, expression in re.findall(r"(MEM_MIDI_\w+) = ([^;]+);", body):
            values[name] = arithmetic(expression)
            starts.append(values[name])
        expected_sizes = [4096 * 10, 2048, 2048, 256 * 4, 4096 * 8,
                          256 * 4, 4096, 128, 128]
        self.assertEqual([b - a for a, b in zip(starts, starts[1:])], expected_sizes)
        values["MEM_CAPTURE_BASE"] = values["MEM_MIDI_END"]
        values["stride"] = (8388608 - values["MEM_CAPTURE_BASE"]) // 24
        body = capture.split("function capture_init()", 1)[1]
        capture_starts = []
        for name, expression in re.findall(r"(MEM_\w+) = ([^;]+);", body):
            values[name] = arithmetic(expression)
            capture_starts.append(values[name])
        self.assertEqual(capture_starts[0], starts[-1])
        self.assertEqual(capture_starts[-1], starts[-1] + 24 * values["stride"])
        self.assertEqual([b - a for a, b in zip(capture_starts, capture_starts[1:])],
                         [values["stride"]] * 20 + [4 * values["stride"]])
        self.assertLessEqual(capture_starts[-1], 8388608)

    def test_snapshot_rejects_mutable_note_writes_and_lifecycle_changes(self):
        def valid(midi_before, midi_after, epoch_before, epoch_after):
            return midi_before % 2 == 0 and midi_before == midi_after and epoch_before == epoch_after
        self.assertTrue(valid(4, 4, 7, 7))
        self.assertFalse(valid(5, 5, 7, 7))
        self.assertFalse(valid(4, 6, 7, 7))
        self.assertFalse(valid(4, 4, 7, 8))

    def test_source_drain_package_lifecycle_and_snapshot_order(self):
        main = (SRC / "bloomscope.jsfx").read_text()
        midi = (SRC / "bloomscope_midi.jsfx-inc").read_text()
        capture = (SRC / "bloomscope_capture.jsfx-inc").read_text()
        block = main.split("\n@block\n", 1)[1].split("\n@sample\n", 1)[0]
        receive = block.split("while (midirecv", 1)[1]
        self.assertIn("midisend(midi_offset, midi_msg1, midi_msg2, midi_msg3);", receive)
        self.assertNotIn("break", receive)
        self.assertNotIn("ext_midi_bus =", main + midi)
        self.assertLess(receive.index("midisend("), receive.index("loop_receive("))
        for name in ("bloomscope_midi.jsfx-inc", "bloomscope_notes.jsfx-inc"):
            self.assertIn("//   " + name, main)
            self.assertIn("import " + name, main)
        self.assertIn("type == 144 && vel > 0", midi)
        self.assertIn("type == 144 && vel == 0", midi)
        self.assertIn("midi_reset_data();", capture)
        self.assertIn("cap_boundary = 0;", capture)
        self.assertIn("changed ? atomic_add(cap_lifecycle_epoch, 1)", midi)
        self.assertIn("atomic_get(midi_revision) != rev ? ok = 0", midi)
        self.assertLess(main.index("frame_ok = snapshot_capture()"), main.index("frame_ok = snapshot_midi()"))
        self.assertIn("atomic_get(cap_lifecycle_epoch) != frame_epoch ? frame_ok = 0", main)
        self.assertIn("MEM_CAPTURE_BASE = MEM_MIDI_END", main)

    def test_source_shared_strip_guides_labels_and_audio_space(self):
        main = (SRC / "bloomscope.jsfx").read_text()
        layout = (SRC / "bloomscope_layout.jsfx-inc").read_text()
        notes = (SRC / "bloomscope_notes.jsfx-inc").read_text()
        self.assertIn("g_midi_visible > 0 ? MIDI_STRIP_HEADING", layout)
        self.assertIn("bottom - top - g_midi_h", layout)
        self.assertIn("g_time_y = g_plot_y + g_plot_h + 2", layout)
        self.assertIn("g_midi_y = g_time_y + TIME_AXIS_HEIGHT", layout)
        self.assertIn("dense || capped ? (", notes)
        self.assertNotIn("gfx_line(g_plot_x, g_midi_y, g_plot_x + g_plot_w, g_midi_y)", notes)
        self.assertIn("g_panels * PANEL_MIN_H + (g_panels - 1) * PANEL_GAP", layout)
        self.assertIn("rows = min(MIDI_STRIP_MAX_ROWS, max(4,", layout)
        self.assertIn("floor((bottom - top - audio_min_h - MIDI_STRIP_HEADING) / MIDI_STRIP_ROW)", layout)
        self.assertIn("MIDI_STRIP_ROW * min(g_midi_pitches, rows)", layout)
        self.assertIn("draw_notes();", main)
        self.assertLess(main.index("prepare_notes();"), main.index("calculate_layout();", main.index("prepare_notes();")))
        self.assertIn("loop(g_panels,", notes)
        self.assertIn("draw_note_guide(note_field(k, 0), 0, target - g_note_marker_h)", notes)
        self.assertIn("draw_note_guide(note_field(k, 1), 1, target + g_note_marker_h - 1)", notes)
        self.assertIn('gfx_setfont(1, "Arial", 16)', notes)
        self.assertIn("row_h >= max(18, label_h)", notes)
        self.assertNotIn('"%s ch%d v%d"', notes)
        self.assertIn("g_note_hover = k + 1", notes)
        self.assertIn("dense rows (labels omitted)", notes)
        self.assertIn("lx >= label_end + 4", notes)
        self.assertNotRegex(notes, r"slider\d+\s*=(?!=)")

    def test_all_package_source_lines_and_sections(self):
        for path in SRC.glob("*.jsfx*"):
            text = path.read_text()
            for line_number, line in enumerate(text.splitlines(), 1):
                self.assertLessEqual(len(line), 200, f"{path.name}:{line_number}")
            if path.suffix == ".jsfx-inc":
                self.assertIn("@init", text)
                function = re.search(r"^function ", text, re.MULTILINE)
                self.assertIsNotNone(function)
                self.assertLess(text.index("@init"), function.start())


class BloomScopeMidiLayoutTests(unittest.TestCase):
    def test_layout_source_constants_and_audio_reserve_precede_strip_allocation(self):
        layout = (SRC / "bloomscope_layout.jsfx-inc").read_text()
        for name, expected in (("MIDI_STRIP_HEADING", 18), ("MIDI_STRIP_ROW", 22),
                               ("MIDI_STRIP_MAX_ROWS", 8), ("PANEL_MIN_H", 40),
                               ("PANEL_GAP", 6), ("CTRL_BAR_TOP", 6),
                               ("CTRL_BAR_HEIGHT", 24), ("CTRL_BAR_GAP", 8),
                               ("STATUS_TEXT_MARGIN", 24), ("TIME_AXIS_HEIGHT", 17)):
            actual = re.search(rf"^{name} = (\d+);", layout, re.MULTILINE)[1]
            self.assertEqual(int(actual), expected, name)
        body = layout.split("function calculate_layout()", 1)[1]
        self.assertLess(body.index("g_panels ="), body.index("audio_min_h ="))
        self.assertLess(body.index("audio_min_h ="), body.index("rows ="))
        self.assertLess(body.index("rows ="), body.index("g_midi_h ="))
        self.assertIn("short_notes = g_midi_visible > 0 && h < audio_min_h", body)
        self.assertIn("short_notes ? ( g_midi_h = 0; h = bottom - top; );", body)
        self.assertIn("g_panels_fit = !short_notes", body)

    def test_eight_pitch_window_height_to_budget_and_row_height(self):
        # (gfx height, single-panel rows/row_h, Split rows/row_h).
        table = ((200, 0, 0, 0, 0), (225, 4, 11, 0, 0),
                 (247, 5, 13.75, 0, 0), (269, 6, 16.5, 0, 0),
                 (271, 6, 16.5, 4, 11), (291, 7, 19.25, 4, 11),
                 (293, 7, 19.25, 5, 13.75), (313, 8, 22, 5, 13.75),
                 (315, 8, 22, 6, 16.5), (337, 8, 22, 7, 19.25),
                 (359, 8, 22, 8, 22), (420, 8, 22, 8, 22))
        for height, single_rows, single_h, split_rows, split_h in table:
            for view in (0, 1, 2):
                layout = midi_strip_layout(height, 8, view)
                expected = (split_rows, split_h) if view == 2 else (single_rows, single_h)
                self.assertEqual((layout.strip_rows, layout.row_h), expected, (height, view))
                self.assertEqual(layout.panels_fit, expected[0] > 0)

    def test_extra_row_thresholds_and_label_threshold_are_exact(self):
        for view, reserve in ((0, 40), (1, 40), (2, 86)):
            for rows in range(5, 9):
                threshold = 79 + reserve + 18 + 22 * rows
                self.assertEqual(midi_strip_layout(threshold - 1, 8, view).strip_rows, rows - 1)
                self.assertEqual(midi_strip_layout(threshold, 8, view).strip_rows, rows)
            labels_at = 79 + reserve + 18 + 22 * 7
            self.assertLess(midi_strip_layout(labels_at - 1, 8, view).row_h, 18)
            self.assertGreaterEqual(midi_strip_layout(labels_at, 8, view).row_h, 18)

    def test_resize_hint_reserves_no_invisible_strip_and_still_blocks_note_painting(self):
        for pitches in (1, 8, 128):
            layout = midi_strip_layout(200, pitches, 2)
            self.assertFalse(layout.panels_fit)
            self.assertEqual((layout.strip_rows, layout.strip_h, layout.row_h), (0, 0, 0))
            self.assertEqual((layout.plot_h, layout.panel_h), (121, 57))
        notes = (SRC / "bloomscope_notes.jsfx-inc").read_text()
        plot = (SRC / "bloomscope_plot.jsfx-inc").read_text()
        self.assertIn("g_midi_visible > 0 && g_panels_fit ? (", notes)
        hint = plot.split("g_panels_fit == 0 ? (", 1)[1].split(") : (\n    p = 0;", 1)[0]
        # Hint branch still selected even though releasing the strip restores 57 px panels.
        self.assertIn("draw_split_hint();", hint)
        self.assertNotIn("draw_notes", hint)

    def test_four_row_fallback_and_dense_heading_stay_when_extra_height_is_unavailable(self):
        for view, reserve in ((0, 40), (1, 40), (2, 86)):
            for height in range(79 + reserve + 106, 79 + reserve + 128):
                for pitches in (4, 5, 8, 128):
                    layout = midi_strip_layout(height, pitches, view)
                    self.assertTrue(layout.panels_fit)
                    self.assertEqual(layout.strip_h, 106)
                    self.assertEqual(layout.row_h, 88 / pitches)
                    self.assertEqual(layout.row_h < 18, pitches > 4)
                    heading = note_heading_candidates(layout.row_h < 18, False, pitches)[0]
                    self.assertEqual("dense rows (labels omitted)" in heading, pitches > 4)

    def test_adaptive_strip_respects_panel_minimum_and_eight_row_budget_at_all_sizes(self):
        for view in (0, 1, 2):
            for height in range(1, 801):
                for pitches in (1, 2, 4, 5, 8, 9, 10, 128):
                    layout = midi_strip_layout(height, pitches, view)
                    self.assertLessEqual(layout.row_budget, 8)
                    self.assertLessEqual(layout.strip_rows, min(pitches, 8))
                    self.assertLessEqual(layout.strip_h, 194)
                    if layout.panels_fit:
                        self.assertGreaterEqual(layout.panel_h, 40)
                        self.assertLessEqual(layout.strip_h + layout.plot_h, height - 79)
                        self.assertAlmostEqual(layout.row_h * pitches, layout.strip_h - 18)
                    else:
                        self.assertEqual(layout.strip_h, 0)
        # The cap limits height, not pitch storage: all semitones still share that height.
        self.assertGreaterEqual(midi_strip_layout(420, 9).row_h, 18)
        self.assertLess(midi_strip_layout(420, 10).row_h, 18)
        self.assertEqual(midi_strip_layout(420, 128).row_h, 176 / 128)

    def test_audio_only_b_geometry_and_small_pitch_strip_are_unchanged(self):
        for view in (0, 1, 2):
            for height in range(1, 801):
                audio = midi_strip_layout(height, 0, view, visible=False)
                h = max(height - 79, 40)
                panel_h = max(math.floor((h - 6) / 2), 1) if view == 2 else h
                self.assertEqual((audio.strip_h, audio.plot_h, audio.panel_h), (0, h, panel_h))
                self.assertEqual(audio.panels_fit, view != 2 or panel_h >= 40)
                for pitches in (1, 2, 3, 4):
                    layout = midi_strip_layout(height, pitches, view)
                    if layout.panels_fit:
                        self.assertEqual(layout.strip_h, 18 + 22 * pitches)
                        self.assertEqual(layout.row_h, 22)


class BloomScopeNotePrimitiveTests(unittest.TestCase):
    def assert_primitives_contained(self, primitives, left, top, right, bottom):
        for primitive in primitives:
            x1, y1, x2, y2 = note_primitive_extent(primitive)
            self.assertGreaterEqual(x1, left - 1e-9, primitive)
            self.assertGreaterEqual(y1, top - 1e-9, primitive)
            self.assertLessEqual(x2, right + 1e-9, primitive)
            self.assertLessEqual(y2, bottom + 1e-9, primitive)

    def test_twenty_two_pitch_arrow_extent_at_strip_and_time_boundaries(self):
        layout = midi_strip_layout(420, 22, 2)
        self.assertEqual(layout.row_h, 8)
        midi_y = 38 + layout.plot_h + 2 + 17
        bottom = midi_y + layout.strip_h
        y = math.floor(bottom - layout.row_h * .25)
        self.assertEqual(layout.marker_h, 1)
        for x in (46, 100, 588):
            for off in (False, True):
                primitives = strip_note_marker_primitives(layout, 21, x, 46, 588, off)
                self.assert_primitives_contained(primitives, 46, midi_y + 18, 588, bottom)
                self.assertEqual(len(primitives), 1)
                bounds = note_primitive_extent(primitives[0])
                self.assertEqual(bounds[1], y if off else y - 1)
                self.assertEqual(bounds[3], bounds[1])

    def test_fractional_x_has_equal_mirrored_up_down_pixel_areas(self):
        for height in range(1, 9):
            for x in (46, 46.0625, 46.5, 100.25, 587.9375, 588):
                up = note_arrow_primitives(x, 100, height, 46, 588, False)
                down = note_arrow_primitives(x, 100, height, 46, 588, True)
                self.assertEqual(len(up), height)
                self.assertEqual(len(down), height)
                self.assertEqual(sum(p[3] * p[4] for p in up), sum(p[3] * p[4] for p in down))
                for a, b in zip(up, down):
                    self.assertEqual((a[1], a[3], a[4]), (b[1], b[3], b[4]))
                    self.assertEqual(a[2] + b[2], 200)
                    self.assertLessEqual(abs(math.floor(x + .5) - x), .5)

    def test_arrow_extents_across_all_row_budgets(self):
        for view in (0, 1, 2):
            for height in (200, 225, 247, 269, 271, 291, 293, 313, 315, 337, 359, 420, 662):
                for pitches in (1, 8, 22, 128):
                    layout = midi_strip_layout(height, pitches, view)
                    midi_y = 38 + layout.plot_h + 2 + 17
                    for row in range(pitches):
                        for width in (40, 542, 1092):
                            left, right = 46, 46 + width
                            for x in (left, left + .5, (left + right) / 2, right - .5, right):
                                for off in (False, True):
                                    primitives = strip_note_marker_primitives(layout, row, x, left, right, off)
                                    if not layout.panels_fit:
                                        self.assertEqual(primitives, [])
                                    else:
                                        self.assert_primitives_contained(primitives, left, midi_y + 18,
                                                                         right, midi_y + layout.strip_h)

    def test_dense_first_and_last_row_primitive_extents_for_every_pitch_count(self):
        for height in (271, 337, 420):
            for pitches in range(1, 129):
                layout = midi_strip_layout(height, pitches, 2)
                midi_y = 38 + layout.plot_h + 2 + 17
                for row in (0, pitches - 1):
                    for x in (46, 46.125, 66, 85.875, 86):
                        for off in (False, True):
                            primitives = strip_note_marker_primitives(layout, row, x, 46, 86, off)
                            self.assert_primitives_contained(primitives, 46, midi_y + 18,
                                                             86, midi_y + layout.strip_h)
        # There is no whole-pixel room at extreme density: omit both heads,
        # rather than fabricate unequal glyphs or paint into neighboring rows.
        layout = midi_strip_layout(420, 128)
        self.assertEqual(layout.marker_h, 0)
        for off in (False, True):
            self.assertEqual(strip_note_marker_primitives(layout, 127, 100, 46, 588, off), [])

    def test_note_on_above_and_note_off_below_bar_within_each_pitch_row(self):
        for pitches in (1, 8, 22, 128):
            layout = midi_strip_layout(420, pitches, 2)
            for row in range(pitches):
                top = 38 + layout.plot_h + 2 + 17 + 18 + row * layout.row_h
                bar = math.floor(top + layout.row_h * .75)
                for off in (False, True):
                    primitives = strip_note_marker_primitives(layout, row, 100, 46, 588, off)
                    lo, hi = (bar, top + layout.row_h) if off else (top, bar)
                    self.assert_primitives_contained(primitives, 46, lo, 588, hi)
                    bounds = [note_primitive_extent(p) for p in primitives]
                    if bounds:
                        self.assertEqual(min(b[1] for b in bounds) if off else max(b[3] for b in bounds),
                                         bar if off else bar - 1)

    def test_boundary_clipping_keeps_nearest_pixel_apex_and_no_stem(self):
        left, right, bar, height = 46, 86, 100, 5
        for x in (left, left + .5, 66, right - .5, right):
            for off in (False, True):
                primitives = note_arrow_primitives(x, bar, height, left, right, off)
                self.assert_primitives_contained(primitives, left, bar - height, right, bar + height)
                apex = primitives[-1]
                self.assertEqual(apex[1], math.floor(x + .5))
                self.assertEqual(apex[3:], (1, 1))
                self.assertEqual(apex[2], bar + height if off else bar - height)
        self.assertEqual(note_arrow_primitives(66, bar, 0, left, right), [])

    def test_audio_guide_endpoint_marker_primitives_are_clipped_in_each_panel(self):
        for view in (0, 1, 2):
            layout = midi_strip_layout(420, 22, view)
            for panel in range(2 if view == 2 else 1):
                top = 38 + panel * (layout.panel_h + 6)
                bottom = top + layout.panel_h
                for x in (46, 46.5, 317, 587.5, 588):
                    for off in (False, True):
                        base = bottom - 1 - layout.marker_h if off else top + 1 + layout.marker_h
                        primitives = note_arrow_primitives(x, base, layout.marker_h, 46, 588, off)
                        self.assert_primitives_contained(primitives, 46, top, 588, bottom)
                        strip = note_arrow_primitives(x, 100, layout.marker_h, 46, 588, off)
                        self.assertEqual([(p[1], p[3:]) for p in primitives],
                                         [(p[1], p[3:]) for p in strip])

    def test_source_uses_contained_primitives_without_changing_timestamp_coordinates(self):
        notes = (SRC / "bloomscope_notes.jsfx-inc").read_text()
        arrow = notes.split("function draw_note_arrow(", 1)[1].split("function draw_guide_line(", 1)[0]
        self.assertIn("cx = floor(x + 0.5)", arrow)
        self.assertIn("half = height - 1 - i", arrow)
        self.assertIn("py = off ? base_y + 1 + i : base_y - 1 - i", arrow)
        self.assertIn("gfx_rect(left, py, right - left + 1, 1)", arrow)
        self.assertNotRegex(arrow, r"(?m)^\s*x\s*=")
        self.assertNotIn("gfx_circle(", notes)
        self.assertIn("g_note_marker_h = 8", notes)
        self.assertIn("floor(ly + row_h) - 1 - y", notes)
        self.assertIn("draw_note_arrow(x1, y, g_note_marker_h, 0)", notes)
        self.assertIn("draw_note_arrow(x2, y - 1, g_note_marker_h, 1)", notes)
        self.assertIn("draw_note_plot_head(on, 0, g_note_marker_h)", notes)
        self.assertIn("draw_note_arrow(x, base, height, off)", notes)


class BloomScopeJointTests(unittest.TestCase):
    def history_through_one_second(self):
        j = BloomScopeJointModel()
        # Exact review timestamps; host integer-offset recipe uses samples 24003/24005.
        # Realistic block partition matters: a one-second block gives B a 0.5005 s
        # continuity tolerance, so a 0.5 s seek would not be recognized as a gap.
        schedule = [on(.50005 * 48000), off(.50010 * 48000)]
        for sample in range(0, 48000, 512):
            length = min(512, 48000 - sample)
            events = [(offset - sample, msg1, msg2, msg3)
                      for offset, msg1, msg2, msg3 in schedule if sample <= offset < sample + length]
            j.block(sample / 48000, length, events, reset=False)
        return j

    def test_frozen_drain_accepts_every_interleaved_frame_and_passes_every_event(self):
        j = BloomScopeJointModel()
        j.block(0, 32, [on()], reset=False)
        baseline = j.frame()
        events = [off(), on(1, pitch=64), (2, 0xB0, 11, 99), (3, 0xE1, 0, 64)]
        frames = []
        revision = j.revision
        for position, state in ((32 / 48000, 1), (0, 0), (8, 1)):
            j.block(position, 512, events, state=state, freeze=True,
                    during_drain=lambda model: frames.append(model.frame()))
        self.assertEqual(frames, [baseline] * 12)
        self.assertEqual(j.revision, revision)
        self.assertEqual(j.output[-12:], events * 3)
        self.assertEqual(j.frame(), baseline)

    def test_idle_stopped_drain_does_not_open_seqlock(self):
        j = BloomScopeJointModel()
        frames = []
        j.block(0, 512, [on(), off()], state=0,
                during_drain=lambda model: frames.append(model.frame()))
        self.assertTrue(all(frame is not None for frame in frames))
        self.assertEqual(j.revision, 0)
        self.assertEqual(j.output, [on(), off()])

    def test_mutating_drain_and_stop_cleanup_still_reject_interleaved_frames(self):
        j = BloomScopeJointModel()
        frames = []
        j.block(0, 32, [on(), on(2, pitch=64)], reset=False,
                during_drain=lambda model: frames.append(model.frame()))
        self.assertEqual(frames, [None, None])
        self.assertIsNotNone(j.frame())
        j.block(32 / 48000, 32, [off()], state=0,
                during_drain=lambda model: frames.append(model.frame()))
        self.assertIsNone(frames[-1])
        self.assertEqual(j.frame()[1][0].kind, 2)

    def test_eight_sample_backward_seek_then_freeze_preserves_joint_history(self):
        j = self.history_through_one_second()
        baseline = j.frame()
        self.assertEqual(len(baseline[1]), 1)
        j.block(.5, 8, [on(1, pitch=64)], reset=False)
        self.assertEqual(j.partial, 8)
        self.assertEqual(j.segments[-1][3], 0)
        # The original time-only ownership path hides the old note prematurely.
        legacy_visible = visible_notes(j.held(), j.segments, j.audio_now, 2)
        self.assertEqual([r.pitch for r in legacy_visible], [64])
        after_seek = j.frame()
        self.assertEqual(after_seek, baseline)
        self.assertLess(after_seek[0].segment, j.segment_id)
        frames = []
        j.block(.5 + 8 / 48000, 512, [off(0, pitch=64)], freeze=True,
                during_drain=lambda model: frames.append(model.frame()))
        self.assertEqual(j.frame(), baseline)
        self.assertEqual(frames, [baseline])
        self.assertEqual(j.partial, 0)

    def test_first_post_seek_hop_publishes_ownership_and_pending_notes_together(self):
        j = self.history_through_one_second()
        j.block(.5, 8, [on(1, pitch=64)], reset=False)
        self.assertEqual([r.pitch for r in j.frame()[1]], [60])
        previous_written = j.audio_written
        j.block(.5 + 8 / 48000, 24, reset=False)
        audio, visible = j.frame()
        self.assertEqual(audio.written, previous_written + 1)
        self.assertEqual(j.segments[-1][3], audio.written)
        self.assertEqual(audio.segment, j.segment_id)
        self.assertAlmostEqual(audio.now, .5 + 32 / 48000)
        self.assertTrue(audio.points[-1][2])
        self.assertEqual([r.pitch for r in visible], [64])

    def test_never_completed_intermediate_segment_cannot_gain_ownership_later(self):
        j = self.history_through_one_second()
        j.block(.5, 8, [on(1, pitch=64)], reset=False)
        pending = j.segment_id
        j.block(2, 32, reset=False)
        audio, visible = j.frame(window=3)
        self.assertGreater(audio.segment, pending)
        self.assertEqual(j.segments[-2][3], 0)
        self.assertEqual([r.pitch for r in visible], [60])

    def test_copy_before_first_hop_remains_old_joint_frame_when_hop_publishes_during_copy(self):
        j = self.history_through_one_second()
        baseline = j.frame()
        j.block(.5, 8, [on(1, pitch=64)], reset=False)
        j.block(.5 + 8 / 48000, 24, reset=False, process_samples=False)
        old_frame = j.frame(after_audio=lambda: j.samples(24))
        self.assertEqual(old_frame, baseline)
        self.assertEqual([r.pitch for r in j.frame()[1]], [64])

    def test_seek_during_joint_copy_rejects_frame_then_stable_pending_frame_is_valid(self):
        j = self.history_through_one_second()
        baseline = j.frame()
        self.assertIsNone(j.frame(after_audio=lambda: j.block(.5, 8, reset=False)))
        self.assertEqual(j.frame(), baseline)

    def test_midi_mutation_during_copy_rejects_snapshot_not_torn_fields(self):
        j = BloomScopeJointModel()
        j.block(0, 32, [on()], reset=False)
        baseline = j.frame()
        self.assertIsNone(j.frame(during_midi_copy=lambda: j.block(32 / 48000, 32, [off(1)], reset=False)))
        self.assertEqual(baseline[1][0].kind, 0)
        self.assertEqual(j.frame()[1][0].kind, 1)

    def test_startup_pending_notes_need_a_hop_and_clear_rate_do_not_reuse_tickets(self):
        j = BloomScopeJointModel()
        j.block(0, 8, [on()], reset=False)
        self.assertEqual(j.frame()[0].segment, 0)
        self.assertEqual(j.frame()[1], [])
        j.block(8 / 48000, 24, reset=False)
        initial = j.frame()[0]
        self.assertEqual(len(j.frame()[1]), 1)
        for action in ({"clear": True}, {"rate": 96000}):
            j.block(0, 8, freeze=True, **action)
            self.assertEqual(j.frame()[1], [])
            self.assertEqual(j.frame()[0].segment, 0)
            j.block(0, 32, [on()], reset=False)
            current = j.frame()[0]
            self.assertGreater(current.written, initial.written)
            self.assertGreater(current.segment, initial.segment)
            self.assertEqual(len(j.frame()[1]), 1)
            initial = current

    def test_heading_tiers_preserve_dense_and_capped_flags_at_narrow_widths(self):
        def measure(text):
            # Synthetic proportional-font model, not a host font measurement.
            return sum(7 if ch in "MW" else 3 if ch in "il " else 6 for ch in text)
        for dense, capped in ((False, False), (True, False), (False, True), (True, True)):
            for width in (40, 48, 75, 100, 150, 220, 350, 600):
                for metric in (measure, lambda text: len(text) * 9):
                    text, tier = fit_note_heading(dense, capped, 128, width, metric)
                    self.assertTrue(text)
                    self.assertLessEqual(tier, 3)
                    self.assertLessEqual(metric(text), width - 8)
                    self.assertEqual("dense" in text or text in ("D", "D/C"), dense)
                    self.assertEqual("capped" in text or text in ("C", "D/C"), capped)
        self.assertEqual(fit_note_heading(True, True, 128, 40, measure), ("D/C", 3))
        self.assertEqual(fit_note_heading(True, True, 128, 100, measure)[1], 2)
        self.assertEqual(fit_note_heading(True, True, 128, 220, measure)[1], 1)
        self.assertEqual(fit_note_heading(True, True, 128, 600, measure)[1], 0)

    def test_source_bridges_freeze_guard_audio_publication_and_heading_tiers(self):
        main = (SRC / "bloomscope.jsfx").read_text()
        midi = (SRC / "bloomscope_midi.jsfx-inc").read_text()
        capture = (SRC / "bloomscope_capture.jsfx-inc").read_text()
        plot = (SRC / "bloomscope_plot.jsfx-inc").read_text()
        notes = (SRC / "bloomscope_notes.jsfx-inc").read_text()
        block = main.split("\n@block\n", 1)[1].split("\n@sample\n", 1)[0]
        self.assertIn("midi_writing = !cap_freeze &&", block)
        self.assertIn("midi_writing ? (\n  atomic_add(midi_revision, 1);\n  midi_block();", block)
        self.assertIn("midi_writing ? atomic_add(midi_revision, 1);", block)
        self.assertIn("midi_writing ? loop_receive(", block)
        self.assertIn("midi_publish_audio_hop(cap_written);", capture)
        self.assertIn("cap_now_segment = midi_segment_id;", capture)
        self.assertNotIn("cap_now_segment =", capture.split("function capture_block()", 1)[1])
        self.assertIn("segment = cap_now_segment;", plot)
        self.assertIn("snap_audio_segment = segment;", plot)
        self.assertIn("snap_written = written;", plot)
        self.assertIn("note_segment(k, 0) <= snap_audio_segment", midi)
        self.assertIn("note_segment(k, 3) > 0", midi)
        self.assertIn("note_segment(k, 3) <= snap_written", midi)
        self.assertIn("note_segment_published(s) ? (", midi)
        self.assertIn("mem[r + 3] = 0;", midi)
        self.assertIn("mem[r + 3] = ticket;", midi)
        for candidates in (note_heading_candidates(True, True, 128)[1:],
                           note_heading_candidates(True, False, 128)[1:],
                           note_heading_candidates(False, True, 128)[1:]):
            for text in candidates:
                self.assertIn(f'"{text}"', notes)
        self.assertIn("while (tw > avail && tier < 3)", notes)
        self.assertIn("draw_note_heading(row_h < max(18, label_h), snap_midi_dropped > 0);", notes)
        self.assertNotIn("tw <= g_plot_w ? (", notes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
