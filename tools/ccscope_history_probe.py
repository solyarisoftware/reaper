#!/usr/bin/env python3
"""Build a test-only native EEL2 probe for the event ring and the renderer.

Does not launch REAPER. Output must be a new temporary Effects directory.
Results use gmem namespace CCScopeRing27: [0] checks, [1] failures, [2] done.
"""
from pathlib import Path
import argparse
import shutil


CAPTURES = '''
// Same value as the host declares; the probe owns no renderer constant of its
// own, it only lets the extracted one compile.
DOT_MIN_SPACING = 12;

function history_line(x1,y1,x2,y2) (
 history_lines+=1; history_low=min(history_low,min(y1,y2));
 history_high=max(history_high,max(y1,y2));
 x1!=x2 && y1==y2 ? history_horizontal+=1;
 x1==x2 && y1!=y2 ? history_vertical+=1;
 history_x1=x1; history_y1=y1; history_x2=x2; history_y2=y2;
);
function history_circle(x,y,r,fill) (
 history_dots+=1; history_low=min(history_low,y); history_high=max(history_high,y);
);
function history_verify(condition) ( history_checks+=1; condition==0 ? history_failures+=1; );
function history_reset_capture() (
 history_lines=0; history_dots=0; history_low=1000000; history_high=-1000000;
 history_horizontal=0; history_vertical=0;
 history_x1=0; history_y1=0; history_x2=0; history_y2=0;
);
'''

CASES = '''
history_checks=0; history_failures=0;

// geometry: 1000 px over one second, value 0..127 mapped to 127..0
mem[MEM_CC_SORTED]=0; mem[MEM_PAIR_LIST_COUNT]=1;
g_graph_margin_left=0; g_graph_width=1000; g_graph_start_y=0;
g_graph_actual_height=127; g_y_range_min=0; g_y_range_total=127;
g_time_start=1; g_time_end=2; g_time_window=1;
slider5=1;

// one event: one mark, no segment
clear_history(); add_event(1.5,0,64);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==1 && history_lines==0);

// two events: two marks and one diagonal between them
clear_history(); add_event(1.1,0,20); add_event(1.9,0,100);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==2 && history_lines==1);
history_verify(history_horizontal==0 && history_vertical==0);

// every event is a vertex: four events, three segments
clear_history();
add_event(1.1,0,64); add_event(1.3,0,0); add_event(1.5,0,127); add_event(1.7,0,70);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==4 && history_lines==3);

// an event outside the window draws nothing
clear_history(); add_event(0.5,0,64);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==0 && history_lines==0);

// Clear empties the trace in O(1) and the ring still takes events
clear_history(); history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==0 && history_lines==0);
add_event(1.5,0,64); history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==1);

// the ring wraps at its capacity, two slots an event
history_verify(event_slot(0)==MEM_EVENT_RING);
history_verify(event_slot(EVENT_CAPACITY)==MEM_EVENT_RING);
history_verify(event_slot(EVENT_CAPACITY+1)==MEM_EVENT_RING+2);
history_verify(event_count()==1);

// above the drawing budget the trace decimates, and says by how much
clear_history();
i=0; loop(4001, add_event(1 + i*0.0002, 0, i%128); i+=1;);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(g_mark_stride==2);
history_verify(history_dots==2001);
history_verify(history_lines==2000);

// every event below the budget, one mark each: the budget must not bite early
history_verify(MARK_BUDGET>=4000);

// Auto spacing: a mark every twelve pixels, so two close events give one mark
slider5=0; clear_history(); add_event(1.1,0,64); add_event(1.11,0,65);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==1);

// None: the line, no marks
slider5=2; clear_history(); add_event(1.1,0,64); add_event(1.9,0,100);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==0 && history_lines==1);
slider5=1;

clear_history();
gmem[0]=history_checks; gmem[1]=history_failures; gmem[2]=1;
'''


def build(source: Path, output: Path) -> None:
    if output.exists():
        raise ValueError('Output must be a new temporary directory')
    # The renderer lives in the plot panel; the probe extracts it from there so
    # it tests the code that ships, not a copy.
    text = (source / 'ccscope_plot.jsfx-inc').read_text()
    start = text.index('function draw_cc_data_lines(')
    functions = text[start:]
    functions = functions.replace('gfx_line(', 'history_line(').replace('gfx_circle(', 'history_circle(')
    output.mkdir(parents=True)
    shutil.copy2(source / 'ccscope_utils.jsfx-inc', output / 'ccscope_utils.jsfx-inc')
    probe = ('desc:CCScope event ring native checks\noptions:gmem=CCScopeRing27\n'
             'import ccscope_utils.jsfx-inc\n@init\n' + CAPTURES + functions + CASES +
             '\n@block\nwhile(midirecv(o,a,b,c)) (midisend(o,a,b,c););\n'
             '@gfx 320 160\ngfx_x=10;gfx_y=10;gfx_drawstr("Native event ring checks completed");\n')
    (output / 'history_checks.jsfx').write_text(probe)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path,
                        default=Path(__file__).resolve().parent.parent / 'ccscope')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
    print('Built actual-source native event ring and renderer checks')


if __name__ == '__main__':
    main()
