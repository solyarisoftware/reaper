"""Public product identity, package wiring and ALPHA contract checks."""
from pathlib import Path
import re
import shutil
import tempfile
import unittest

from lint_header import check

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'bloomscope'
TESTS = Path(__file__).resolve().parent
TAGLINE = "See how your instrument's sound unfolds in relation to MIDI notes."


class IdentityTests(unittest.TestCase):
    def test_public_name_tagline_and_versions_are_consistent(self):
        main = (PACKAGE / 'bloomscope.jsfx').read_text()
        self.assertEqual(main.splitlines()[0], 'desc:BloomScope')
        self.assertIn('// @description BloomScope\n', main)
        version = re.search(r'^// @version (\S+)$', main, re.MULTILINE).group(1)
        self.assertEqual(version, '0.1.3')
        self.assertIn('//   ' + TAGLINE, main)
        layout = (PACKAGE / 'bloomscope_layout.jsfx-inc').read_text()
        self.assertIn('BLOOMSCOPE_VERSION = "' + version + '";', layout)
        self.assertIn(TAGLINE, (PACKAGE / 'README.md').read_text())
        self.assertIn('## ' + version + ' ', (PACKAGE / 'CHANGELOG.md').read_text())

    def test_alpha_warning_badge_and_changelog_match_metadata(self):
        main = (PACKAGE / 'bloomscope.jsfx').read_text()
        readme = (PACKAGE / 'README.md').read_text()
        self.assertIn('> [!WARNING]\n> **ALPHA**', readme)
        self.assertIn('**ALPHA**', main)
        self.assertRegex((ROOT / 'README.md').read_text(),
                         r'(?m)^\| \[BloomScope\].*status-ALPHA-yellow')
        change = re.search(r'^// @changelog\n//   (.+)$', main, re.MULTILINE).group(1)
        self.assertIn('- ' + change, (PACKAGE / 'CHANGELOG.md').read_text())

    def test_description_covers_combined_audio_and_optional_midi(self):
        main = (PACKAGE / 'bloomscope.jsfx').read_text()
        for phrase in ('combined audio output', 'Chords, ensembles, overlapping notes and release tails',
                       'not a separate envelope for each MIDI note', 'not a sum of per-note envelopes',
                       'MIDI input is optional', 'not while stopped, paused or recording',
                       'Use project playrate 1', 'known first-note timing defect'):
            self.assertIn(phrase, main)

    def test_readme_explains_polyphony_and_capture_limits(self):
        readme = (PACKAGE / 'README.md').read_text()
        for phrase in ('combined audio signal', 'not a separate envelope for each note',
                       'MIDI is optional', 'note-off is not necessarily the end of the sound',
                       'Playback-only acquisition', 'Project playrate 1'):
            self.assertIn(phrase, readme)

    def test_namespace_is_shared_by_plugin_action_and_host_probe(self):
        namespace = 'BloomScope_Loop_v1'
        main = (PACKAGE / 'bloomscope.jsfx').read_text()
        action = (PACKAGE / 'bloomscope_loop_companion.lua').read_text()
        probe = (TESTS / 'build_loop_host_probe.py').read_text()
        self.assertIn('options:gmem=' + namespace, main)
        self.assertIn("'" + namespace + "'", action)
        self.assertIn(namespace, probe)

    def test_package_wiring_and_action_registration(self):
        self.assertEqual(check(), [])
        self.assertEqual(len(list(PACKAGE.glob('*.jsfx*'))), 10)
        self.assertIn('-- @noindex\n', (PACKAGE / 'bloomscope_loop_companion.lua').read_text())

    def test_linter_rejects_a_missing_include_and_wrong_action_type(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'bloomscope'
            shutil.copytree(PACKAGE, package)
            (package / 'bloomscope_midi.jsfx-inc').unlink()
            main = package / 'bloomscope.jsfx'
            main.write_text(main.read_text().replace('[script main=main]', '[main]'))
            errors = check(package)
            self.assertTrue(any('missing or unowned include' in error for error in errors))
            self.assertIn('companion must be provided as a Main script', errors)

    def test_runtime_sources_have_no_old_brand_or_private_source_dependencies(self):
        previous_names = ('env' + 'scope', 'envelope' + 'scope', 'response' + 'scope')
        for path in PACKAGE.iterdir():
            if path.suffix not in ('.jsfx', '.jsfx-inc', '.lua'):
                continue
            text = path.read_text().lower()
            for previous in previous_names:
                with self.subTest(filename=path.name, previous=previous):
                    self.assertNotIn(previous, path.name.lower())
                    self.assertNotIn(previous, text)
            self.assertNotIn('jsfx-lab/', text)
            self.assertNotIn('reamate/scores', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
