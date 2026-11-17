"""Document the measured loop-wrap limitation; no speculative event retiming.

The expected failure is intentional: MIDI can arrive in the block before the
host publishes the wrapped play position. The standalone JSFX has no verified
loop-boundary context to distinguish this from an arbitrary backward seek.
"""
import unittest

from test_bloomscope_midi import BloomScopeJointModel, on, off


class LoopWrapTests(unittest.TestCase):
    def test_fresh_play_captures_note_at_project_zero(self):
        j = BloomScopeJointModel()
        j.block(-512 / 48000, 384, reset=False)
        j.block(-128 / 48000, 384, [on(128, pitch=62, velocity=88)], reset=False)
        j.block(256 / 48000, 384, reset=False)
        audio, notes = j.frame(window=15)
        self.assertEqual(len(notes), 1)
        self.assertTrue(notes[0].has_on)
        self.assertAlmostEqual(notes[0].on, 0)

    @unittest.expectedFailure
    def test_first_wrapped_note_needs_correct_note_on_reference(self):
        # Measured host observation: loop [0, 26 2/3 s), 48 kHz / 384 samples;
        # first D4 arrives at block position 26.661333... with offset 256.
        j = BloomScopeJointModel()
        j.block(26 + 1984 / 3000, 384,
                [on(256, pitch=62, velocity=88)], reset=False)
        for i in range(104):
            t = (128 + i * 384) / 48000
            events = [off(320, pitch=62)] if i == 103 else ()
            j.block(t, 384, events, reset=False)
        audio, notes = j.frame(window=15)
        self.assertTrue(any(n.pitch == 62 and n.has_on and abs(n.on) < 1e-8 for n in notes),
                        "Known bug: first wrapped D4 is currently an unmatched off")


if __name__ == "__main__":
    unittest.main(verbosity=2)
