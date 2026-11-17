#!/usr/bin/env python3
"""Generate a deterministic REAPER JSFX test of the actual acquisition functions.

Only host read-only variable names are substituted, so tests can drive measured
block anchors. The EEL2 function bodies are otherwise the production sources.
This is a host-compiled regression, not a substitute for live playback testing.
Usage: python3 build_loop_host_probe.py <external-output-directory>
Results: BloomScope_Loop_v1 gmem[10000] = completion magic 9173,
[10001] assertion count, [10002] failure count, [10003] last failed assertion.
"""
from pathlib import Path
import re
import sys

SRC = Path(__file__).resolve().parents[2] / 'bloomscope'

DRIVER = r'''
@init
ext_noinit = 1;
function check(value) (
  checks += 1;
  !value ? ( failures += 1; last_failed = checks; );
);
function context(enabled) local(b) (
  b = (slider11 % LOOP_SLOTS) * LOOP_STRIDE;
  slider11 > 0 ? (
  gmem[b] = 1;
  gmem[b + 1] = slider11;
  gmem[b + 2] = loop_nonce;
  gmem[b + 3] = enabled;
  gmem[b + 4] = test_start;
  gmem[b + 5] = test_end;
  gmem[b + 6] = test_srate;
  gmem[b + 7] = 0;
  gmem[b + 8] = 1;
  gmem[b + 9] += 1;
  gmem[b + 10] = time_precise();
  gmem[b] = 2;
  );
);
function setup(rate, start, end, token) (
  test_srate = rate; test_start = start; test_end = end;
  slider1 = 0; slider7 = 0; slider11 = token;
  test_play_state = 1;
  loop_token = 0; loop_age = 10; loop_seen_heartbeat = -1; loop_config = -1;
  loop_init(0); midi_init(MEM_LOOP_END); MEM_CAPTURE_BASE = MEM_MIDI_END;
  capture_init();
);
function begin(t, n) (
  test_play_position = t; test_beat_position = t * 1.2; test_samplesblock = n;
  context(1);
  capture_block(); loop_block();
  atomic_add(midi_revision, 1); midi_block(); loop_limit_segment();
);
function samples(n) (
  atomic_add(midi_revision, 1);
  loop(n,
    loop_sample_boundary(); capture_sample(0.25, 0.5); loop_sample_boundary();
  );
);
function find_note(pitch) local(k, r) (
  found = 0;
  k = 0;
  loop(midi_n,
    r = MEM_MIDI_RECORD + ((midi_head - midi_n + k + MIDI_CAPACITY) % MIDI_CAPACITY) * MIDI_RECORD_STRIDE;
    mem[r + 2] == pitch && mem[r + 7] == 1 ? found = r + 1;
    k += 1;
  );
  found;
);

// Baseline: exact measured reproduction still fails without a companion.
setup(48000, 0, 80/3, 0);
begin(80/3 - 640/48000, 384); samples(384);
begin(80/3 - 256/48000, 384); loop_receive(256, 144, 62, 88); samples(384);
begin(128/48000, 384); loop_receive(320, 128, 62, 0); samples(384);
r = find_note(62) - 1;
check(r >= 0 && abs(mem[r]) > 1);
check(midi_n == 2 && mem[r + 5] == 2);

// With context: old notes truncate at end, new on/off pair at wrapped times.
setup(48000, 0, 80/3, 127);
begin(80/3 - 640/48000, 384); loop_receive(0, 144, 60, 90); samples(384);
begin(80/3 - 256/48000, 384);
check(loop_split == 256);
loop_receive(255, 128, 60, 0);
loop_receive(256, 144, 62, 88);
loop_receive(257, 145, 62, 99);
check(loop_queued == 2);
check(midi_n == 1);
samples(256);
check(loop_splits >= 1 && cap_hopn == 0);
check(midi_n == 3);
check(cap_now_segment < midi_segment_id);
seg = MEM_MIDI_SEG + ((midi_seg_head + MIDI_SEGMENTS - 1) % MIDI_SEGMENTS) * MIDI_SEGMENT_FIELDS;
check(mem[seg + 3] == 0);
samples(32);
check(cap_now_segment == midi_segment_id && mem[seg + 3] > 0);
check(abs(cap_now_t - 32/48000) < 1e-9);
samples(96);
wrapped_segment = midi_segment_id;
begin(128/48000, 384);
check(midi_segment_id == wrapped_segment && !cap_boundary);
loop_receive(320, 144, 62, 0); samples(384);
r = find_note(62) - 1;
// Last found record is channel 2; verify channel independence separately.
check(mem[r + 3] == 1 && mem[r + 5] == 0);
r = MEM_MIDI_RECORD + MIDI_RECORD_STRIDE;
check(abs(mem[r]) < 1e-9 && mem[r + 5] == 1);
check(abs(mem[r + 1] - 448/48000) < 1e-9);
check(mem[r + 4] == 88);

// Nonzero loop start, exact block endpoint, partial-hop discard, freeze.
setup(44100, 2, 3, 127);
begin(3 - 117/44100, 65); samples(65);
begin(3 - 52/44100, 52); loop_receive(52, 144, 65, 77); samples(52);
check(cap_hopn == 0 && abs(cap_play_t + 52/44100 - 2) < 1e-9);
r = find_note(65) - 1;
check(r >= 0 && abs(mem[r] - 2) < 1e-9);
begin(2, 64); samples(64);
check(abs(cap_now_t - (2 + 64/44100)) < 1e-9);
slider1 = 1;
begin(2 + 64/44100, 64);
check(loop_split == -1);
samples(64);
check(abs(cap_now_t - (2 + 64/44100)) < 1e-9);

// A manual backward seek opens a gap but is never remapped to the loop start.
setup(48000, 1, 3, 127);
begin(2, 384); samples(384);
begin(1.5, 384); loop_receive(0, 144, 66, 88); samples(384);
r = find_note(66) - 1;
check(abs(mem[r] - 1.5) < 1e-9);
check(loop_split == -1);

// Invalid context and multiwrap blocks fail closed, not speculative retiming.
setup(48000, 0, 0.001, 127);
begin(0, 384); samples(384);
begin(0, 384);
check(loop_status != 1 || loop_split == -1);
samples(384);
setup(48000, 0, 1, 127);
begin(0.98, 384); samples(384);
context(1); b = (slider11 % LOOP_SLOTS) * LOOP_STRIDE;
gmem[b + 2] = loop_nonce + 1;
test_play_position = 0.988; test_samplesblock = 768;
capture_block(); loop_block();
check(loop_status == 2 && loop_split == -1);
context(1); gmem[b] = 3;
loop_block(); check(loop_status == 2 && loop_split == -1);
context(1); gmem[b + 6] = 96000;
loop_block(); check(loop_status == 2 && loop_split == -1);
context(1); gmem[b + 10] = time_precise() - 5;
loop_block(); check(loop_status == 2 && loop_split == -1);
context(1); gmem[b + 10] = time_precise() + 5;
loop_block(); check(loop_status == 2 && loop_split == -1);
context(0); loop_block(); check(loop_status == 2 && loop_split == -1);
context(1); loop_block();
loop(130, loop_block(););
check(loop_status == 2 && loop_split == -1);

// Common rates/buffers: partial hops, exact onset and repeated-pitch FIFO.
rate_index = 0;
loop(4,
  test_rate = rate_index == 0 ? 44100 : rate_index == 1 ? 48000 : rate_index == 2 ? 96000 : 192000;
  block_index = 0;
  loop(4,
    n = block_index == 0 ? 128 : block_index == 1 ? 256 : block_index == 2 ? 384 : 1024;
    split_at = floor(n / 3) + 1;
    setup(test_rate, 1, 3, 127);
    begin(3 - (split_at + n) / test_rate, n); samples(n);
    begin(3 - split_at / test_rate, n);
    check(loop_split == split_at);
    loop_receive(split_at, 144, 62, 88);
    loop_receive(split_at + 1, 144, 62, 99);
    loop_receive(split_at + 2, 144, 62, 0);
    loop_receive(split_at + 3, 128, 62, 0);
    samples(n);
    r = MEM_MIDI_RECORD;
    check(midi_n == 2 && abs(mem[r] - 1) < 1e-9);
    check(abs(mem[r + 1] - (1 + 2/test_rate)) < 1e-9 && mem[r + 5] == 1);
    r += MIDI_RECORD_STRIDE;
    check(abs(mem[r] - (1 + 1/test_rate)) < 1e-9 && mem[r + 4] == 99);
    check(abs(mem[r + 1] - (1 + 3/test_rate)) < 1e-9 && mem[r + 5] == 1);
    block_index += 1;
  );
  rate_index += 1;
);

// Queue exhaustion is bounded and explicit. It cannot alter MIDI passthrough.
setup(48000, 0, 1, 127);
begin(1 - 640/48000, 384); samples(384);
begin(1 - 256/48000, 384);
loop(LOOP_QUEUE_CAPACITY + 1, loop_receive(256, 144, 62, 88););
check(loop_queued == LOOP_QUEUE_CAPACITY && loop_status == 4 && loop_overflows == 1);
samples(384);
check(midi_n == MIDI_CAPACITY);

gmem[10001] = checks;
gmem[10002] = failures;
gmem[10003] = last_failed;
gmem[10000] = 9173;
'''


def build(destination):
    destination.mkdir(parents=True, exist_ok=True)
    imports = []
    for name in ('midi', 'capture', 'loop'):
        original = SRC / f'bloomscope_{name}.jsfx-inc'
        text = original.read_text()
        for identifier in ('play_position', 'play_state', 'samplesblock', 'srate', 'beat_position'):
            text = re.sub(rf'\b{identifier}\b', 'test_' + identifier, text)
        target = f'probe_{name}.jsfx-inc'
        (destination / target).write_text(text)
        imports.append('import ' + target)
    path = destination / 'loop_regression_probe.jsfx'
    path.write_text('desc:BloomScope loop regression probe\noptions:gmem=BloomScope_Loop_v1\n'
                    'in_pin:none\nout_pin:none\n' + '\n'.join(imports) + '\n' + DRIVER.replace('1e-9', '0.000000001') + '\n@block\ngmem[10004] = time_precise();\n')
    return path


if __name__ == '__main__':
    print(build(Path(sys.argv[1])))
