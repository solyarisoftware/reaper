"""Contextual-help source contracts; these checks do not execute JSFX graphics."""
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[2] / "bloomscope"


class HelpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (SRC / "bloomscope.jsfx").read_text()
        cls.notes = (SRC / "bloomscope_notes.jsfx-inc").read_text()
        cls.help = (SRC / "bloomscope_help.jsfx-inc").read_text()
        cls.renderer = (SRC / "bloomscope_tooltip.jsfx-inc").read_text()

    def test_packaged_modules_and_final_overlay(self):
        for filename in ("bloomscope_tooltip.jsfx-inc", "bloomscope_help.jsfx-inc"):
            self.assertIn("//   " + filename, self.main)
            self.assertIn("import " + filename, self.main)
        self.assertLess(self.main.index("ctl_draw_menu_items();"),
                        self.main.index("draw_context_help(frame_ok);"))

    def test_larger_pitch_only_labels_and_measured_dense_threshold(self):
        self.assertIn('gfx_setfont(1, "Arial", 16)', self.notes)
        self.assertIn('gfx_measurestr("Mg", tw, label_h)', self.notes)
        self.assertIn("row_h >= max(18, label_h)", self.notes)
        self.assertIn("row_h < max(18, label_h)", self.notes)
        self.assertNotIn('"%s ch%d v%d"', self.notes)
        self.assertIn("lx >= label_end + 4 && lx + tw <= right", self.notes)

    def test_dense_and_off_only_hover_without_invented_velocity(self):
        hover = self.notes.index("g_note_hover = k + 1")
        self.assertLess(hover, self.notes.index("row_h >= max(18, label_h)"))
        self.assertIn("g_note_hover = 0", self.notes)
        self.assertIn("note_field(k, 7) ?", self.help)
        self.assertIn("velocity %d", self.help)
        self.assertIn("unmatched note-off", self.help)
        self.assertIn("No start time, velocity or note duration is invented", self.help)

    def test_dwell_suppression_and_snapshot_only_note_data(self):
        self.assertIn("ready && cbm_open() == 0 && (mouse_cap & 3) == 0", self.help)
        self.assertIn("now - help_since >= 0.45", self.help)
        self.assertIn("abs(mouse_x - help_last_x) > 4", self.help)
        self.assertIn("strcmp(#help_previous, #help_identity)", self.help)
        self.assertNotIn("MEM_MIDI_RECORD", self.help)
        self.assertNotIn("mem[", self.help.split("@init", 1)[1])
        self.assertIn("mouse_x >= 0 && mouse_x < gfx_w", self.help)
        self.assertIn("mouse_y >= 0 && mouse_y < gfx_h", self.help)
        self.assertIn("tip_visible = 0", self.help)

    def test_explanations_and_ccscope_renderer_safety(self):
        for text in ("not LUFS", "not a mono fold-down", "four lines", "two lines",
                     "not a third measurement", "CC1 or CC11", "MIDI 60 = C4",
                     "preserves history", "Axis labels and MIDI event guides remain",
                     "moving average of hop RMS amplitudes"):
            self.assertIn(text, self.help)
        self.assertIn("tip_w = min(520, gfx_w - 12)", self.renderer)
        self.assertIn("tip_h <= room", self.renderer)
        self.assertIn("gfx_mode = old_mode", self.renderer)
        self.assertIn("gfx_a = 1", self.renderer)
        self.assertIn("2c2a7238ad6068ce9ae4824b45f37d820b3ab1e6", self.help)


if __name__ == "__main__":
    unittest.main(verbosity=2)
