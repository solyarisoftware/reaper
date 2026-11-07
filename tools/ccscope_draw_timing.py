#!/usr/bin/env python3
"""Build a native EEL2 probe that times the trace renderer. Never launches REAPER.

Does not launch REAPER. Output must be a new temporary Effects directory.

The probe copies the current storage code and extracts the production renderer, so
it times the code that ships, not a copy. Four fixtures are measured, each in the
worst-case drawing mode (points + step + coda):

    case 0   4000 events, 10 pairs    the drawing budget, spread over ten traces
    case 1   9600 events, 10 pairs    320 events/s over a 30 s window
    case 2   9600 events,  1 pair     the same stream on a single trace
    case 3   4000 events,  1 pair     the budget on a single trace

Each case is set up on one frame, then `draw_cc_data_lines` is timed over 32
frames with `time_precise()`; the best and the mean are kept, because a single
frame can be disturbed by the host and the best is the least noisy estimate of
the renderer's own cost.

Results use gmem namespace CCScopeDrawTiming, three slots per case:
[case*3] best microseconds, [case*3+1] mean microseconds, [case*3+2] marks drawn.
[12] is the number of cases stored: 4 means the run is complete.

What this measures and what it does not: the time spent inside `@gfx` emitting the
drawing commands. REAPER rasterises afterwards, so this is not the time to
pixels on screen; it is the same quantity the plugin's own budget is based on, so
it can be compared with it. Measure frames per second separately.
"""
from pathlib import Path
import argparse
import shutil


CASES = '''
// case -> how many events, on how many pairs. Declared as data, applied identically
// to both the fixture and the reading side, so a new case is one line.
function timing_events(c) ( (c == 1 || c == 2) ? 9600 : 4000 );
function timing_pairs(c) ( (c == 2 || c == 3) ? 1 : 10 );

/** Fills the ring for one case and resets the window: every event is new. */
function timing_load(c) local(i, n, pairs) (
  n = timing_events(c);
  pairs = timing_pairs(c);
  mem[MEM_PAIR_LIST_COUNT] = pairs;
  i = 0;
  loop(pairs,
    mem[MEM_CC_SORTED + i] = make_cc_channel_key(i, 0);
    i += 1;
  );
  clear_history();
  // spread over 28 s of a 30 s window: the trace fills most of the plot, so the
  // cost is a real one and not a handful of pixels at the right edge
  i = 0;
  loop(n,
    add_event(0.1 + i * (28.0 / n), make_cc_channel_key(i % pairs, 0), (i * 37) % 128);
    i += 1;
  );
  best = 0; sum = 0; count = 0;
);

// The plot the timing is measured on: the geometry of a 1000x720 window, which is
// the size the plugin uses on this machine.
g_graph_margin_left = 35;
g_graph_width = 949;
g_graph_start_y = 38;
g_graph_actual_height = 602;
g_y_range_min = 0;
g_y_range_total = 127;
g_time_start = 0;
g_time_end = 30;
g_time_window = 30;
slider5 = 0;              // worst case: marks, steps and the dashed coda
case = 0; frame = 0; best = 0; sum = 0; count = 0; stored = 0;

@gfx 1000 720
gfx_clear = 1;
frames_per_case = 34;
case < 4 ? (
  frame == 0 ? timing_load(case);
  frame >= 1 && frame < 33 ? (
    t0 = time_precise();
    draw_cc_data_lines(timing_pairs(case));
    dt = (time_precise() - t0) * 1000000;
    (best == 0 || dt < best) ? best = dt;
    sum += dt; count += 1;
  );
  frame == 33 ? (
    gmem[case * 3] = best;
    gmem[case * 3 + 1] = count > 0 ? sum / count : 0;
    gmem[case * 3 + 2] = g_marks_drawn;
    case += 1;
    gmem[12] = case;
    frame = -1;
  );
  frame += 1;
);

// One frame of text, so the window is never a blank canvas someone mistakes for a
// plugin that failed to load.
gfx_setfont(1, "Arial", 14);
gfx_r = 0.85; gfx_g = 0.85; gfx_b = 0.9; gfx_a = 1;
gfx_x = 12; gfx_y = 12;
sprintf(#timing_text, "draw timing: case %d of 4   %d events   best %.0f us",
        case, timing_events(case < 4 ? case : 3), best);
gfx_drawstr(#timing_text);
'''


def build(source: Path, output: Path) -> None:
    if output.exists():
        raise ValueError('Output must be a new temporary directory')
    # The renderer lives in the plot panel; the probe extracts it from there so it
    # times the code that ships, not a copy.
    text = (source / 'ccscope_plot.jsfx-inc').read_text()
    start = text.index('function draw_cc_data_lines(')
    functions = text[start:]
    output.mkdir(parents=True)
    shutil.copy2(source / 'ccscope_utils.jsfx-inc', output / 'ccscope_utils.jsfx-inc')
    # @init comes before every definition, as in the history probe: EEL2 resolves
    # a function only if the section that holds it has already started, and a
    # definition placed before the first section is reported as undefined at its
    # call site inside @gfx.
    probe = ('desc:CCScope draw timing\noptions:gmem=CCScopeDrawTiming\n'
             'import ccscope_utils.jsfx-inc\n@init\n' + functions + CASES)
    (output / 'draw_timing.jsfx').write_text(probe)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', type=Path,
                        default=Path(__file__).resolve().parent.parent / 'ccscope')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
    print('Built native draw-timing probe')


if __name__ == '__main__':
    main()
