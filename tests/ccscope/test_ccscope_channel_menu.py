"""Offline CH menu geometry checks; native REAPER interaction is separate."""
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def test_channel_menu_geometry_and_resize():
    source = (ROOT / 'ccscope/ccscope_controlbar.jsfx-inc').read_text()
    body = source.split('function cbm_menu_fit_rows(', 1)[1].split('\n);', 1)[0]
    rows_expr = re.search(r'rows = (.*?);', body, re.S).group(1)
    rows_expr = rows_expr.replace('mem[g_cbm_base + CBM_MENU_COUNT]', 'count')
    rows_expr = rows_expr.replace('mem[g_cbm_base + CBM_ST_ROW]', 'row_height')
    def rows(height):
        return eval(rows_expr, {'__builtins__': {}, 'min': min, 'floor': math.floor},
                    dict(limit=17, count=17, gfx_h=height, y=33, row_height=15))
    assert rows(294) == 17  # 33 + 17*15 + 4 frame + 2 shadow
    assert rows(293) == 16
    assert rows(114) == 5
    assert rows(53) == 0
    assert '(rows < 1 || gfx_w < 3)' in body
    assert 'gfx_w - width - 2' in body
    assert 'mem[g_cbm_base + CBM_MENU_COUNT] - rows' in body
    assert 'cur - floor(rows / 2)' in body


def test_only_channel_menu_is_refitted_before_input_and_after_opening():
    main = (ROOT / 'ccscope/ccscope.jsfx').read_text()
    pipeline = main.split('ctl_layout();', 1)[1].split('ctl_apply_changes();', 1)[0]
    before, after = pipeline.split('cbm_mouse();', 1)
    assert 'cbm_open() == 2 ? ( cbm_menu_fit_rows(17, 0); );' in before
    assert 'cbm_open() == 2 ? ( cbm_menu_fit_rows(17, previous_menu != 2); );' in after
    assert 'palette_menu_w' not in after      # the palette cell is gone
