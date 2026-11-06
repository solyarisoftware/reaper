"""Offline checks for CCScope's palette data and its display wiring."""
import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / 'ccscope'


def test_six_palettes_define_all_sixteen_distinct_slots():
    utils = (SOURCE / 'ccscope_utils.jsfx-inc').read_text()
    body = utils.split('function init_color_palette(palette) (', 1)[1].split('// Sets gfx color', 1)[0]
    entries = re.findall(r'set_palette_color\((\d+), 0x([0-9a-f]{6})\)', body)
    assert len(entries) == 6 * 16
    for offset in range(0, len(entries), 16):
        palette = entries[offset:offset + 16]
        assert [int(index) for index, _ in palette] == list(range(16))
        assert len({rgb for _, rgb in palette}) == 16
    assert 'COLOR_PALETTE_SIZE = 16;' in utils


def test_mapping_is_order_independent_and_normalizes_cc_zero():
    utils = (SOURCE / 'ccscope_utils.jsfx-inc').read_text()
    main = (SOURCE / 'ccscope.jsfx').read_text()
    assert 'idx = (cc_num + 15) % COLOR_PALETTE_SIZE;' in utils
    assert 'assign_color_to_cc' not in utils + main
    assert 'MEM_NEXT_COLOR' not in utils + main
    slots = [(cc + 15) % 16 for cc in range(128)]
    assert (slots[0], slots[1], slots[16], slots[17], slots[127]) == (15, 0, 15, 0, 14)
    assert slots == [dict((cc, (cc + 15) % 16) for cc in reversed(range(128)))[cc]
                     for cc in range(128)]


def test_palette_parameter_is_wired_to_all_views_in_same_frame():
    main = (SOURCE / 'ccscope.jsfx').read_text()
    utils = (SOURCE / 'ccscope_utils.jsfx-inc').read_text()
    assert 'slider8:0<0,5,1{' in main
    assert 'cbm_cell(6, 1, 0, 5, 0);' in main
    assert 'slider8 = v; sliderchange(slider8);' in main
    assert main.index('ctl_apply_changes();', main.index('@gfx')) < main.index('init_color_palette(palette_choice);', main.index('@gfx'))
    assert 'v = channel % 4;' in utils
    for view in ('ccscope_plot.jsfx-inc', 'ccscope_rows.jsfx-inc'):
        assert 'get_cc_channel_color(' in (SOURCE / view).read_text()
    assert 'cbm_menu_fit(palette_menu_w + 22);' in main


def test_daybreak_and_twilight_common_controllers_and_palette_sets():
    utils = (SOURCE / 'ccscope_utils.jsfx-inc').read_text()
    body = utils.split('function init_color_palette(palette) (', 1)[1].split('// Sets gfx color', 1)[0]
    colors = re.findall(r'set_palette_color\(\d+, 0x([0-9a-f]{6})\)', body)
    expected = (
        ('ff4545', 'ffe23b', '35e65b',
         'ff4545 35e65b ffe23b 5592ff ffffff 27dfe8 f159e7 ff9636 '
         'a6ed3b bb79ff 399dff ff80b3 39d6a0 ff7661 d1ab47 bed2eb'),
        ('e77878', 'dfc970', '78c88b',
         'e77878 78c88b dfc970 83a8e6 dedede 72c5c9 c88bc2 dfa171 '
         'b4cb80 ae94d6 83bce5 dc9fba 83c5ac d49788 cbb088 adbacb'),
    )
    for offset, (red, yellow, green, original_set) in zip((0, 16), expected):
        palette = colors[offset:offset + 16]
        assert (palette[0], palette[10], palette[6]) == (red, yellow, green)  # CC1, CC11, CC7
        assert set(palette) == set(original_set.split())
        white = tuple(bytes.fromhex(palette[4]))
        assert min(white) >= 220 and max(white) - min(white) == 0
