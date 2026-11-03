#!/usr/bin/env python3
"""Build temporary, instrumented copies for native UI/audio/MIDI acceptance.

Never launches REAPER or replaces the installed package. Use a new temporary
Effects subdirectory and copy ccscope_acceptance_runner.lua to a work directory.
Only the test copies receive telemetry and a synthetic initial history.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

SEED = '''
accept_cookie = time_precise();
g_clock_sec = 200;
accept_i = 0;
accept_pairs = max(1, gmem[3]);
loop(MAX_HISTORY_ITEMS,
  accept_pair = accept_i % accept_pairs;
  accept_cc = accept_pair % 128;
  accept_ch = floor(accept_pair / 128);
  accept_t = 200 - (MAX_HISTORY_ITEMS - 1 - accept_i) / (accept_pairs * 16);
  accept_v = (floor(accept_i / accept_pairs) * 7 + accept_pair * 13) % 128;
  assign_color_to_cc(accept_cc);
  store_cc_channel_value(accept_cc, accept_ch, accept_v);
  add_to_history_with_channel(accept_t, accept_cc, accept_ch, accept_v);
  accept_t >= 199 ? update_metrics_for_cc_channel(accept_cc, accept_ch, accept_v, accept_t);
  accept_i += 1;
);
'''

TELEMETRY = '''
accept_elapsed = (time_precise() - accept_start) * 1000;
accept_interval = accept_last > 0 ? (accept_start - accept_last) * 1000 : 0;
accept_last = accept_start;
accept_gfx_seq += 1;
accept_slot = 5000 + (accept_gfx_seq % 1024) * 2;
gmem[accept_slot] = accept_elapsed;
gmem[accept_slot + 1] = accept_interval;
gmem[6] = g_clock_sec;
gmem[7] = get_history_count();
gmem[8] = mem[MEM_HISTORY_WRITE];
gmem[10] = gfx_w; gmem[11] = gfx_h;
gmem[12] = slider2; gmem[13] = g_menu_open; gmem[14] = g_hover_cell;
gmem[15] = g_grid_cache_valid; gmem[16] = g_layout_side;
gmem[17] = filtered_count; gmem[18] = g_metrics_tier;
gmem[19] = accept_grid_calls;
gmem[20] = slider1; gmem[21] = slider2; gmem[22] = slider3;
gmem[23] = slider4; gmem[24] = slider5; gmem[25] = slider6; gmem[26] = slider7;
gmem[27] = srate; gmem[28] = samplesblock;
accept_i = 1;
loop(7,
  gmem[40 + accept_i] = mem[MEM_CTL_X + accept_i] + mem[MEM_CTL_W + accept_i] / 2;
  accept_i += 1;
);
gmem[60] = g_metrics_x; gmem[61] = g_start_y; gmem[62] = g_visible_bars;
gmem[63] = FONT_SIZE; gmem[64] = gfx_ext_retina;
gmem[71] = g_side_fallback; gmem[72] = g_time_end;
gmem[73] = g_menu_x; gmem[74] = g_menu_y;
gmem[75] = g_menu_scroll; gmem[76] = g_menu_rows;
gmem[77] = gfx_ext_flags;
gmem[91] = accept_cookie;
gmem[4] = accept_gfx_seq;
'''

GENERATOR = '''desc:CCScope acceptance MIDI generator
options:no_meter
options:gmem=CCScopeAcceptance23
@init
phase = 0; step = 0;
function emit(offset, a, b, c) (
  gmem[104] += 1;
  midisend(offset, a, b, c);
);
@block
// Include any host-generated reset messages in the observed input stream too.
while(midirecv(in_offset, in_a, in_b, in_c)) ( emit(in_offset, in_a, in_b, in_c); );
gmem[2] ? (
  pos = phase;
  while(pos < samplesblock) (
    pair = 0;
    loop(gmem[1],
      emit(floor(pos), 0xB0 | floor(pair / 128), pair % 128, (step * 7 + pair * 13) % 128);
      pair += 1;
    );
    emit(floor(pos), 0x90, 60, 80);
    emit(floor(pos), 0x80, 60, 0);
    emit(floor(pos), 0xC0, step % 128, 0);
    emit(floor(pos), 0xE0, step % 128, 64);
    step += 1;
    pos += srate / 16;
  );
  phase = pos - samplesblock;
) : phase = 0;
@sample
spl0 = 0; spl1 = 0;
'''

MONITOR = '''desc:CCScope acceptance MIDI monitor
options:no_meter
options:gmem=CCScopeAcceptance23
@block
while(midirecv(offset, a, b, c)) (
  n = gmem[102];
  n < 32768 ? (
    gmem[100000 + n * 2] = offset;
    gmem[100000 + n * 2 + 1] = a | (b << 8) | (c << 16);
    gmem[102] = n + 1;
  ) : gmem[103] = 1;
);
@sample
spl0 = 0; spl1 = 0;
'''


def provides(source: Path) -> list[Path]:
    """The package files, read from the @provides block: one source of truth."""
    text = (source / 'ccscope.jsfx').read_text()
    block = text.split('@provides', 1)[1].split('@changelog', 1)[0]
    names = [line.strip().lstrip('/').strip() for line in block.splitlines()]
    names = [name for name in names if name]
    if not names:
        raise ValueError('@provides lists no files')
    for name in names:
        if not (source / name).exists():
            raise ValueError(f'@provides names a file that does not exist: {name}')
    return [source / name for name in names]


def instrument(source: str, variant: str, *, seed_history: bool = True,
               temporal: bool = True) -> str:
    """Instrument the conductor: metadata, gmem, the audio clock and telemetry.

    Only ccscope.jsfx is touched here: it owns desc/options and the @block,
    @sample and @gfx sections. The two drawing hooks live in the panels and are
    injected by instrument_plot() and instrument_rows().
    """
    if 'options:gmem=' in source or 'accept_start =' in source:
        raise ValueError('Use an uninstrumented source, not an earlier probe')
    seed = SEED if seed_history else '\naccept_cookie = time_precise();\n'
    if seed_history and temporal:
        marker = '  add_to_history_with_channel(accept_t, accept_cc, accept_ch, accept_v);'
        seed = seed.replace(marker, marker + '\n  add_temporal_history(accept_t, make_cc_channel_key(accept_cc, accept_ch), accept_v);')
    replacements = {
        'desc:CCScope (MIDI CC oscilloscope)': f'desc:CCScope acceptance {variant}',
        'options:no_meter': 'options:no_meter\noptions:gmem=CCScopeAcceptance23',
        '\n@block\n': seed + '\n@block\naccept_block_start = time_precise();\n',
        '\n@sample\n': '''
accept_block_seq += 1;
gmem[2000 + (accept_block_seq % 2048)] = (time_precise() - accept_block_start) * 1000000;
gmem[5] = accept_block_seq;
@sample
''',
        '@gfx 1000 720': '@gfx 1000 720\naccept_start = time_precise();\ngmem[70] = 0;',
    }
    for old, new in replacements.items():
        if source.count(old) != 1:
            raise ValueError(f'Unexpected source boundary: {old!r}')
        source = source.replace(old, new)
    return source + TELEMETRY


def instrument_plot(source: str) -> str:
    """Count grid rebuilds from inside the real background renderer."""
    signature = 'function draw_graph_background() local(i, level, weight, y) ('
    if source.count(signature) != 1:
        raise ValueError('Unexpected background function signature')
    return source.replace(signature, signature + '\n  accept_grid_calls += 1;')


def instrument_rows(source: str) -> str:
    """Observe entry to the actual tooltip paint branch; no fake pointer state."""
    marker = '  hit && mouse_x > 0 && mouse_y > 0 ? ('
    if source.count(marker) != 1:
        raise ValueError('Unexpected tooltip paint branch')
    return source.replace(marker, marker + '\n    gmem[70] = hit;')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference', type=Path, required=True)
    ap.add_argument('--candidate', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        ap.error('--output must be a new temporary directory')
    for variant, path in (('baseline', args.reference), ('candidate', args.candidate)):
        target = args.output / variant
        target.mkdir(parents=True)
        files = provides(path.parent)
        for file in files:
            shutil.copy2(file, target / file.name)
        (target / 'ccscope_plot.jsfx-inc').write_text(
            instrument_plot((path.parent / 'ccscope_plot.jsfx-inc').read_text()))
        (target / 'ccscope_rows.jsfx-inc').write_text(
            instrument_rows((path.parent / 'ccscope_rows.jsfx-inc').read_text()))
        (target / 'ccscope.jsfx').write_text(instrument(path.read_text(), variant))
    (args.output / 'generator.jsfx').write_text(GENERATOR)
    # Observe the delivered input, not the generator's pre-host emission order:
    # REAPER may canonicalize simultaneous bank/program/note events between FX.
    observer = MONITOR.replace('MIDI monitor', 'MIDI input observer')
    observer = observer.replace('gmem[102]', 'gmem[100]').replace('gmem[103]', 'gmem[101]')
    observer = observer.replace('100000', '10000')
    observer = observer.replace('\n);\n@sample', '\n  midisend(offset, a, b, c);\n);\n@sample')
    (args.output / 'input.jsfx').write_text(observer)
    (args.output / 'monitor.jsfx').write_text(MONITOR)
    print('Built test-only baseline/candidate, MIDI generator and byte/offset monitor')


if __name__ == '__main__':
    main()
