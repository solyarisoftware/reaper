#!/usr/bin/env python3
"""Build a test-only native EEL2 probe for the event ring and the renderer.

Does not launch REAPER. Output must be a new temporary Effects directory.
Results use gmem namespace CCScopeRing27: [0] checks, [1] failures, [2] done,
[3] the ordinal of the first failing check (0 when every check passes).
"""
from pathlib import Path
import argparse
import shutil


CAPTURES = '''
function history_line(x1,y1,x2,y2) (
 history_lines+=1; history_low=min(history_low,min(y1,y2));
 history_high=max(history_high,max(y1,y2));
 x1!=x2 && y1==y2 ? history_horizontal+=1;
 x1==x2 && y1!=y2 ? (
   // A mark drawn as a tick is a vertical line too. It is the only vertical of
   // exactly 2*MARK_TICK_HALF px: a step vertical spans a value difference, and
   // the cases below keep those far from that length.
   abs(y2-y1)==2*MARK_TICK_HALF ? history_ticks+=1 : history_vertical+=1;
 );
 x1!=x2 && y1!=y2 ? history_diagonal+=1;
 history_lines==1 ? (
   history_fx1=x1; history_fy1=y1; history_fx2=x2; history_fy2=y2;
 );
 history_x1=x1; history_y1=y1; history_x2=x2; history_y2=y2;
);
function history_circle(x,y,r,fill) (
 history_dots+=1; history_radius=r;
 history_low=min(history_low,y); history_high=max(history_high,y);
);
function history_verify(condition) (
 history_checks+=1;
 condition==0 ? (
   history_failures+=1;
   history_failures==1 ? history_fail_at=history_checks;
 );
);
function history_reset_capture() (
 history_lines=0; history_dots=0; history_low=1000000; history_high=-1000000;
 history_horizontal=0; history_vertical=0; history_ticks=0; history_diagonal=0;
 history_radius=0; history_fx1=0; history_fy1=0; history_fx2=0; history_fy2=0;
 history_x1=0; history_y1=0; history_x2=0; history_y2=0;
);
'''

CASES = '''
history_checks=0; history_failures=0; history_fail_at=0;

// geometry: 1000 px over one second, value 0..127 mapped to 127..0
mem[MEM_CC_SORTED]=0; mem[MEM_PAIR_LIST_COUNT]=1;
g_graph_margin_left=0; g_graph_width=1000; g_graph_start_y=0;
g_graph_actual_height=127; g_y_range_min=0; g_y_range_total=127;
g_time_start=1; g_time_end=2; g_time_window=1;
slider5=1;

// an untouched pair is not visible: shared memory starts zeroed, and a zero
// there would read as slot 0, so a hidden pair's events would be drawn
history_verify(mem[MEM_PLOT_SLOT+7]==-1);

// Points only: one event, one mark, no line at all
slider5=2; clear_history(); add_event(1.5,0,64);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==1 && history_lines==0);

// A step, not a ramp: hold at the previous value, then jump. One horizontal and
// one vertical, never a diagonal.
slider5=1; clear_history(); add_event(1.1,0,20); add_event(1.9,0,100);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==2);
history_verify(history_horizontal==1 && history_vertical==1);
history_verify(history_diagonal==0 && history_lines==2);
// the hold runs at the PREVIOUS value (20 -> y 107), from x 100 to x 900
history_verify(abs(history_fx1-100)<0.001 && abs(history_fy1-107)<0.001);
history_verify(abs(history_fx2-900)<0.001 && abs(history_fy2-107)<0.001);
// and the change is a vertical at the new event, up to the new value (100 -> 27)
history_verify(abs(history_x1-900)<0.001 && abs(history_y1-107)<0.001);
history_verify(abs(history_x2-900)<0.001 && abs(history_y2-27)<0.001);

// every event is a vertex: four events, three holds and three changes
clear_history();
add_event(1.1,0,64); add_event(1.3,0,0); add_event(1.5,0,127); add_event(1.7,0,70);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==4);
history_verify(history_horizontal==3 && history_vertical==3);
history_verify(history_diagonal==0);

// an unchanged value draws the hold and no change
clear_history(); add_event(1.1,0,50); add_event(1.9,0,50);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==2 && history_horizontal==1 && history_vertical==0);

// the mark adapts to the spacing, the count never does: 4 px apart is a tick,
// 8 px apart is a filled circle of radius 2
slider5=2; clear_history(); add_event(1.1,0,64); add_event(1.104,0,65);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==1 && history_ticks==1 && history_lines==1);
clear_history(); add_event(1.1,0,64); add_event(1.108,0,66);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==2 && history_ticks==0 && history_radius==2);

// the coda: the held value continues dashed after the last event, at that value
slider5=0; clear_history(); add_event(1.1,0,20); add_event(1.5,0,100);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==2 && history_vertical==1);
history_verify(history_horizontal==1+ceil(500/(CODA_DASH_ON+CODA_DASH_OFF)));
history_verify(history_diagonal==0);
history_verify(abs(history_y1-27)<0.001 && abs(history_y2-27)<0.001);
history_verify(abs(history_x2-1000)<0.001);

// no coda, and no line at all, in the other two modes
slider5=1; history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_lines==2 && history_vertical==1);
slider5=2; history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_lines==0 && history_dots==2);

// the tail survives the window: the last event is older than the window, so the
// value held since then is drawn across the whole width -- a blank plot after WIN
// seconds of silence would say the value is gone, and it is not
slider5=0; clear_history(); store_cc_channel_value(0,0,90); add_event(0.5,0,90);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==0 && history_vertical==0 && history_diagonal==0);
history_verify(history_horizontal==ceil(1000/(CODA_DASH_ON+CODA_DASH_OFF)));
history_verify(abs(history_fx1)<0.001);
history_verify(abs(history_y1-37)<0.001 && abs(history_y2-37)<0.001);

// an event outside the window draws nothing when the tail is off
slider5=1; clear_history(); add_event(0.5,0,64);
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

// a filter that hides a pair must not truncate the window: the visible events
// sit at 1.1 and 1.3, with a hidden one in between
clear_history();
add_event(1.1,0,20); add_event(1.2,1,30); add_event(1.3,0,100);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(history_dots==2 && history_diagonal==0);
history_verify(abs(history_x2-300)<0.001 && abs(history_y2-27)<0.001);

// above the drawing budget the STEPS decimate and the trace says by how much;
// the marks still count one per event, as ticks at this density
clear_history();
i=0; loop(4001, add_event(1 + i*0.0002, 0, i%128); i+=1;);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(g_segment_stride==2);
history_verify(g_marks_drawn==4001 && g_events_in_window==4001);
history_verify(history_dots==1 && history_ticks==4000);
history_verify(history_horizontal==2000 && history_vertical==2000);

// at exactly the budget nothing is skipped
clear_history();
i=0; loop(4000, add_event(1 + i*0.0002, 0, i%128); i+=1;);
history_reset_capture(); draw_cc_data_lines(1);
history_verify(g_segment_stride==1);
history_verify(history_vertical==3999 && history_ticks==3999);

// the constants are the ones the geometry above assumes
history_verify(MARK_CIRCLE_MIN>4);
history_verify(SEGMENT_BUDGET>=8000);

slider5=1; clear_history();
gmem[0]=history_checks; gmem[1]=history_failures; gmem[2]=1; gmem[3]=history_fail_at;
'''


def build(source: Path, output: Path) -> None:
    if output.exists():
        raise ValueError('Output must be a new temporary directory')
    # The renderer lives in the plot panel; the probe extracts it from there so
    # it tests the code that ships, not a copy.
    text = (source / 'ccscope_plot.jsfx-inc').read_text()
    # from plot_y: the renderer calls it, and the probe owns no copy of the mapping
    start = text.index('function plot_y(')
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
