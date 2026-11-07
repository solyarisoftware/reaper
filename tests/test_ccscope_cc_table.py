"""Offline checks for CCScope's CC table: the user's colours and names.

The table is data the user edits by hand, so what is worth asserting is not what
the colours look like -- that changes at the user's taste -- but the invariants a
hand edit can break silently:

  - a CC that is listed twice, or is missing, or out of range,
  - an rgb that is neither a colour nor -1,
  - a name that no longer fits the space the status line gives it,
  - a file that is imported without opening a section (REAPER then refuses the
    import with "has no @init or other code"),
  - a file that is not declared in @provides (ReaPack would not install it).
"""
import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / 'ccscope'
TABLE = SOURCE / 'ccscope_cc_table.jsfx-inc'
UTILS = SOURCE / 'ccscope_utils.jsfx-inc'
MAIN = SOURCE / 'ccscope.jsfx'

NAME_MAX = 12     # matches the width the status line and the rows give it


def table_lines():
    return TABLE.read_text().splitlines()


def entries():
    """(cc, rgb, name) of every cc_entry() line, in file order."""
    text = TABLE.read_text()
    return [(int(cc), rgb, name)
            for cc, rgb, name in re.findall(r'^cc_entry\(\s*(\d+),\s*(-?\w+),\s*"([^"]*)"\);',
                                            text, re.M)]


def ladder():
    text = TABLE.read_text()
    return [(int(slot), rgb) for slot, rgb in
            re.findall(r'^cc_fallback\(\s*(\d+),\s*(0x[0-9a-f]{6})\);', text, re.M)]


def test_every_cc_is_listed_exactly_once():
    listed = [cc for cc, _, _ in entries()]
    assert listed == list(range(128))


def test_each_entry_is_a_colour_or_the_ladder():
    for cc, rgb, _ in entries():
        assert rgb == '-1' or re.fullmatch(r'0x[0-9a-f]{6}', rgb), (cc, rgb)


def test_names_fit_the_space_the_row_gives_them():
    for cc, _, name in entries():
        assert len(name) <= NAME_MAX, (cc, name)


def test_the_ladder_is_sixteen_distinct_colours():
    slots = ladder()
    assert [s for s, _ in slots] == list(range(16))
    assert len({c for _, c in slots}) == 16


def test_the_colours_the_user_picked_are_the_ones_shipped():
    """A guard, not a rule: these are the four the owner asked for by name."""
    chosen = {cc: rgb for cc, rgb, _ in entries() if rgb != '-1'}
    assert chosen[1] == '0xff4d4d'    # mod wheel, red
    assert chosen[11] == '0x4ade80'   # expression, green
    assert chosen[17] == '0xffe03b'   # knob 1, yellow
    assert chosen[21] == '0x1feef9'   # knob 5, cyan


def test_the_file_opens_a_section():
    # Measured: importing a file that opens no section fails with
    # "import: '<file>' has no @init or other code", even when the import
    # already sits inside @init.
    assert any(line.strip() == '@init' for line in table_lines())


def test_the_file_is_imported_and_declared_for_repack():
    main = MAIN.read_text()
    assert 'import ccscope_cc_table.jsfx-inc' in main
    provides = main.split('// @provides', 1)[1].split('// @', 1)[0]
    assert 'ccscope_cc_table.jsfx-inc' in provides


def test_no_palette_or_history_buffer_survives_anywhere():
    for path in SOURCE.glob('*.jsfx*'):
        text = path.read_text()
        for gone in ('init_color_palette', 'set_palette_color', 'MEM_COLOR_PALETTE',
                     'MEM_HISTORY_BASE', 'MEM_HISTORY_WRITE', 'add_to_history_with_channel'):
            assert gone not in text, (path.name, gone)


def test_the_colour_is_resolved_channel_then_cc_then_ladder():
    utils = UTILS.read_text()
    body = utils.split('function get_cc_channel_color(', 1)[1].split('\n);', 1)[0]
    # the order is the rule: a channel entry wins, the CC entry next, the ladder last
    assert body.index('MEM_PAIR_RGB') < body.index('MEM_CC_RGB') < body.index('MEM_FALLBACK_RGB')


def test_the_shade_moves_luminance_not_channels():
    """The old shade multiplied sRGB, which buries blue: it must go via Y."""
    utils = UTILS.read_text()
    body = utils.split('function get_cc_channel_color(', 1)[1].split('\n);', 1)[0]
    assert 'Y_FLOOR' in body
    assert 'srgb_to_lin(' in body and 'lin_to_srgb(' in body
    # darker and lighter scale Y; the old code multiplied the rgb triple instead
    assert 't = max(Y_FLOOR, y * 0.55)' in body
    assert 't = (y + (1 - y) * 0.50)' in body
