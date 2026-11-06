#!/usr/bin/env python3
"""Build a native JSFX draw-command regression probe; never launch REAPER.

Usage:
    python3 tools/ccscope_rendering_probe.py --reference <baseline.jsfx> \
        --source ccscope --output <temporary-effects-directory>

Load ccscope_rendering_probe.jsfx in a disposable REAPER project. The probe
executes the actual reference and candidate graph functions, intercepting only
their line/circle drawing calls. gmem namespace CCScopeRenderingTest23 exposes
status at 20 (0=running, 1=passed, -1=failed), completed case at 21, and failure
command index / expected count / actual count at 22/23/24.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil


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


def graph_function(source: str) -> str:
    if 'event_slot(' in source:
        raise ValueError('The renderer reads the event ring, so this probe has no fixtures to drive it; use ccscope_history_probe.py instead of exact-event differential tests')
    start = source.index('function draw_cc_data_lines(')
    try:
        end = source.index('\n/**', start)
    except ValueError:          # the renderer is the last function of its file
        end = len(source)
    result = source[start:end].rstrip()
    if not result.endswith(');'):
        raise ValueError('Unexpected graph function boundary; inspect source before updating the probe')
    return result


CAPTURE = '''
// Test-only command buffer, outside all production memory ranges.
function probe_capture(kind, a, b, c, d) local(p) (
  p = 4000000 + probe_commands * 9;
  probe_mode == 0 ? (
    mem[p] = kind; mem[p+1] = a; mem[p+2] = b; mem[p+3] = c; mem[p+4] = d;
    mem[p+5] = gfx_r; mem[p+6] = gfx_g; mem[p+7] = gfx_b; mem[p+8] = gfx_a;
  ) : (
    probe_commands >= probe_expected
      || mem[p] != kind
      || abs(mem[p+1] - a) > 0.0000001 || abs(mem[p+2] - b) > 0.0000001
      || abs(mem[p+3] - c) > 0.0000001 || abs(mem[p+4] - d) > 0.0000001
      || abs(mem[p+5] - gfx_r) > 0.0000001 || abs(mem[p+6] - gfx_g) > 0.0000001
      || abs(mem[p+7] - gfx_b) > 0.0000001 || abs(mem[p+8] - gfx_a) > 0.0000001 ? (
      gmem[20] = -1;
      gmem[22] = probe_commands;
    );
  );
  probe_commands += 1;
);
function probe_line(a, b, c, d) ( probe_capture(1, a, b, c, d); );
function probe_circle(a, b, c, d) ( probe_capture(2, a, b, c, d); );
'''

DRIVER = '''
function probe_fixture(total) local(i, cc, ch, t, v) (
  init_cc_utils();
  // Persistent pairs with no retained events must not acquire stale points.
  i = 0;
  loop(4,
    assign_color_to_cc(120 + i);
    store_cc_channel_value(120 + i, 15, 0);
    i += 1;
  );
  i = 0;
  loop(total,
    cc = i % 16;
    ch = floor(i / 16) % 4;
    t = 15 - (total - 1 - i) * 0.008;
    v = (i * 29 + floor(i / 11)) % 128;
    assign_color_to_cc(cc);
    store_cc_channel_value(cc, ch, v);
    add_to_history_with_channel(t, cc, ch, v);
    i += 1;
  );
);
probe_case = 0;
gmem[20] = 0;
gmem[21] = 0;
@gfx 1000 720
gfx_clear = 0;
gfx_mode = 0;
gfx_setfont(1, "Arial", FONT_SIZE);
probe_case < 630 && gmem[20] != -1 ? (
  probe_size = probe_case % 7;
  probe_total = probe_size == 0 ? 0 : probe_size == 1 ? 1 : probe_size == 2 ? 17
    : probe_size == 3 ? 1999 : probe_size == 4 ? 2000 : probe_size == 5 ? 2031 : 4017;
  slider5 = floor(probe_case / 7) % 3;
  probe_filter = floor(probe_case / 21) % 5;
  slider1 = probe_filter == 1 ? 1 : probe_filter == 3 ? 7 : probe_filter == 4 ? 127 : 0;
  slider6 = probe_filter == 2 ? 2 : probe_filter == 3 ? 3 : probe_filter == 4 ? 16 : 0;
  probe_window = floor(probe_case / 105) % 3;
  slider3 = probe_window == 0 ? 1 : probe_window == 1 ? 10 : 30;
  slider7 = floor(probe_case / 315) % 2;
  probe_fixture(probe_total);
  probe_visible = build_visible_cc_channel_pair_list(slider1, slider6);
  calculate_layout(probe_visible);
  g_time_end = 15;
  g_time_window = slider3;
  g_time_start = g_time_end - g_time_window;
  probe_mode = 0;
  probe_commands = 0;
  probe_reference_lines(probe_visible);
  probe_expected = probe_commands;
  probe_mode = 1;
  probe_commands = 0;
  draw_cc_data_lines(probe_visible);
  probe_commands != probe_expected ? gmem[20] = -1;
  gmem[23] = probe_expected;
  gmem[24] = probe_commands;
  probe_case += 1;
  gmem[21] = probe_case;
  probe_case == 630 && gmem[20] != -1 ? gmem[20] = 1;
);
gfx_r = gmem[20] == -1 ? 1 : 0.2;
gfx_g = gmem[20] == -1 ? 0.2 : 0.8;
gfx_b = 0.2; gfx_a = 1;
gfx_x = 20; gfx_y = 20;
gfx_printf("Graph command regression: %d / 630, status %d", probe_case, gmem[20]);
'''


def build_status(source: Path, output: Path) -> Path:
    """Assemble the status-line probe: the real source plus the recorded driver.

    Refuses to build when the module it probes has changed shape: a probe that
    silently reads globals the plugin no longer has is worse than no probe.
    """
    port = (source / 'ccscope_status.jsfx-inc').read_text()
    if port.count('function draw_status_info(count)') != 1:
        raise ValueError('draw_status_info() changed signature; update the status probe')
    for name in ('g_st_form', 'g_st_ver', 'g_st_w', 'g_st_ver_w'):
        if f'{name} =' not in port:
            raise ValueError(f'the status module no longer declares {name!r}')

    main = (source / 'ccscope.jsfx').read_text().split('\n@block\n', 1)[0]
    main = main.replace('desc:CCScope', 'desc:CCScope status-line probe')
    main = main.replace('options:no_meter', 'options:no_meter\noptions:gmem=CCScopeStatusTest')
    driver = Path(__file__).with_name('ccscope_status_probe.txt').read_text()

    output.mkdir(parents=True, exist_ok=True)
    for path in provides(source):
        shutil.copy2(path, output / path.name)
    target = output / 'ccscope_status_probe.jsfx'
    target.write_text(main + '\n' + driver)
    return target


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference', type=Path)
    ap.add_argument('--grid', action='store_true', help='Compare cached/direct grid pixels instead of graph commands')
    ap.add_argument('--status', action='store_true',
                    help='Check the status line decisions and geometry instead of graph commands')
    ap.add_argument('--source', type=Path, default=Path('ccscope'))
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.status:
        target = build_status(args.source, args.output)
        print(f'Built native status-line probe: {target}')
        return
    main = (args.source / 'ccscope.jsfx').read_text()
    plot_name = 'ccscope_plot.jsfx-inc'
    plot = (args.source / plot_name).read_text()
    if args.grid:
        original = ''
        driver = Path(__file__).with_name('ccscope_grid_probe.txt').read_text()
        signature = 'function draw_graph_background() local(i, level, weight, y) ('
        if plot.count(signature) != 1:
            raise ValueError('Unexpected background function signature')
        plot = plot.replace(signature, signature + '\n  probe_grid_builds += 1;')
    else:
        if args.reference is None:
            ap.error('--reference is required for graph-command comparison')
        original = graph_function(args.reference.read_text())
        candidate = graph_function(plot)
        original = original.replace('function draw_cc_data_lines(', 'function probe_reference_lines(')
        original = original.replace('gfx_line(', 'probe_line(').replace('gfx_circle(', 'probe_circle(')
        wrapped = candidate.replace('gfx_line(', 'probe_line(').replace('gfx_circle(', 'probe_circle(')
        plot = plot.replace(candidate, CAPTURE + wrapped)
    main = main.split('\n@block\n', 1)[0]
    main = main.replace('desc:CCScope', 'desc:CCScope rendering regression probe')
    main = main.replace('options:no_meter', 'options:no_meter\noptions:gmem=CCScopeRenderingTest23')
    args.output.mkdir(parents=True, exist_ok=True)
    for path in provides(args.source):
        shutil.copy2(path, args.output / path.name)
    (args.output / plot_name).write_text(plot)
    target = args.output / 'ccscope_rendering_probe.jsfx'
    target.write_text(main + '\n' + original + '\n' + driver)
    kind = 'grid-pixel' if args.grid else 'graph-command'
    print(f'Built native {kind} probe: {target}')


if __name__ == '__main__':
    main()
