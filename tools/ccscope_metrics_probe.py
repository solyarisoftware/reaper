#!/usr/bin/env python3
"""Build actual-source native Timing checks; never launch REAPER or deploy files.

Use a new WSL temporary directory as --output. An authorized native runner must
load metrics_checks.jsfx with its copied includes. gmem CCScopeMetricsTiming:
[0] checks, [1] failures, [2] done (1), [3] first failing check ordinal,
[4] first failing case (1-based, see CASES), [5] total cases.
These are EEL2 tests, not an offline emulation result. The generator's reference
only supplies independently computed expected numbers to the native assertions.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import shutil


# name, acquisition-order timestamps, now. Values repeat deliberately: Motion=0.
CASES = [
    ('uniform', [i / 100 for i in range(100)], 1.0),
    ('coincident batches', [i / 10 for i in range(10) for _ in range(10)], 1.0),
    ('empty', [], 1.0),
    ('one event', [0.5], 1.0),
    ('one interval', [0.0, 1.0], 1.0),
    ('positive microsecond interval', [0.0, 0.000001], 1.0),
    ('three filtered intervals', [0.0, 0.1, 0.2, 0.3], 1.0),
    ('four filtered intervals', [0.0, 0.1, 0.2, 0.3, 0.4], 1.0),
    ('zero timestamps', [0.0] * 8, 0.0),
    ('closed boundaries', [0.999, 1.0, 1.5, 2.0, 2.001], 2.0),
    ('no cross-cutoff interval', [0.9, 1.2], 2.0),
    ('future breaks adjacency', [1.1, 2.1, 1.4, 1.5], 2.0),
    ('past breaks adjacency', [1.1, 0.9, 1.4, 1.5], 2.0),
    ('negative timestamps', [-0.2, 0.0, 0.1], 0.5),
    ('non-monotonic', [0.0, 0.3, 0.2, 0.2, 0.4], 1.0),
    ('filtered pause', [0.0, 0.1, 0.2, 0.3, 0.4, 0.9], 1.0),
    ('exact ranks 20', [i * (i + 1) / 2000 for i in range(21)], 1.0),
    ('exact ranks 21', [i * (i + 1) / 2000 for i in range(22)], 1.0),
    ('capacity descending', [sum(range(500 - i, 500)) / 125000 for i in range(500)], 1.0),
    ('capacity repeated', [i // 7 / 100 for i in range(500)], 1.0),
    ('capacity permuted', [sum((j * 137) % 499 + 1 for j in range(i)) / 125000
                           for i in range(500)], 1.0),
]


def intervals(times, now):
    """Independent oracle: invalid endpoints break adjacency; backwards deltas drop."""
    result, previous = [], None
    for time in times:
        if time < 0 or not now - 1 <= time <= now:
            previous = None
            continue
        if previous is not None and time >= previous:
            result.append((time - previous) * 1000)
        previous = time
    return sorted(result)


HELPERS = '''
function metrics_verify(ok) (
  gmem[0] += 1;
  !ok ? (
    gmem[1] += 1;
    gmem[3] == 0 ? (gmem[3] = gmem[0]; gmem[4] = metrics_case;);
  );
);
function metrics_close(actual, expected) (
  metrics_verify(abs(actual - expected) < 0.00001);
);
function metrics_reset() (
  metrics_base_ptr = get_cc_channel_metrics_base(0, 0);
  mem[metrics_base_ptr] = 0; mem[metrics_base_ptr + 1] = -1;
);
'''


def checks():
    text = ['gmem[0]=0; gmem[1]=0; gmem[2]=0; gmem[3]=0; gmem[4]=0;']
    for case, (name, times, now) in enumerate(CASES, 1):
        raw = intervals(times, now)
        text += [f'// {case}: {name}', f'metrics_case={case}; metrics_reset();',
                 f'g_metrics_now={now:.17g};']
        text += [f'update_metrics_for_cc_channel(0,0,64,{t:.17f});' for t in times]
        text += ['get_timing_cc_channel(0,0);',
                 f'metrics_verify(g_timing_intervals=={len(raw)});',
                 f'metrics_verify(get_events_per_second_cc_channel(0,0)=={sum(t >= now - 1 for t in times)});',
                 'metrics_verify(get_rate_per_second_cc_channel(0,0)==0);']
        if raw:
            for field, expected in [('p50', raw[math.ceil(len(raw) * .5) - 1]),
                                    ('p95', raw[math.ceil(len(raw) * .95) - 1]),
                                    ('min', raw[0]), ('max', raw[-1]),
                                    ('coincident', 100 * raw.count(0) / len(raw))]:
                text.append(f'metrics_close(g_timing_{field},{expected:.17f});')
            # Every sorted output element, not just two quantiles: pathological
            # permutations/repeated keys cannot hide a broken heap implementation.
            text += [f'metrics_close(mem[MEM_TIMING_SCRATCH+{i}],{v:.17f});'
                     for i, v in enumerate(raw)]
        else:
            text += ['metrics_verify(g_timing_p50==-1 && g_timing_p95==-1);',
                     'metrics_verify(g_timing_min==-1 && g_timing_max==-1 && g_timing_coincident==-1);',
                     'metrics_verify(g_timing_jitter==-1 && g_timing_jitter_intervals==0);']
        if raw:
            accepted = [v for v in raw if v <= raw[0] * 4]
            mean = sum(accepted) / len(accepted)
            jitter = (math.sqrt(sum((v - mean) ** 2 for v in accepted) / len(accepted))
                      if len(accepted) >= 4 else -1)
            text += [f'metrics_verify(g_timing_jitter_intervals=={len(accepted)});',
                     f'metrics_close(g_timing_jitter,{jitter:.17f});']
        if name == 'filtered pause':
            text += ['metrics_close(g_timing_jitter,0);',
                     'metrics_verify(g_timing_jitter_intervals==4);']
    text += ['''
// Pruning must not remove an interior invalid endpoint and invent an interval.
metrics_case=99; metrics_reset();
update_metrics_for_cc_channel(0,0,64,1.1);
update_metrics_for_cc_channel(0,0,64,0.9);
update_metrics_for_cc_channel(0,0,64,1.4);
g_metrics_now=2; get_timing_cc_channel(0,0);
metrics_verify(g_timing_intervals==0);
prune_old_metrics(2); get_timing_cc_channel(0,0);
metrics_verify(g_timing_intervals==0 && mem[metrics_base_ptr]==3);
// Ordered expired prefix, repeats and normal deltas preserve Messages/Motion.
metrics_reset();
update_metrics_for_cc_channel(0,0,60,0.5);
update_metrics_for_cc_channel(0,0,65,1.0);
update_metrics_for_cc_channel(0,0,65,1.1);
update_metrics_for_cc_channel(0,0,70,1.2);
metrics_verify(get_events_per_second_cc_channel(0,0)==3);
metrics_verify(get_rate_per_second_cc_channel(0,0)==10);
prune_old_metrics(2);
metrics_verify(mem[metrics_base_ptr]==3);
metrics_verify(get_events_per_second_cc_channel(0,0)==3);
metrics_verify(get_rate_per_second_cc_channel(0,0)==10);
// Full buffer rejects overflow, can prune then accept up to capacity again.
metrics_reset(); metrics_i=0;
loop(MAX_EVENTS_PER_CC+1,
  update_metrics_for_cc_channel(0,0,64,metrics_i/1000); metrics_i+=1;
);
metrics_verify(mem[metrics_base_ptr]==MAX_EVENTS_PER_CC);
g_metrics_now=1; get_timing_cc_channel(0,0);
metrics_verify(g_timing_intervals==MAX_EVENTS_PER_CC-1);
prune_old_metrics(1.25); metrics_verify(mem[metrics_base_ptr]==250);
metrics_i=0; loop(251, update_metrics_for_cc_channel(0,0,64,1.25); metrics_i+=1;);
metrics_verify(mem[metrics_base_ptr]==MAX_EVENTS_PER_CC);
// Actual window function: Freeze pins now despite the advancing audio clock.
metrics_case=100; metrics_reset();
update_metrics_for_cc_channel(0,0,64,1.0);
update_metrics_for_cc_channel(0,0,64,2.0);
g_prev_freeze=1; g_freeze_time=2; g_clock_sec=20; slider3=30;
calculate_time_window(); g_metrics_now=g_time_end; get_timing_cc_channel(0,0);
metrics_close(g_timing_p95,1000); metrics_verify(g_timing_intervals==1);
g_clock_sec=30; calculate_time_window(); g_metrics_now=g_time_end;
get_timing_cc_channel(0,0); metrics_close(g_timing_p95,1000);
slider3=1; calculate_time_window(); g_metrics_now=g_time_end;
get_timing_cc_channel(0,0); metrics_close(g_timing_p95,1000);
g_prev_freeze=0; g_clock_sec=2.0001; calculate_time_window(); g_metrics_now=g_time_end;
get_timing_cc_channel(0,0); metrics_verify(g_timing_intervals==0 && g_timing_p50==-1);
// Prune at the same cutoff preserves raw stats for ordered normal acquisition.
metrics_reset(); update_metrics_for_cc_channel(0,0,64,1);
update_metrics_for_cc_channel(0,0,64,1.5); update_metrics_for_cc_channel(0,0,64,2);
g_metrics_now=2; prune_old_metrics(2); get_timing_cc_channel(0,0);
metrics_verify(g_timing_intervals==2); metrics_close(g_timing_p50,500);
g_metrics_now=2.0001; get_timing_cc_channel(0,0);
metrics_verify(g_timing_intervals==1); metrics_close(g_timing_p50,500);
init_metrics(); get_timing_cc_channel(0,0);
metrics_verify(g_timing_intervals==0 && g_timing_p50==-1);
''', f'gmem[5]={len(CASES)}; gmem[2]=1;']
    return '\n'.join(text)


# A separate native cost probe: no sorting transcription and no correctness claim.
# Each frame measures the production function over all pairs, not one pair scaled.
BENCHMARK_INIT = """
metrics_pair=0;
loop(64,
  metrics_time=0; metrics_i=0;
  loop(MAX_EVENTS_PER_CC,
    update_metrics_for_cc_channel(floor(metrics_pair/16),metrics_pair%16,64,metrics_time);
    metrics_time += ((metrics_i*137)%499+1)/125000;
    metrics_i+=1;
  );
  metrics_pair+=1;
);
g_metrics_now=1; metrics_case=0; metrics_frame=0;
metrics_best=1000000; metrics_sum=0; gmem[6]=0; gmem[7]=MAX_EVENTS_PER_CC;
"""
BENCHMARK_FRAME = """
metrics_case<3 ? (
  metrics_pairs=metrics_case==0 ? 1 : metrics_case==1 ? 16 : 64;
  metrics_start=time_precise(); metrics_pair=0;
  loop(metrics_pairs,
    get_timing_cc_channel(floor(metrics_pair/16),metrics_pair%16);
    metrics_pair+=1;
  );
  metrics_us=(time_precise()-metrics_start)*1000000;
  // Two warm-up frames, then 32 samples per case; best and mean in microseconds.
  metrics_frame>=2 ? (
    metrics_best=min(metrics_best,metrics_us); metrics_sum+=metrics_us;
  );
  metrics_frame+=1;
  metrics_frame==34 ? (
    gmem[metrics_case]=metrics_best; gmem[3+metrics_case]=metrics_sum/32;
    metrics_case+=1; gmem[6]=metrics_case;
    metrics_frame=0; metrics_best=1000000; metrics_sum=0;
  );
);
gfx_x=10; gfx_y=10; gfx_printf("Timing cost: %d/3 cases",gmem[6]);
"""


def build(source: Path, output: Path, benchmark: bool = False) -> Path:
    if output.exists():
        raise ValueError('Use a new temporary output directory')
    output.mkdir(parents=True)
    for name in ('ccscope_utils.jsfx-inc', 'ccscope_metrics.jsfx-inc', 'ccscope_plot.jsfx-inc'):
        shutil.copy2(source / name, output / name)
    namespace = 'CCScopeMetricsCost' if benchmark else 'CCScopeMetricsTiming'
    target = output / ('metrics_cost.jsfx' if benchmark else 'metrics_checks.jsfx')
    init = BENCHMARK_INIT if benchmark else HELPERS + checks()
    frame = (BENCHMARK_FRAME if benchmark else
             'gfx_x=10;gfx_y=10;'
             'gfx_printf("Timing: %d checks, %d failures, first %d case %d",'
             'gmem[0],gmem[1],gmem[3],gmem[4]);\n')
    target.write_text('desc:CCScope native Timing probe\noptions:gmem=' + namespace + '\n'
                      'import ccscope_utils.jsfx-inc\nimport ccscope_metrics.jsfx-inc\n'
                      'import ccscope_plot.jsfx-inc\n@init\n' + init +
                      '\n@block\nwhile(midirecv(o,a,b,c)) (midisend(o,a,b,c););\n'
                      '@gfx 400 80\n' + frame)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent.parent / 'ccscope')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--benchmark', action='store_true',
                        help='Build a separate native 1/16/64-pair, 500-event cost probe')
    args = parser.parse_args()
    print(build(args.source, args.output, args.benchmark))


if __name__ == '__main__':
    main()
