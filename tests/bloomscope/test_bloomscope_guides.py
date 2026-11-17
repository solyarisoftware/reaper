"""Guide-mode and paint-order contracts, not a host renderer/CPU test."""
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[2] / "bloomscope"


class GuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (SRC / "bloomscope.jsfx").read_text()
        cls.notes = (SRC / "bloomscope_notes.jsfx-inc").read_text()

    def test_appended_opt_in_out_does_not_repurpose_existing_parameters(self):
        self.assertIn("slider9:0<0,2,1{Full,Levels,Off}>-Audio grid", self.main)
        self.assertIn("slider10:2<0,2,1{Off,Plot only,Linked to MIDI}>-MIDI guides", self.main)
        for name in ("bloomscope_capture.jsfx-inc", "bloomscope_midi.jsfx-inc"):
            self.assertNotIn("slider10", (SRC / name).read_text())
        self.assertNotIn("slider9", self.notes)

    def test_off_hides_plot_lines_and_heads_not_strip_heads(self):
        guide = self.notes.split("function draw_note_guide(", 1)[1].split("function draw_note_plot_head(", 1)[0]
        head = self.notes.split("function draw_note_plot_head(", 1)[1].split("function note_heading_text(", 1)[0]
        self.assertIn("slider10 > 0", guide)
        self.assertIn("slider10 > 0", head)
        glyph = self.notes.split("function draw_note_arrow(", 1)[1].split("function draw_guide_line(", 1)[0]
        self.assertNotIn("slider10", glyph)
        self.assertIn("draw_note_arrow(x1, y, g_note_marker_h, 0)", self.notes)

    def test_linked_extension_joins_marker_and_crosses_split_gap(self):
        self.assertIn("slider10 == 2 ? (", self.notes)
        self.assertIn("draw_guide_line(x, bottom, target_y, off)", self.notes)
        self.assertIn("draw_guide_line(x, g_panel_y0 + g_panel_h, g_panel_y1, off)", self.notes)
        self.assertIn("target - g_note_marker_h", self.notes)
        self.assertIn("target + g_note_marker_h", self.notes)
        self.assertIn("event_colour(off, 0.16)", self.notes)

    def test_coincident_events_have_ordered_continuous_and_dashed_passes(self):
        self.assertIn("loop(2,", self.notes)
        self.assertIn("p == 0 && note_field(k, 7)", self.notes)
        self.assertIn("p == 1 && note_field(k, 5) == 1", self.notes)
        self.assertIn("y += 6", self.notes)
        self.assertIn("min(y + 3, bottom)", self.notes)
        self.assertLess(self.notes.index("loop(2,"), self.notes.index("draw_note_arrow(x1"))

    def test_native_context_menu_and_larger_axis_labels(self):
        help_source = (SRC / "bloomscope_help.jsfx-inc").read_text()
        layout = (SRC / "bloomscope_layout.jsfx-inc").read_text()
        plot = (SRC / "bloomscope_plot.jsfx-inc").read_text()
        self.assertIn("help_guide_menu(frame_ok)", self.main)
        self.assertIn("gfx_showmenu(#help_guide_menu)", help_source)
        self.assertIn("slider10 = choice - 1", help_source)
        self.assertIn("AXIS_FONT = 13", layout)
        self.assertIn("AXIS_LABEL_SPACING = 18", layout)
        self.assertGreaterEqual(plot.count('gfx_setfont(1, "Arial", AXIS_FONT)'), 2)
        self.assertIn("gfx_y = max(y0, min(y - th * 0.5, y0 + g_panel_h - th))", plot)

    def test_event_palette_and_opaque_shared_heads_preserve_channel_bars(self):
        self.assertIn("gfx_r = 1; gfx_g = 0.55; gfx_b = 0.15", self.notes)
        self.assertIn("gfx_r = 1; gfx_g = 0.25; gfx_b = 0.25", self.notes)
        self.assertIn("event_colour(0, 1)", self.notes)
        self.assertIn("event_colour(1, 1)", self.notes)
        self.assertIn("event_colour(off, 1)", self.notes)
        self.assertIn("note_colour(ch, 0.95)", self.notes)
        self.assertIn("draw_note_plot_head(on, 0, g_note_marker_h)", self.notes)
        self.assertIn("draw_note_plot_head(note_field(k, 1), 1, g_note_marker_h)", self.notes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
