"""Offline grid contract/source wiring checks, not an EEL2 or host renderer test.

Run: python3 test/test_bloomscope_grid.py
"""
from pathlib import Path
import re
import unittest

SRC = Path(__file__).resolve().parents[2] / "bloomscope"


def function_body(source, name):
    """Extract an EEL2 function through the next definition/doc boundary."""
    match = re.search(rf"function {name}\([^\n]*", source)
    if not match:
        raise AssertionError(f"Missing function: {name}")
    tail = source[match.start():]
    end = re.search(r"\n(?:function |/\*\*)", tail[1:])
    return tail if end is None else tail[:end.start() + 1]


class GridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (SRC / "bloomscope.jsfx").read_text()
        cls.plot = (SRC / "bloomscope_plot.jsfx-inc").read_text()
        cls.notes = (SRC / "bloomscope_notes.jsfx-inc").read_text()
        cls.capture = (SRC / "bloomscope_capture.jsfx-inc").read_text()

    def test_appended_parameter_preserves_old_slider_meanings(self):
        self.assertIn("slider9:0<0,2,1{Full,Levels,Off}>-Audio grid", self.main)
        self.assertIn("slider8:0<0,1,1>-Clear history", self.main)
        self.assertIn("slider2:10<1,30,1>-Time window (seconds)", self.main)
        self.assertIn("cbm_init(MEM_CBM_BASE, 8)", self.main)

    def test_control_mapping_and_text(self):
        mapping = function_body(self.main, "ctl_slider_number")
        self.assertIn("i == 6 ? 9", mapping)
        self.assertIn("i == 7 ? 1 : 8", mapping)
        self.assertIn("s == 9 ? slider9", function_body(self.main, "ctl_slider_value"))
        self.assertIn("slider9 = v; sliderchange(slider9)",
                      function_body(self.main, "ctl_slider_write"))
        self.assertIn("cbm_cell(6, 4, 0, 2, 0)", self.main)
        self.assertIn('"GRID"', function_body(self.main, "ctl_key_text"))
        for text in ('"Full"', '"Levels"', '"Off"'):
            self.assertIn(text, function_body(self.main, "ev_grid_text"))
        for name in ("ctl_value_text", "ctl_item_text"):
            self.assertIn("ev_grid_text(v)", function_body(self.main, name))
        self.assertIn('"Levels"', function_body(self.main, "ctl_value_widest"))

    def test_compact_bar_keeps_toggle_words_but_hides_cycle_keys(self):
        bar = (SRC / "bloomscope_controlbar.jsfx-inc").read_text()
        keys = function_body(bar, "cbm_shows_key")
        self.assertIn("cbm_kind(i) == 2 || cbm_kind(i) == 3", keys)
        self.assertIn("cbm_has_labels()", keys)
        self.assertNotIn("cbm_kind(i) >= 2", keys)

    def test_temporal_grid_disabled_before_history_scan(self):
        grid = function_body(self.plot, "draw_panel_grid")
        self.assertIn("slider9 == 0 ? draw_beat_grid(p);", grid)
        self.assertIn("slider9 == 0 && snap_n > 0 ?", grid)

    def test_level_lines_optional_but_labels_and_borders_unconditional(self):
        grid = function_body(self.plot, "draw_panel_grid")
        self.assertIn("slider9 != 2 ? gfx_line(g_plot_x, y, g_plot_x + g_plot_w, y);", grid)
        self.assertIn('sprintf(#ev_lbl, "%d", db)', grid)
        self.assertIn("gfx_drawstr(#ev_lbl)", grid)
        self.assertIn("// Border, drawn last", grid)
        self.assertNotIn("slider9", function_body(self.plot, "draw_time_axis"))

    def test_capture_and_midi_guides_independent_of_grid(self):
        self.assertNotIn("slider9", self.capture)
        self.assertNotIn("slider9", self.notes)
        block = self.main.split("@block\n", 1)[1].split("@gfx", 1)[0]
        self.assertNotIn("slider9", block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
