#!/usr/bin/env python3
"""Offline model of BloomScope's arithmetic, and the tests that pin it down.

Why a Python model at all: these offline tests do not compile JSFX or start
REAPER, and source inspection is not proof of compilation. What
CAN be proven offline is the arithmetic and the state machine -- the hop
counter, the ring index, the dB axis, the gap rule and the definitions of the
per-note metrics -- so those are mirrored here, asserted, and only then
transcribed into EEL2. Where the model and the EEL2 disagree later, the EEL2 is
wrong until it is shown otherwise.

Run from the repository root:
    python3 tests/bloomscope/test_bloomscope_math.py  (stdlib only, no REAPER)
The isolated-note metric formulas are experimental models, not shipped features.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Constants mirrored from src/bloomscope_capture.jsfx-inc and the layout module
# ---------------------------------------------------------------------------

HOP = 32
MAX_WINDOW = 30.0
MAX_COLS = 2048
FLOOR_DB = -60.0
FLOAT_EPS = 1e-9


# ---------------------------------------------------------------------------
# The dB axis (src/bloomscope_layout.jsfx-inc)
# ---------------------------------------------------------------------------

def db_of_amp(amplitude: float) -> float:
    """Linear amplitude -> dBFS, with the log10 guard of the plugin."""
    value = max(amplitude, FLOAT_EPS)
    return 20.0 * math.log10(value)


def y_of_db(db: float, floor_db: float, y0: float, height: float) -> float:
    """dBFS -> pixel y. 0 dB is the top edge, the floor the bottom edge."""
    return y0 + (0.0 - db) / (0.0 - floor_db) * height


def db_of_y(y: float, floor_db: float, y0: float, height: float) -> float:
    """Pixel y -> dBFS, the inverse used by the pointer readout."""
    return -((y - y0) / height) * (0.0 - floor_db)


def grid_step(height: float, floor_db: float) -> int:
    """Every how many 6 dB lines a label still fits."""
    per_line = height * 6.0 / (0.0 - floor_db)
    step = 1
    if per_line < 18:
        step = 2
    if per_line * 2 < 18:
        step = 5
    return step


def grid_count(height: float, floor_db: float) -> int:
    step = grid_step(height, floor_db)
    return int(math.floor((0.0 - floor_db) / (6.0 * step))) + 1


def grid_db(i: int, height: float, floor_db: float) -> float:
    return 0.0 - i * 6.0 * grid_step(height, floor_db)


# ---------------------------------------------------------------------------
# The hop counter and the four stored series (src/bloomscope_capture.jsfx-inc)
# ---------------------------------------------------------------------------
# Revision 4 stores L and R separately and derives the view at draw time
# Both channels are measured. There is no channel mode: the detector always
# measures both channels, so a view change never needs a re-measurement.

def channel_point(left: float, right: float) -> tuple[float, float, float, float]:
    """Peak and squared-energy contribution of one sample, per channel."""
    return abs(left), left * left, abs(right), right * right


def envelope_points(samples, blocks, hop: int = HOP):
    """The series a block-partitioned plugin stores: [(lpk,lrms,rpk,rrms), ...].

    State lives across blocks on purpose: this is what makes the measurement
    independent of the audio buffer size.
    """
    acc_lpk = acc_rpk = 0.0
    acc_lsq = acc_rsq = 0.0
    count = 0
    pos = 0
    out: list[tuple[float, float, float, float]] = []

    for length in blocks:
        for _ in range(length):
            left, right = samples[pos]
            pos += 1
            lpk, lsq, rpk, rsq = channel_point(left, right)
            acc_lpk = max(acc_lpk, lpk)
            acc_rpk = max(acc_rpk, rpk)
            acc_lsq += lsq
            acc_rsq += rsq
            count += 1
            if count >= hop:
                out.append((acc_lpk, math.sqrt(acc_lsq / count),
                            acc_rpk, math.sqrt(acc_rsq / count)))
                acc_lpk = acc_rpk = 0.0
                acc_lsq = acc_rsq = 0.0
                count = 0

    return out


# ---------------------------------------------------------------------------
# The three presentation modes - pure functions of a point
# ---------------------------------------------------------------------------

VIEW_STEREO, VIEW_OVERLAY, VIEW_SPLIT = 0, 1, 2


def linked_point(point) -> tuple[float, float]:
    """Stereo: one linked reading. Not a fold-down, so it cannot cancel."""
    lpk, lrms, rpk, rrms = point
    return max(lpk, rpk), math.sqrt((lrms * lrms + rrms * rrms) * 0.5)


def channel_series(points, channel: int):
    """Overlay and Split read the channels separately: 0 = L, 1 = R."""
    return [(p[0], p[1]) if channel == 0 else (p[2], p[3]) for p in points]


def window_coincides(points, tolerance_db: float = 0.05):
    """Both detector series must coincide at every visible hop."""
    return all(abs(db_of_amp(lpk) - db_of_amp(rpk)) < tolerance_db
               and abs(db_of_amp(lrms) - db_of_amp(rrms)) < tolerance_db
               for lpk, lrms, rpk, rrms in points)


def channels_coincide_db(point, tolerance_db: float = 0.05):
    """The §6.3 announcement: None when L=R, the difference in dB otherwise."""
    lpk, _, rpk, _ = point
    if lpk == 0.0 and rpk == 0.0:
        return None
    difference = db_of_amp(lpk) - db_of_amp(rpk)
    return None if abs(difference) < tolerance_db else difference


# ---------------------------------------------------------------------------
# The ring (src/bloomscope_capture.jsfx-inc)
# ---------------------------------------------------------------------------

def ring_index(k: int, head: int, n: int, capacity: int) -> int:
    i = head - n + k
    if i < 0:
        i += capacity
    if i >= capacity:
        i -= capacity
    return i


def ring_after_pushes(count: int, capacity: int) -> tuple[list[int], int, int]:
    """Pushes 0..count-1 into a ring; returns (memory, head, held)."""
    memory = [-1] * capacity
    head = 0
    held = 0
    for label in range(count):
        memory[head] = label
        head = (head + 1) % capacity
        held = min(held + 1, capacity)
    return memory, head, held


# ---------------------------------------------------------------------------
# The gap rule (the mirror of capture_block)
# ---------------------------------------------------------------------------

def break_flags(positions, states, samplesblock: int, srate: float) -> list[int]:
    """1 where the block starts a new segment, 0 where it continues the line."""
    out: list[int] = []
    prev_position = 0.0
    prev_state = -1

    for position, state in zip(positions, states):
        flag = 0
        if state == 1:
            if prev_state == 1:
                expected = prev_position + samplesblock / srate
                tolerance = 0.5 * samplesblock / srate + 0.0005
                if abs(position - expected) > tolerance:
                    flag = 1
            else:
                flag = 1
        else:
            flag = 1
        out.append(flag)
        prev_state = state
        prev_position = position

    return out


# ---------------------------------------------------------------------------
# Experimental isolated-note metrics - arithmetic models, not plugin features
# ---------------------------------------------------------------------------

def note_metrics(amplitude, t0: float, hop_dt: float, note_on: float, note_off: float,
                 floor_db: float = FLOOR_DB):
    """Measure one note on a hop series.

    amplitude[i] is the level at t0 + i*hop_dt. Returns a dict; a missing
    measurement is None, never a fabricated zero.
    """
    onset_floor = 10.0 ** ((floor_db + 6.0) / 20.0)
    i_on = max(0, int(round((note_on - t0) / hop_dt)))
    i_off = min(len(amplitude) - 1, int(round((note_off - t0) / hop_dt)))

    window = amplitude[i_on:i_off + 1]
    if not window:
        return {"onset_ms": None, "to_peak_ms": None, "attack_10_90_ms": None,
                "release_ms": None, "peak_db": None}

    peak = max(window)
    i_peak = i_on + window.index(peak)
    onset_threshold = max(onset_floor, peak * 0.1)

    onset = None
    for i in range(i_on, i_peak + 1):
        if amplitude[i] > onset_threshold:
            onset = i
            break

    attack = None
    first_10 = None
    first_90 = None
    for i in range(i_on, i_peak + 1):
        if first_10 is None and amplitude[i] > peak * 0.1:
            first_10 = i
        if first_90 is None and amplitude[i] > peak * 0.9:
            first_90 = i
    if first_10 is not None and first_90 is not None:
        attack = (first_90 - first_10) * hop_dt * 1000.0

    sustain = amplitude[i_off]
    release_threshold = max(onset_floor, sustain * 10.0 ** (-40.0 / 20.0))
    release = None
    below = 0
    for i in range(i_off, len(amplitude)):
        if amplitude[i] < release_threshold:
            below += 1
            if below >= 3:
                release = (i - 2 - i_off) * hop_dt * 1000.0
                break
        else:
            below = 0

    return {
        "onset_ms": None if onset is None else (onset - i_on) * hop_dt * 1000.0,
        "to_peak_ms": (i_peak - i_on) * hop_dt * 1000.0,
        "attack_10_90_ms": attack,
        "release_ms": release,
        "peak_db": db_of_amp(peak),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_db_axis_is_one_sided_and_round_trips():
    for floor_db in (-96.0, -60.0, -24.0):
        top = y_of_db(0.0, floor_db, 30.0, 200.0)
        bottom = y_of_db(floor_db, floor_db, 30.0, 200.0)
        assert abs(top - 30.0) < 1e-9, "0 dBFS must sit on the top edge"
        assert abs(bottom - 230.0) < 1e-9, "the floor must sit on the bottom edge"
        for db in (0.0, -6.0, -18.4, floor_db):
            y = y_of_db(db, floor_db, 30.0, 200.0)
            assert abs(db_of_y(y, floor_db, 30.0, 200.0) - db) < 1e-9
            assert 30.0 - 1e-9 <= y <= 230.0 + 1e-9, "the axis never leaves the panel"


def test_db_of_amp_never_logs_zero():
    assert db_of_amp(0.0) == db_of_amp(FLOAT_EPS)
    assert abs(db_of_amp(1.0)) < 1e-12
    assert abs(db_of_amp(0.5) + 6.020599913279624) < 1e-9
    assert db_of_amp(2.0) > 0.0, "above full scale is a fact, not an error"


def test_grid_labels_stay_above_the_floor():
    for floor_db in (-96.0, -60.0, -24.0):
        for height in (40.0, 120.0, 400.0, 1200.0):
            step = grid_step(height, floor_db)
            count = grid_count(height, floor_db)
            assert count >= 1
            for i in range(count):
                db = grid_db(i, height, floor_db)
                assert db <= 0.0
                assert db >= floor_db - 1e-9, "a label below the floor cannot be drawn"
            if floor_db == -60.0:
                assert grid_db(0, height, floor_db) == 0.0
                assert abs(grid_db(count - 1, height, floor_db) - (-60.0)) < 6.0 * step


def test_the_hop_counter_ignores_the_block_partition():
    srate = 48000
    samples = []
    for i in range(5000):
        phase = 2.0 * math.pi * 1000.0 * i / srate
        left = 0.5 * math.sin(phase)
        right = 0.25 * math.sin(phase * 0.5)
        if i % 700 < 3:            # a couple of transients, so peak means something
            left = 0.99
        samples.append((left, right))

    whole = envelope_points(samples, [len(samples)])
    at_128 = envelope_points(samples, [128] * (len(samples) // 128) + [len(samples) % 128])
    at_1024 = envelope_points(samples, [1024] * (len(samples) // 1024) + [len(samples) % 1024])

    assert whole and whole == at_128 and whole == at_1024, (
        "the series must not depend on how the audio arrives"
    )
    assert len(whole) == len(samples) // HOP, "one point per hop, none lost"


def test_the_four_series_are_finite_and_the_linked_point_cannot_cancel():
    samples = [(0.5, -0.25), (0.0, 0.0), (1.0, 1.0), (-0.125, 0.75)]
    points = envelope_points(samples * 64, [len(samples) * 64])
    assert points
    for point in points:
        for value in point:
            assert value >= 0.0
        peak, rms = linked_point(point)
        assert rms <= peak + 1e-12, "the linked rms cannot exceed the linked peak"
        assert peak >= point[0] and peak >= point[2], "linked peak is the louder channel"


def test_antiphase_material_is_not_cancelled_by_the_linked_reading():
    samples = [(0.5, -0.5)] * HOP
    ((lpk, lrms, rpk, rrms),) = envelope_points(samples, [HOP])
    peak, rms = linked_point((lpk, lrms, rpk, rrms))
    assert abs(peak - 0.5) < 1e-12 and abs(rms - 0.5) < 1e-12, (
        "a mono fold-down would read zero here; the linked reading must not"
    )


def test_split_keeps_channel_identity():
    samples = [(0.5, 0.0)] * HOP
    ((lpk, _, rpk, _),) = envelope_points(samples, [HOP])
    assert abs(lpk - 0.5) < 1e-12 and rpk == 0.0
    left = channel_series([(lpk, 0.0, rpk, 0.0)], 0)
    right = channel_series([(lpk, 0.0, rpk, 0.0)], 1)
    assert left == [(0.5, 0.0)] and right == [(0.0, 0.0)], (
        "each panel reads its own channel, never the linked value"
    )


def test_window_coincidence_checks_history_and_both_detectors():
    same = (0.5, 0.25, 0.5, 0.25)
    different_rms = (0.5, 0.25, 0.5, 0.125)
    assert window_coincides([same, same])
    assert not window_coincides([different_rms, same])


def test_the_mono_announcement_follows_the_newest_hop():
    same = (0.25, 0.125, 0.25, 0.125)
    assert channels_coincide_db(same) is None, "identical envelopes read as L=R"
    louder_left = (0.5, 0.25, 0.25, 0.125)
    difference = channels_coincide_db(louder_left)
    assert difference is not None and abs(difference - 6.0206) < 0.001
    assert channels_coincide_db((0.0, 0.0, 0.0, 0.0)) is None, "silence is not a channel difference"


def test_ring_returns_the_oldest_first_across_the_wrap():
    capacity = 10
    memory, head, held = ring_after_pushes(25, capacity)
    assert held == capacity
    labels = [memory[ring_index(k, head, held, capacity)] for k in range(held)]
    assert labels == list(range(15, 25)), "k = 0 is the oldest point held"
    for k in range(held - 1):
        assert labels[k] < labels[k + 1]


def test_a_steady_transport_has_no_break_after_the_first_point():
    srate = 48000.0
    block = 512
    positions = [i * block / srate for i in range(20)]
    flags = break_flags(positions, [1] * 20, block, srate)
    assert flags[0] == 1, "the first point always starts a segment"
    assert all(f == 0 for f in flags[1:]), "contiguous playback must not break the line"


def test_a_locate_breaks_the_line():
    srate = 48000.0
    block = 512
    positions = [i * block / srate for i in range(10)]
    positions += [20.0 + i * block / srate for i in range(5)]     # a jump forward
    flags = break_flags(positions, [1] * 15, block, srate)
    assert flags[10] == 1, "the first block after a locate starts a segment"
    assert sum(flags) == 2


def test_a_dropped_block_is_a_break_but_a_one_sample_jitter_is_not():
    srate = 48000.0
    block = 512
    step = block / srate

    # One block never arrives: the position advances by two blocks.
    positions = [0.0, step, 3 * step, 4 * step]
    assert break_flags(positions, [1] * 4, block, srate)[2] == 1

    # Normal quantization noise of a few samples.
    jitter = 3.0 / srate
    positions = [0.0, step + jitter, 2 * step, 3 * step - jitter]
    assert all(f == 0 for f in break_flags(positions, [1] * 4, block, srate)[1:])


def test_stop_and_restart_break_the_line():
    srate = 48000.0
    block = 512
    positions = [0.0, 0.0, 0.0, 5.0, 5.0 + block / srate]
    states = [1, 1, 0, 1, 1]
    flags = break_flags(positions, states, block, srate)
    assert flags[2] == 1, "a stop is a break"
    assert flags[3] == 1, "a restart is a break"
    assert flags[4] == 0


def test_note_metrics_match_a_synthetic_envelope():
    hop_dt = 0.001                     # 1 ms hops, so 1 hop = 1 ms
    amplitude: list[float] = []
    amplitude += [0.0] * 10
    amplitude += [i / 100.0 for i in range(1, 101)]      # linear attack, 100 ms
    amplitude += [1.0] * 200                             # hold
    for i in range(300):                                 # exponential release, tau 50 ms
        amplitude.append(math.exp(-i / 50.0))

    t0 = 0.0
    note_on = 0.010                    # the note starts with the ramp
    note_off = 0.010 + 0.100 + 0.200   # 310 ms

    m = note_metrics(amplitude, t0, hop_dt, note_on, note_off)

    # The ramp reaches 0.1 at index 19 and 1.0 at index 109; the note starts at
    # index 10, so the onset is 9 ms in, the peak 99 ms in, and 10% -> 90% is 80 ms.
    assert abs(m["onset_ms"] - 9.0) <= 2.0, m["onset_ms"]
    assert abs(m["to_peak_ms"] - 99.0) <= 2.0, m["to_peak_ms"]
    assert abs(m["attack_10_90_ms"] - 80.0) <= 3.0, m["attack_10_90_ms"]
    # 1.0 * exp(-k/50) < 0.01  ->  k > 230.2
    assert m["release_ms"] is not None and 228.0 <= m["release_ms"] <= 236.0, m["release_ms"]
    assert abs(m["peak_db"]) < 1e-9


def test_release_ignores_a_momentary_dip_and_respects_the_floor():
    hop_dt = 0.001
    # Note-off at index 40, then a one-hop dip at 45 that must not end the note.
    amplitude = [1.0] * 40 + [1.0] * 5 + [0.0] + [1.0] * 5 + [0.0] * 100
    m = note_metrics(amplitude, 0.0, hop_dt, 0.0, 0.040)
    assert m["release_ms"] is not None
    assert m["release_ms"] > 6.0, "a single dip is not a release"
    assert abs(m["release_ms"] - 11.0) <= 2.0, m["release_ms"]

    # A signal that never falls below its threshold has no release to report.
    quiet = [0.01] * 200
    m2 = note_metrics(quiet, 0.0, hop_dt, 0.0, 0.100, floor_db=-60.0)
    assert m2["peak_db"] < -39.0
    assert m2["release_ms"] is None, "no fall, no release"


def test_moving_average_resets_at_gap_and_uses_finite_window():
    # Mirrors aggregate's rolling sum and segment count, not exponential smoothing.
    values = [1.0, 0.0, 0.0, 0.0, 0.6, 0.0]
    breaks = [True, False, False, False, True, False]
    span = 3
    total = 0.0
    count = 0
    result = []
    for k, value in enumerate(values):
        if breaks[k]:
            total = 0.0
            count = 0
        if count >= span:
            total -= values[k - span]
        else:
            count += 1
        total += value
        result.append(total / count)
    assert result == [1.0, 0.5, 1 / 3, 0.0, 0.6, 0.3]


def test_capture_source_drops_partial_hops_on_discontinuities():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[2] / "bloomscope/bloomscope_capture.jsfx-inc").read_text()
    assert "expected = cap_last_pp + cap_last_block / srate" in source
    assert "abs(play_position - expected) > tol ? capture_drop_hop()" in source
    assert "cap_freeze != cap_prev_freeze ? capture_drop_hop()" in source


def test_detector_visibility_and_resize_hint_status_are_not_stale():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[2] / "bloomscope/bloomscope_plot.jsfx-inc").read_text()
    assert "show_peak = slider4 == 0 || slider4 == 2" in source
    assert "show_rms = slider4 == 1 || slider4 == 2" in source
    hint = source.split("g_panels_fit == 0 ? (", 1)[1].split("draw_split_hint();", 1)[0]
    assert "aggregate(1)" in hint and "aggregate(2)" in hint


class CaptureLifecycleModel:
    """Block-level model of capture_block, including the partial sample hop."""
    def __init__(self, rate=48000):
        self.rate = rate
        self.previous_state = -1
        self.previous_position = 0.0
        self.previous_length = 0
        self.previous_freeze = False
        self.partial = []
        self.break_next = True
        self.points = []

    def drop(self):
        self.partial.clear()
        self.break_next = True

    def block(self, position, length, state=1, freeze=False, reset=True, rate=None, sample=1):
        if rate is not None and rate != self.rate:
            self.rate = rate
            self.points.clear()
            self.drop()
            self.previous_state = -1
            self.previous_freeze = freeze
        if state == 1 and self.rate > 0:
            if self.previous_state == 1:
                expected = self.previous_position + self.previous_length / self.rate
                tolerance = 0.5 * self.previous_length / self.rate + 0.0005
                if abs(position - expected) > tolerance:
                    self.drop()
            else:
                if reset and not freeze:
                    self.points.clear()
                self.drop()
        else:
            self.drop()
        if freeze != self.previous_freeze:
            self.drop()
        self.previous_state = state
        self.previous_position = position
        self.previous_length = length
        self.previous_freeze = freeze
        if state == 1 and not freeze and self.rate > 0:
            for offset in range(1, length + 1):
                self.partial.append(sample)
                if len(self.partial) == HOP:
                    self.points.append((position + offset / self.rate,
                                        tuple(self.partial), self.break_next))
                    self.partial.clear()
                    self.break_next = False


def test_lifecycle_variable_blocks_and_partial_hop_locates():
    c = CaptureLifecycleModel()
    c.block(0, 20, sample=1)
    c.block(20 / c.rate, 20, sample=1)
    assert len(c.points) == 1 and c.points[0][2]
    assert len(c.partial) == 8
    c.block(10, 32, sample=2)
    assert c.points[-1][1] == (2,) * HOP and c.points[-1][2]
    c.block(1, 32, sample=3)
    assert c.points[-1][1] == (3,) * HOP and c.points[-1][2]
    c.block(1 + 32 / c.rate, 32, sample=3)
    assert not c.points[-1][2]


def test_lifecycle_freeze_stop_restart_and_reset_policy():
    c = CaptureLifecycleModel()
    c.block(0, 40, reset=False)
    c.block(40 / c.rate, 32, freeze=True, reset=False)
    frozen = list(c.points)
    c.block(0, 32, state=0, freeze=True)
    c.block(5, 32, freeze=True, reset=True)
    assert c.points == frozen
    c.block(5 + 32 / c.rate, 32, freeze=False, reset=False, sample=2)
    assert c.points[-1][1] == (2,) * HOP and c.points[-1][2]
    c.block(0, 32, state=0)
    c.block(7, 32, reset=False)
    assert len(c.points) == len(frozen) + 2 and c.points[-1][2]
    c.block(0, 32, state=0)
    c.block(9, 32, reset=True)
    assert len(c.points) == 1 and c.points[0][2]


def test_capture_memory_map_rebuild_keeps_ui_fixed_and_checks_capacity():
    # Fixed UI, bounded C note storage, then the preserved B capture strides.
    midi_slots = 4096 * (10 + 8 + 1) + 2 * 2048 + 8 * 256 + 256
    base = 122 + 12 + 3 * MAX_COLS + midi_slots
    stride = (8_388_608 - base) // 24
    for rate in (44100, 48000, 96000, 192000):
        capacity = math.ceil((MAX_WINDOW + 0.3) * rate / HOP) + 2
        starts = [base + i * stride for i in range(20)]
        assert starts[0] == base and base + 24 * stride <= 8_388_608
        assert capacity <= stride
        assert all(b - a == stride for a, b in zip(starts, starts[1:]))
    capacity = math.ceil((MAX_WINDOW + 0.3) * 2_000_000 / HOP) + 2
    assert base + 24 * capacity > 8_388_608
    c = CaptureLifecycleModel()
    c.block(0, 32)
    c.block(0, 32, rate=96000)
    assert len(c.points) == 1 and c.points[0][2]


def test_capture_source_uses_host_lifecycle_and_fixed_ui_map():
    from pathlib import Path
    src = Path(__file__).resolve().parents[2] / "bloomscope"
    main = (src / "bloomscope.jsfx").read_text()
    capture = (src / "bloomscope_capture.jsfx-inc").read_text()
    assert "ext_noinit = 1;" in main
    assert "MEM_CBM_BASE = 0;" in main
    assert "srate != cap_rate ? capture_init();" in capture
    assert "floor((__memtop() - MEM_CAPTURE_BASE) / 24)" in capture
    assert "cap_capacity <= stride" in capture
    assert "cap_ready && play_state == 1" in capture
    assert "slider7 && !cap_freeze" in capture


def segment_marks(points, anchor_times=None):
    """Reverse union of later segment intervals; 0 hidden, 1 continuous, 2 break."""
    marks = [0] * len(points)
    covered = []
    finish = len(points) - 1
    while finish >= 0:
        start = finish
        while start > 0 and not points[start][3]:
            start -= 1
        prior = None
        for k in range(start, finish + 1):
            time = points[k][0]
            overlap = any(a <= time <= b for a, b in covered)
            if overlap:
                prior = None
            else:
                crossed = prior is None or points[k][3] or any(
                    a <= time and b >= prior for a, b in covered)
                marks[k] = 2 if crossed else 1
                if (marks[k] == 2 and points[k][3] and anchor_times is not None
                        and anchor_times[k] <= time
                        and not any(a <= time and b >= anchor_times[k] for a, b in covered)):
                    marks[k] = 3
                prior = time
        covered.append((points[start][0], points[finish][0]))
        covered.sort()
        merged = []
        for a, b in covered:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
            else:
                merged.append((a, b))
        covered = merged
        finish = start - 1
    return marks


def visible_segment_points(points):
    return [bool(mark) for mark in segment_marks(points)]


def test_backward_locate_clips_old_overlap_and_keeps_prior_history():
    points = [(1, 1, 1, True), (2, 2, 2, False), (3, 9, 9, False),
              (4, 9, 9, False), (3, 0.5, 0.5, True), (4, 0.5, 0.5, False)]
    flags = visible_segment_points(points)
    assert flags == [True, True, False, False, True, True]
    shown = [p for p, visible in zip(points, flags) if visible]
    assert max(p[1] for p in shown) == 2
    assert shown[2][3], "the newer segment retains its break"


def test_visibility_handles_forward_multiple_locates_and_ring_wrap():
    forward = [(1, 1, 1, True), (2, 1, 1, False),
               (5, 2, 2, True), (6, 2, 2, False)]
    assert all(visible_segment_points(forward))
    multiple = [(1, 1, 1, True), (2, 1, 1, False), (3, 1, 1, False),
                (5, 2, 2, True), (6, 2, 2, False),
                (4, 3, 3, True), (5, 3, 3, False),
                (2, 4, 4, True), (3, 4, 4, False)]
    assert visible_segment_points(multiple) == [True, False, False, False, True,
                                                 True, True, True, True]
    # Retained ring can start in the middle of a segment after wrapping.
    assert visible_segment_points(multiple[1:]) == [False, False, False, True,
                                                      True, True, True, True]


def test_visibility_resets_moving_average_at_skipped_points_and_breaks():
    points = [(1, 1, 1, True), (2, 1, 1, False), (3, 1, 1, False),
              (2, 0, 0, True), (3, 0, 0, False)]
    mask = visible_segment_points(points)
    total = 0.0
    count = 0
    outputs = []
    for k, (time, peak, rms, is_break) in enumerate(points):
        if not mask[k]:
            total = 0.0
            count = 0
            continue
        if is_break:
            total = 0.0
            count = 0
        if count >= 2:
            total -= points[k - 2][2]
        else:
            count += 1
        total += rms
        outputs.append(total / count)
    assert outputs == [1, 0, 0]


def test_plot_source_clips_before_status_and_smoothing():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[2] / "bloomscope/bloomscope_plot.jsfx-inc").read_text()
    assert "mem[MEM_PLOT_VISIBLE + k] = marked" in source
    assert "marked = vis_intersects(t, t) ? 0 : 1" in source
    assert "mem[MEM_PLOT_VISIBLE + idx] && t <= now_t" in source
    assert "oldidx = k - span" in source


def test_snapshot_tickets_reject_overwrites_and_torn_slots_after_wrap():
    # Three published points, ring full. Snapshot order starts at head.
    tickets = [4, 5, 3]
    fields = ["D", "E", "C"]
    head, n, written, capacity = 2, 3, 5, 3

    def read_slot(k, during=None):
        idx = (head - n + k) % capacity
        expected = written - n + k + 1
        before = tickets[idx]
        value = fields[idx]
        if during:
            during(idx)
        after = tickets[idx]
        return value if before == expected and after == expected else None

    assert [read_slot(k) for k in range(n)] == ["C", "D", "E"]
    def overwrite(idx):
        tickets[idx] = 0
        fields[idx] = "new partial value"
        tickets[idx] = 6
    assert read_slot(0, overwrite) is None
    assert read_slot(0) is None  # already overwritten before the copy began
    # A reset must not reuse ticket numbers; an old ticket cannot match a new point.
    assert tickets[2] != written - n + 1


def test_snapshot_publication_rejects_odd_or_changed_metadata():
    def valid(first, second):
        return first % 2 == 0 and first == second
    assert valid(10, 10)
    assert not valid(11, 11)
    assert not valid(10, 12)


def test_smoothing_warms_before_left_edge_without_polluting_hold():
    points = [(0.70, 1.0), (0.80, 1.0), (0.90, 0.0), (1.00, 0.0)]
    left = 0.90
    span = 3
    seen = []
    visible = []
    for time, level in points:
        seen.append(level)
        if time >= left:
            visible.append((sum(seen[-span:]) / min(span, len(seen)), level))
    assert visible == [(2 / 3, 0.0), (1 / 3, 0.0)]
    assert max(level for _, level in visible) == 0.0


def test_sparse_columns_connect_only_without_breaks():
    columns = [(0, False), (3, False), (8, True), (12, False)]
    connections = []
    previous = None
    for column, is_break in columns:
        if previous is not None and not is_break:
            connections.append((previous, column))
        previous = column
    assert connections == [(0, 3), (8, 12)]


def test_source_wires_snapshot_smoothing_sparse_lines_and_view_cycle():
    from pathlib import Path
    src = Path(__file__).resolve().parents[2] / "bloomscope"
    capture = (src / "bloomscope_capture.jsfx-inc").read_text()
    plot = (src / "bloomscope_plot.jsfx-inc").read_text()
    main = (src / "bloomscope.jsfx").read_text()
    bar = (src / "bloomscope_controlbar.jsfx-inc").read_text()
    assert "atomic_add(cap_revision, 1)" in capture
    assert "atomic_set(mem[MEM_CAP_TICKET + cap_head], 0)" in capture
    assert plot.count("atomic_get(mem[MEM_CAP_TICKET + idx]) != ticket") == 2
    assert "frame_ok = snapshot_capture();" in main
    assert "frame_ok ? frame_ok = snapshot_midi();" in main
    assert plot.index("sum += rms;") < plot.index("t >= left_t ? (")
    assert "prev_col >= 0 && brk == 0" in plot
    assert "gfx_line(g_plot_x + prev_col" in plot
    assert "while (j < c)" in plot and "mem[MEM_COLS_BRK + c] == 0" in plot
    assert "cbm_cell(5, 4, 0, 2, 0)" in main
    assert "cbm_kind(hit) == 4 ?" in bar
    assert "ctl_slider_write(ctl_slider_number(i), v)" in main


def test_repeated_seeks_preserve_nonoverlap_and_mark_resumed_history():
    old = [(t, 1, 1, t == 0) for t in range(11)]
    replacement = [(2, 2, 2, True), (3, 2, 2, False)]
    latest = [(8, 3, 3, True), (9, 3, 3, False)]
    marks = segment_marks(old + replacement + latest)
    assert [t for (t, _, _, _), m in zip(old, marks) if m] == [0, 1, 4, 5, 6, 7, 10]
    assert marks[4] == 2 and marks[10] == 2
    assert marks[11:] == [2, 1, 2, 1]


def test_ownership_boundary_between_sparse_points_breaks_even_without_hidden_hop():
    points = [(0, 1, 1, True), (5, 1, 1, False),
              (2, 2, 2, True), (3, 2, 2, False)]
    assert segment_marks(points) == [2, 2, 2, 1]


def test_max_window_retains_smoothing_preroll_at_common_rates():
    for rate in (44100, 48000, 96000, 192000):
        capacity = math.ceil((MAX_WINDOW + 0.3) * rate / HOP) + 2
        visible = math.ceil(MAX_WINDOW * rate / HOP)
        smooth = round(0.3 * rate / HOP)
        assert capacity - visible >= smooth


def test_shared_time_axis_and_bounded_historical_beat_grid():
    from pathlib import Path
    src = Path(__file__).resolve().parents[2] / "bloomscope"
    main = (src / "bloomscope.jsfx").read_text()
    layout = (src / "bloomscope_layout.jsfx-inc").read_text()
    plot = (src / "bloomscope_plot.jsfx-inc").read_text()
    assert "draw_time_axis();" in main
    assert "STATUS_TEXT_MARGIN - TIME_AXIS_HEIGHT" in layout
    assert 'sprintf(#ev_lbl, "%.0f s", tick)' in plot
    assert "step_s = ev_tick_step();" in plot
    assert "beat_dur = 60 / cap_tempo" not in plot
    assert "draw_beat_grid(p);" in plot
    assert "t - prev_t <= 0.05" in plot


def bounded_beat_grid(points, playing=True):
    """Model (point_time, block_time, block_beat, visibility); midpoint bounds."""
    out = []
    if not playing:
        return out
    prev = None
    segment_start = 0
    for point_time, time, beat, flag in points:
        if flag == 0:
            prev = None
            continue
        if flag >= 2:
            prev = None
            segment_start = time if flag == 3 else point_time
        if time < segment_start:
            continue
        if prev and time > prev[0] and time - prev[0] <= 0.05 and beat > prev[1]:
            for number in range(math.floor(prev[1]) + 1, math.floor(beat) + 1):
                out.append((number, time if number == beat else (prev[0] + time) / 2,
                            prev[0], time))
        if prev is None or time > prev[0]:
            prev = (time, beat)
    return out


def test_beat_grid_uses_each_historical_anchor_across_tempo_change():
    # Beat at 0.5 s under 120 BPM, then 1.5 s after a switch to 60 BPM.
    points = [(0.0, 0.0, 0.0, 2), (0.49, 0.49, 0.98, 1),
              (0.51, 0.51, 1.02, 1), (1.49, 1.49, 1.99, 1),
              (1.51, 1.51, 2.01, 1)]
    beats = bounded_beat_grid(points)
    assert [(number, round(t, 3)) for number, t, _, _ in beats] == [(1, 0.5), (2, 1.5)]
    assert all((right - left) <= 0.05 for _, _, left, right in beats)


def test_beat_grid_respects_seeks_hidden_points_freeze_and_block_bound():
    points = [(0, 0, 0.9, 2), (0.02, 0.02, 1.1, 1),
              (3, 3, 4.9, 2), (3.02, 3.02, 5.1, 1),
              (4, 4, 7.9, 0), (4.02, 4.02, 8.1, 1),
              (4.20, 4.20, 9.1, 1)]
    assert [entry[0] for entry in bounded_beat_grid(points)] == [1, 5]
    frozen = bounded_beat_grid(points)
    assert frozen == bounded_beat_grid(points)
    assert bounded_beat_grid(points, playing=False) == []


def test_beat_grid_preserves_exact_anchors_and_ignores_duplicate_blocks():
    points = [(0, 0, 0.9, 2), (0.01, 0, 0.9, 1),
              (0.02, 0.02, 1.0, 1), (0.03, 0.02, 1.0, 1)]
    assert bounded_beat_grid(points) == [(1, 0.02, 0, 0.02)]


def test_beat_anchor_snapshot_and_empty_hold_wiring():
    from pathlib import Path
    src = Path(__file__).resolve().parents[2] / "bloomscope"
    capture = (src / "bloomscope_capture.jsfx-inc").read_text()
    plot = (src / "bloomscope_plot.jsfx-inc").read_text()
    assert "mem[MEM_CAP_BEAT_TIME + cap_head] = cap_beat_t" in capture
    assert "mem[MEM_CAP_BEAT + cap_head] = cap_beat_b" in capture
    assert "mem[MEM_SNAP_BEAT + k] = capture_beat(idx)" in plot
    assert "flag >= 2 ? (" in plot
    assert "seg_start = flag == 3 ? plot_beat_time(k) : plot_time(k)" in plot
    assert "brk = mem[MEM_PLOT_VISIBLE + idx] >= 2" in plot
    assert "g_agg_hold = -1" in plot
    assert "g_agg_hold >= 0 ? ev_db_of_amp(g_agg_hold)" in plot


def test_beat_grid_accepts_first_block_anchor_before_first_hop_end():
    sr = 48000
    first_hop = 32 / sr
    next_block = 512 / sr
    audio = [(first_hop, 1, 1, True), (next_block + first_hop, 1, 1, False)]
    anchors = [0.0, next_block]
    marks = segment_marks(audio, anchors)
    assert marks == [3, 1]
    beats = bounded_beat_grid([(audio[0][0], anchors[0], 0.99, marks[0]),
                               (audio[1][0], anchors[1], 1.01, marks[1])])
    assert len(beats) == 1 and abs(beats[0][1] - next_block / 2) < 1e-12


def test_beat_first_anchor_rejected_when_newer_coverage_intervenes():
    hop_end = 32 / 48000
    next_block = 512 / 48000
    # First point is visible, but the newer interval lies between its anchor and hop end.
    points = [(hop_end, 1, 1, True), (next_block + hop_end, 1, 1, False),
              (0.0002, 2, 2, True), (0.0004, 2, 2, False)]
    anchors = [0.0, next_block, 0.0002, 0.0002]
    marks = segment_marks(points, anchors)
    assert marks[:2] == [2, 1]
    assert bounded_beat_grid([(points[0][0], anchors[0], 0.99, marks[0]),
                              (points[1][0], anchors[1], 1.01, marks[1])]) == []


def test_beat_artificial_ownership_boundary_never_reuses_earlier_anchor():
    points = [(0.001, 1, 1, True), (0.021, 1, 1, False),
              (0.015, 2, 2, True), (0.019, 2, 2, False)]
    anchors = [0.0, 0.01, 0.015, 0.015]
    marks = segment_marks(points, anchors)
    assert marks[:2] == [3, 2]
    assert bounded_beat_grid([(points[0][0], anchors[0], 0.9, marks[0]),
                              (points[1][0], anchors[1], 1.1, marks[1])]) == []


class VisibilityCoverageTree:
    """Model of EEL2 sorted coordinates and iterative coverage operations."""
    def __init__(self, times):
        self.coords = sorted(times)
        self.leaf = 1
        while self.leaf < len(times):
            self.leaf *= 2
        self.tree = [0] * (2 * self.leaf)
        self.steps = 0

    def indices(self, a, b):
        from bisect import bisect_left, bisect_right
        return (bisect_left(self.coords, a) + self.leaf,
                bisect_right(self.coords, b) + self.leaf)

    def cover(self, a, b):
        l, r = self.indices(a, b)
        left, right = l, r - 1
        while l < r:
            self.steps += 1
            if l % 2:
                self.tree[l] = 2
                l += 1
            if r % 2:
                r -= 1
                self.tree[r] = 2
            l //= 2
            r //= 2
        for boundary in (left, right):
            node = boundary // 2
            while node:
                self.steps += 1
                if self.tree[node] != 2:
                    c1, c2 = self.tree[node * 2:node * 2 + 2]
                    self.tree[node] = 2 if c1 == c2 == 2 else int(bool(c1 or c2))
                node //= 2

    def intersects(self, a, b):
        l, r = self.indices(a, b)
        if l >= r:
            return False
        for boundary in (l, r - 1):
            node = boundary // 2
            while node:
                self.steps += 1
                if self.tree[node] == 2:
                    return True
                node //= 2
        while l < r:
            self.steps += 1
            if l % 2:
                if self.tree[l]:
                    return True
                l += 1
            if r % 2:
                r -= 1
                if self.tree[r]:
                    return True
            l //= 2
            r //= 2
        return False


def segment_marks_tree(points, anchors):
    tree = VisibilityCoverageTree([p[0] for p in points])
    marks = [0] * len(points)
    finish = len(points) - 1
    while finish >= 0:
        start = finish
        while start > 0 and not points[start][3]:
            start -= 1
        prior = None
        for k in range(start, finish + 1):
            time = points[k][0]
            if tree.intersects(time, time):
                prior = None
                continue
            is_break = prior is None or points[k][3] or tree.intersects(prior, time)
            marks[k] = 2 if is_break else 1
            if (is_break and points[k][3] and anchors[k] <= time
                    and not tree.intersects(anchors[k], time)):
                marks[k] = 3
            prior = time
        tree.cover(points[start][0], points[finish][0])
        finish = start - 1
    return marks, tree.steps


def test_visibility_tree_matches_interval_union_across_adversarial_seeks():
    import random
    rng = random.Random(417)
    for case in range(150):
        points, anchors = [], []
        for _ in range(rng.randint(1, 30)):
            start = rng.randrange(-20, 21)
            for offset in range(rng.randint(1, 5)):
                time = start + offset
                points.append((time, 1, 1, offset == 0))
                anchors.append(time - rng.choice((0, 0.5, 2)))
        expected = segment_marks(points, anchors)
        actual, _ = segment_marks_tree(points, anchors)
        assert actual == expected, (case, points, actual, expected)


def test_visibility_tree_bounds_work_for_many_disjoint_single_hop_segments():
    n = 45000
    points = [(float(k * 2), 1, 1, True) for k in range(n)]
    marks, steps = segment_marks_tree(points, [p[0] for p in points])
    assert all(mark == 3 for mark in marks)
    # Each union insertion/query traverses O(log n) nodes, not prior segments.
    assert steps < n * 12 * math.ceil(math.log2(n))


def test_visibility_source_runs_once_per_snapshot_and_allocates_tree():
    from pathlib import Path
    src = Path(__file__).resolve().parents[2] / "bloomscope"
    capture = (src / "bloomscope_capture.jsfx-inc").read_text()
    plot = (src / "bloomscope_plot.jsfx-inc").read_text()
    assert plot.count("  plot_visibility();") == 1
    assert "MEM_CAPTURE_END = MEM_PLOT_TREE + 4 * stride" in capture
    assert "floor((__memtop() - MEM_CAPTURE_BASE) / 24)" in capture
    assert "n > 0 ? (\n    k = 0;\n    loop(2 * vis_leaf" in plot


def _main() -> int:
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    failures = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"ok   {test.__name__}")
    print(f"\n{len(tests)} test(s), {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
