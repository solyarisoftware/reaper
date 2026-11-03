#!/usr/bin/env python3
"""Build a test-only native EEL2 retention/rendering probe from actual sources.

Does not launch REAPER. Output must be a new temporary Effects directory.
Results use gmem namespace CCScopeHistory5: [0] checks, [1] failures, [2] done.
"""
from pathlib import Path
import argparse
import shutil


def build(source: Path, output: Path) -> None:
    if output.exists():
        raise ValueError('Output must be a new temporary directory')
    text = (source / 'ccscope.jsfx').read_text()
    start = text.index('function draw_temporal_point(')
    end = text.index('/**\n * Draws status information text', start)
    functions = text[start:end].replace('gfx_line(', 'history_line(').replace('gfx_circle(', 'history_circle(')
    captures = '''
function history_line(x1,y1,x2,y2) (
 history_lines+=1; history_low=min(history_low,min(y1,y2));
 history_high=max(history_high,max(y1,y2));
);
function history_circle(x,y,r,fill) (
 history_dots+=1; history_low=min(history_low,y); history_high=max(history_high,y);
 history_dots<=64 ? gmem[200+history_dots]=y;
);
function history_verify(condition) ( history_checks+=1; condition==0 ? history_failures+=1; );
function history_slot(t,p) (
 MEM_TIME_HISTORY+(p*TIME_HISTORY_BUCKETS+floor(t*TIME_HISTORY_HZ)%TIME_HISTORY_BUCKETS)*TIME_HISTORY_STRIDE;
);
function history_reset_capture() (
 history_lines=0; history_dots=0; history_low=1000000; history_high=-1000000;
);
'''
    cases = '''
history_checks=0; history_failures=0;
// 40,000 messages/s total for 32 seconds. Each pair owns its entire time ring.
i=0;
loop(64001,
 t=i/2000; p=0;
 loop(20, add_temporal_history(t,p,i%128); p+=1; );
 i+=1;
);
p=0;
loop(20,
 tick=20;
 loop(301,
  b=MEM_TIME_HISTORY+(p*TIME_HISTORY_BUCKETS+tick%TIME_HISTORY_BUCKETS)*TIME_HISTORY_STRIDE;
  history_verify(mem[b]==tick+1);
  history_verify(mem[b+1]==g_history_epoch);
  tick+=1;
 );
 p+=1;
);
// Every dense key has a distinct bucket, including CC127/channel16.
i=0;
loop(2048, add_temporal_history(32.05,i,i%128); i+=1; );
i=0;
loop(2048,
 b=history_slot(32.05,i);
 history_verify(floor(mem[b+4]/128)==i%128);
 i+=1;
);
// Sparse pair does not compete with dense ones for event capacity.
add_temporal_history(10.01,2047,64);
history_verify(mem[history_slot(10.01,2047)]==101);
// Endpoints and extrema order are retained, including a spike returning to zero.
add_temporal_history(31.01,2000,64);
add_temporal_history(31.02,2000,127);
add_temporal_history(31.03,2000,0);
add_temporal_history(31.04,2000,70);
b=history_slot(31.01,2000);
history_verify(mem[b+4]==64+70*128);
history_verify(mem[b+5]==127*128);
history_verify(mem[b+6]==1);
// O(1) Clear followed by another event inside the same tick.
old_epoch=g_history_epoch; clear_history();
history_verify(g_history_epoch==old_epoch+1);
add_temporal_history(31.05,2000,50);
history_verify(mem[b+1]==g_history_epoch);
history_verify(mem[b+4]==50+50*128);
history_verify(mem[b+5]==50+50*128);
history_verify(mem[b+2]==31.05);
// Execute the actual production renderer with only the gfx sink intercepted.
mem[MEM_CC_SORTED]=0; mem[MEM_PAIR_LIST_COUNT]=1;
g_graph_margin_left=0; g_graph_width=1000; g_graph_start_y=0;
g_graph_actual_height=127; g_y_range_min=0; g_y_range_total=127;
slider5=1; clear_history();
add_temporal_history(1.08,0,64);
g_time_start=1; g_time_end=2; g_time_window=1;
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_lines==0); history_verify(history_dots==1);
// A partially intersected left bucket must retain its min/max envelope.
clear_history();
add_temporal_history(1.001,0,0);
add_temporal_history(1.08,0,127);
add_temporal_history(1.09,0,0);
g_time_start=1.05; g_time_window=0.95;
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_low==0); history_verify(history_high==127);
// Repeated extrema at the same timestamp and both extrema orders.
clear_history();
add_temporal_history(1.08,0,64); add_temporal_history(1.08,0,0);
add_temporal_history(1.08,0,127); add_temporal_history(1.08,0,64);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_low==0); history_verify(history_high==127);
// Both extrema orders must reach the renderer in order, not just global bounds.
// Y is 127-value: endpoints 64/70 => 63/57; min/max 0/127 => 127/0.
clear_history();
add_temporal_history(1.01,0,64); add_temporal_history(1.02,0,0);
add_temporal_history(1.03,0,127); add_temporal_history(1.04,0,70);
g_time_start=1; g_time_end=2; g_time_window=1;
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==4 && history_lines==3);
history_verify(gmem[201]==63); history_verify(gmem[202]==127);
history_verify(gmem[203]==0); history_verify(gmem[204]==57);
clear_history();
add_temporal_history(1.01,0,64); add_temporal_history(1.02,0,127);
add_temporal_history(1.03,0,0); add_temporal_history(1.04,0,70);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==4 && history_lines==3);
history_verify(gmem[201]==63); history_verify(gmem[202]==0);
history_verify(gmem[203]==127); history_verify(gmem[204]==57);
// Clear invalidates rendering without deleting the persistent pair list.
clear_history(); history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_lines==0 && history_dots==0);
// Delayed input must not resurrect a bucket that has aged out of the window.
add_temporal_history(1.08,0,127);
g_time_start=32; g_time_end=62; g_time_window=30;
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_lines==0 && history_dots==0);
gmem[0]=history_checks; gmem[1]=history_failures; gmem[2]=1;
'''
    output.mkdir(parents=True)
    shutil.copy2(source / 'ccscope_utils.jsfx-inc', output / 'ccscope_utils.jsfx-inc')
    probe = ('desc:CCScope temporal history native checks\noptions:gmem=CCScopeHistory5\n'
             'import ccscope_utils.jsfx-inc\n@init\n' + captures + functions + cases +
             '\n@block\nwhile(midirecv(o,a,b,c)) (midisend(o,a,b,c););\n'
             '@gfx 320 160\ngfx_x=10;gfx_y=10;gfx_drawstr("Native history checks completed");\n')
    (output / 'history_checks.jsfx').write_text(probe)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent.parent / 'MIDI/ccscope')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
    print('Built actual-source native temporal history and renderer checks')


if __name__ == '__main__':
    main()
