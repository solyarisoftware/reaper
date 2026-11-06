"""Offline checks for rendering-test infrastructure; native probes test EEL2."""
from pathlib import Path
import importlib.util
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location('ccscope_memory', ROOT / 'tools/check_ccscope_memory.py')
MEMORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEMORY)


class MemoryMapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)
        for name in ('ccscope_utils.jsfx-inc', 'ccscope_metrics.jsfx-inc',
                     'ccscope_controlbar.jsfx-inc'):
            shutil.copy2(ROOT / 'ccscope' / name, self.source / name)

    def replace(self, old, new):
        path = self.source / 'ccscope_utils.jsfx-inc'
        text = path.read_text()
        self.assertEqual(text.count(old), 1)
        path.write_text(text.replace(old, new))

    def test_current_ranges_fit(self):
        self.assertEqual(MEMORY.check(self.source), [])

    def test_event_ring_overlap_is_rejected(self):
        self.replace('MEM_EVENT_RING = 3120000;', 'MEM_EVENT_RING = 20000;')
        self.assertTrue(any('overlaps' in error for error in MEMORY.check(self.source)))

    def test_event_ring_must_cover_thirty_seconds_at_the_flood_rate(self):
        self.replace('EVENT_CAPACITY = 2600000;', 'EVENT_CAPACITY = 20000;')
        self.assertTrue(any('30-second' in error for error in MEMORY.check(self.source)))

    def test_event_ring_must_fit_default_memory(self):
        self.replace('EVENT_CAPACITY = 2600000;', 'EVENT_CAPACITY = 3000000;')
        self.assertTrue(any('8M-slot' in error for error in MEMORY.check(self.source)))

    def test_detects_control_bar_block_overlap(self):
        self.replace('MEM_CBM_BASE = 12612;', 'MEM_CBM_BASE = 2304;')  # inside MEM_CC_SORTED
        self.assertTrue(any('MEM_CBM' in error and 'overlaps' in error
                            for error in MEMORY.check(self.source)))

    def test_control_bar_block_must_fit_its_reservation(self):
        # The module grew by the list-table slots; the reservation has to follow.
        self.replace('MEM_CBM_SIZE = 122;', 'MEM_CBM_SIZE = 96;')
        self.assertTrue(any('Control-bar block needs' in error
                            for error in MEMORY.check(self.source)))

    def test_history_growth_requires_resizing_all_ranges(self):
        self.replace('MAX_HISTORY_ITEMS = 2000;', 'MAX_HISTORY_ITEMS = 2001;')
        self.assertTrue(any('overlaps' in error for error in MEMORY.check(self.source)))

    def test_narrower_pair_key_collisions_are_rejected(self):
        self.replace('  (cc_num << 4) | channel\n', '  (cc_num << 3) | channel\n')
        self.assertTrue(any('dense-key' in error for error in MEMORY.check(self.source)))

    def test_wider_pair_key_is_rejected(self):
        self.replace('  (cc_num << 4) | channel\n', '  (cc_num << 5) | channel\n')
        self.assertTrue(any('dense-key' in error for error in MEMORY.check(self.source)))


class HistoryProbeTests(unittest.TestCase):
    def load_tool(self, name):
        spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_probe_uses_actual_renderer_and_copies_current_storage(self):
        module = self.load_tool('ccscope_history_probe')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'new'
            module.build(ROOT / 'ccscope', output)
            text = (output / 'history_checks.jsfx').read_text()
            self.assertIn('function draw_cc_data_lines(', text)
            self.assertIn('event_slot(', text)
            self.assertIn('history_verify(history_dots==1)', text)
            self.assertNotIn('1e20', text)  # Unsupported EEL2 literal caused a native false start.
            self.assertEqual((output / 'ccscope_utils.jsfx-inc').read_bytes(),
                             (ROOT / 'ccscope/ccscope_utils.jsfx-inc').read_bytes())
            with self.assertRaises(ValueError):
                module.build(ROOT / 'ccscope', output)

    def test_probe_covers_the_ring_and_the_drawing_budget(self):
        module = self.load_tool('ccscope_history_probe')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'new'
            module.build(ROOT / 'ccscope', output)
            text = (output / 'history_checks.jsfx').read_text()
            self.assertIn(module.CASES, text)
            self.assertIn('history_x1=x1; history_y1=y1;', text)
            # every event is a vertex: four events, three segments
            self.assertIn('history_verify(history_dots==4 && history_lines==3)', text)
            # the ring wraps in two-slot events
            self.assertIn('history_verify(event_slot(EVENT_CAPACITY)==MEM_EVENT_RING)', text)
            # above the budget the trace decimates and publishes the stride
            self.assertIn('history_verify(g_mark_stride==2)', text)
            self.assertIn('history_verify(history_dots==2001)', text)
            # Auto spacing and None still behave
            self.assertIn('slider5=0;', text)
            self.assertIn('slider5=2;', text)

    def test_old_exact_event_probe_rejects_temporal_renderer(self):
        module = self.load_tool('ccscope_rendering_probe')
        with self.assertRaisesRegex(ValueError, 'ccscope_history_probe'):
            module.graph_function((ROOT / 'ccscope/ccscope_plot.jsfx-inc').read_text())

    def test_acceptance_seed_populates_both_temporal_and_raw_history(self):
        module = self.load_tool('ccscope_acceptance_probe')
        source = (ROOT / 'ccscope/ccscope.jsfx').read_text()
        seeded = module.instrument(source, 'candidate')
        self.assertIn('g_clock_sec = 200;', seeded)
        self.assertIn('add_temporal_history(accept_t,', seeded)
        unseeded = module.instrument(source, 'candidate', seed_history=False)
        self.assertNotIn('add_temporal_history(accept_t,', unseeded)
        self.assertNotIn('g_clock_sec = 200;', unseeded)


class StatusProbeTests(unittest.TestCase):
    def load_tool(self, name):
        spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_probe_checks_the_real_status_module(self):
        module = self.load_tool('ccscope_rendering_probe')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'status'
            target = module.build_status(ROOT / 'ccscope', output)
            text = target.read_text()
            # the module arrives through the import, so it is a copied file, not text
            port = (output / 'ccscope_status.jsfx-inc').read_text()
            self.assertIn('function draw_status_info(count)', port)
            self.assertIn('probe_form_that_fits(', text)
            self.assertIn('draw_status_info(probe_count);', text)
            self.assertIn('options:gmem=CCScopeStatusTest', text)
            self.assertIn('desc:CCScope status-line probe', text)
            # the probe drives the real module, not a copy of it
            self.assertEqual((output / 'ccscope_status.jsfx-inc').read_bytes(),
                             (ROOT / 'ccscope/ccscope_status.jsfx-inc').read_bytes())

    def test_probe_refuses_a_module_that_changed_shape(self):
        module = self.load_tool('ccscope_rendering_probe')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'ccscope'
            shutil.copytree(ROOT / 'ccscope', source)
            port = source / 'ccscope_status.jsfx-inc'
            port.write_text(port.read_text().replace('function draw_status_info(count)',
                                                      'function draw_status_info(count, extra)'))
            with self.assertRaisesRegex(ValueError, 'changed signature'):
                module.build_status(source, Path(directory) / 'out')

    def test_driver_only_calls_functions_the_plugin_declares(self):
        driver = (ROOT / 'tools/ccscope_status_probe.txt').read_text()
        source = ''.join(p.read_text() for p in (ROOT / 'ccscope').glob('ccscope*.jsfx*'))
        import re
        for called in set(re.findall(r'\b(status_build|status_measure|draw_status_info)\(', driver)):
            self.assertIn(f'function {called}(', source,
                          f'the driver calls {called}() but the plugin does not declare it')

    def test_the_two_warnings_are_asserted_by_the_probe(self):
        driver = (ROOT / 'tools/ccscope_status_probe.txt').read_text()
        # both warnings are checked against the real layout, in both row layouts
        self.assertIn('(probe_count > g_visible_bars) != probe_got_wv', driver)
        self.assertIn('((slider7 == 1) && g_side_fallback) != probe_got_ws', driver)
        self.assertIn('slider7 = floor(probe_case / 45) % 2;', driver)
        self.assertIn('calculate_layout(probe_count);', driver)


class PackageLayoutTests(unittest.TestCase):
    def test_every_include_is_provided_present_and_imported(self):
        import importlib.util
        source = ROOT / 'ccscope'
        main = (source / 'ccscope.jsfx').read_text()
        spec = importlib.util.spec_from_file_location(
            'ccscope_acceptance_probe', ROOT / 'tools/ccscope_acceptance_probe.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        provided = {path.name for path in module.provides(source)}
        imported = {line.split()[1] for line in main.splitlines()
                    if line.startswith('import ')}
        self.assertEqual(provided, imported)
        on_disk = {path.name for path in source.glob('*.jsfx-inc')}
        self.assertEqual(provided, on_disk)

    def test_panels_do_not_call_each_other(self):
        """A panel reads the frame state; it calls no other panel's function."""
        import re
        source = ROOT / 'ccscope'
        panels = ['ccscope_layout', 'ccscope_plot', 'ccscope_rows',
                  'ccscope_status', 'ccscope_controlbar']
        owner, bodies = {}, []
        for panel in panels:
            text = (source / f'{panel}.jsfx-inc').read_text()
            for match in re.finditer(r'^function\s+([A-Za-z_]\w*)\s*\(', text, re.M):
                owner[match.group(1)] = panel
                bodies.append((panel, match.group(1), match.start()))
        for index, (panel, name, start) in enumerate(bodies):
            end = bodies[index + 1][2] if index + 1 < len(bodies) else None
            body = (source / f'{panel}.jsfx-inc').read_text()[start:end]
            code = re.sub(r'/\*.*?\*/', '', body, flags=re.S)
            code = re.sub(r'//[^\n]*', '', code)
            for call in set(re.findall(r'\b([A-Za-z_]\w*)\s*\(', code)):
                other = owner.get(call)
                self.assertIn(other, (None, panel),
                              f'{panel}.{name} calls {other}.{call}: panels must stay leaves')


class Eel2OrderTests(unittest.TestCase):
    """EEL2 has no forward declarations: a function may only call what came first."""

    def combined(self):
        import re
        source = ROOT / 'ccscope'
        main = (source / 'ccscope.jsfx').read_text()
        order = [line.split()[1] for line in main.splitlines() if line.startswith('import ')]
        parts = [(source / name).read_text() for name in order]
        parts.append(main)
        # Native tooltip fixtures call production functions too: catch stale
        # signatures/forward references before a parent-authorized native run.
        parts.append((ROOT / 'tools/ccscope_tooltip_probe.txt').read_text())
        text = '\n'.join(parts)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
        return re.sub(r'//[^\n]*', '', text)

    def test_no_forward_references(self):
        import re
        text = self.combined()
        marks = [(m.start(), m.group(1)) for m in
                 re.finditer(r'^function\s+([A-Za-z_]\w*)\s*\(', text, re.M)]
        order = [name for _, name in marks]
        problems = []
        for index, (start, name) in enumerate(marks):
            end = marks[index + 1][0] if index + 1 < len(marks) else len(text)
            for call in set(re.findall(r'\b([A-Za-z_]\w*)\s*\(', text[start:end])):
                if call != name and call in order and order.index(call) > index:
                    problems.append(f'{name} calls {call}, declared later')
        self.assertEqual(problems, [], 'EEL2 requires the callee to be declared first')

    def test_calls_match_declared_arity(self):
        """EEL2 checks arity at compile time: a stray argument is a plugin that will not load."""
        import re
        text = self.combined()
        clean = re.sub(r'"(?:[^"\\]|\\.)*"', '@', text)

        def split_args(piece):
            if not piece.strip():
                return []
            depth, args, current = 0, [], ''
            for char in piece:
                if char in '([':
                    depth += 1
                if char in ')]':
                    depth -= 1
                if char == ',' and depth == 0:
                    args.append(current)
                    current = ''
                else:
                    current += char
            args.append(current)
            return args

        declared = {}
        for match in re.finditer(r'^function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)[^\n(]*\(', clean, re.M):
            declared[match.group(1)] = len(split_args(match.group(2)))
        self.assertGreater(len(declared), 90, 'the package must be parsed, not skipped')
        problems = []
        for match in re.finditer(r'\b([A-Za-z_]\w*)\s*\(', clean):
            name = match.group(1)
            if name not in declared or clean[:match.start()].rstrip().endswith('function'):
                continue
            index, depth, current = match.end(), 1, ''
            while index < len(clean) and depth:
                char = clean[index]
                if char == '(':
                    depth += 1
                if char == ')':
                    depth -= 1
                if depth:
                    current += char
                index += 1
            if len(split_args(current)) != declared[name]:
                problems.append(f'{name}: declared {declared[name]}, called with {len(split_args(current))}')
        self.assertEqual(problems, [])

    def test_module_block_fits_the_declared_size(self):
        import re
        source = ROOT / 'ccscope'
        module = (source / 'ccscope_controlbar.jsfx-inc').read_text()
        utils = (source / 'ccscope_utils.jsfx-inc').read_text()
        constants = {m.group(1): int(m.group(2)) for m in
                     re.finditer(r'^(CBM_\w+|MEM_CBM_\w+)\s*=\s*(\d+);', module + '\n' + utils, re.M)}
        cells = constants['CBM_MAX_CELLS']
        arrays = [constants[name] for name in
                  ('CBM_X', 'CBM_W', 'CBM_KIND', 'CBM_MIN', 'CBM_MAX',
                   'CBM_DEF', 'CBM_VAL', 'CBM_APL', 'CBM_LBASE', 'CBM_LCOUNT')]
        for left, right in zip(arrays, arrays[1:]):
            self.assertGreater(right - left, cells, 'one-based cell arrays must not overlap')
        for start in arrays:
            self.assertLess(start + cells, constants['CBM_ARRAYS_END'],
                                 'a cell array runs past the module block')
        self.assertEqual(constants['CBM_ARRAYS_END'], constants['MEM_CBM_SIZE'],
                         'the module block and the size declared in ccscope_utils must agree')
        self.assertLess(max(value for name, value in constants.items()
                            if name.startswith('CBM_') and name not in
                            ('CBM_ARRAYS_END', 'CBM_MAX_CELLS') and value < min(arrays)),
                        min(arrays), 'the scalar header must end before the arrays')

    def test_module_never_touches_a_slider(self):
        import re
        text = (ROOT / 'ccscope/ccscope_controlbar.jsfx-inc').read_text()
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
        text = re.sub(r'//[^\n]*', '', text)
        for word in ('slider1', 'slider2', 'slider3', 'slider4', 'slider5',
                     'slider6', 'slider7', 'sliderchange'):
            self.assertNotIn(word, text, 'the bar module must stay reusable: no parameters of its own')


class ReleaseMetadataTests(unittest.TestCase):
    def read_published_changelog(self):
        """The `// @changelog` block: what ReaPack shows under this version."""
        import re
        lines, inside = [], False
        for line in (ROOT / 'ccscope/ccscope.jsfx').read_text().splitlines():
            if re.match(r'^//\s*@changelog\s*$', line):
                inside = True
                continue
            if inside:
                body = re.match(r'^//\s{2,}(\S.*?)\s*$', line)
                if not body:
                    break
                lines.append(body.group(1))
        return lines

    def read_changelog_entry(self, version):
        """The bullets of one release in CHANGELOG.md, wrapped lines joined."""
        entries, inside = [], False
        for line in (ROOT / 'ccscope/CHANGELOG.md').read_text().splitlines():
            if line.startswith('## '):
                inside = line.startswith(f'## {version} ')
                continue
            if not inside:
                continue
            if line.startswith('- '):
                entries.append(line[2:])
            elif line.startswith('  ') and entries:
                entries[-1] += ' ' + line.strip()
            elif not line.strip() and entries:
                break
        return entries

    @staticmethod
    def words(entry):
        """Word sequence only: markdown and punctuation may differ between the two copies."""
        import re
        entry = re.sub(r'\(https?://[^)]*\)', '', entry)  # a markdown link keeps its label
        return re.findall(r'[a-z0-9]+', entry.lower())

    def test_published_changelog_matches_the_changelog_file(self):
        # ReaPack shows the @changelog block of ccscope.jsfx, GitHub shows CHANGELOG.md:
        # the same sentences in two copies, kept in step by this assertion alone.
        import re
        version = re.search(r'^//\s*@version\s+(\S+)',
                            (ROOT / 'ccscope/ccscope.jsfx').read_text(), re.M).group(1)
        published = self.read_published_changelog()
        self.assertTrue(published, '@changelog must describe this release')
        self.assertEqual([self.words(entry) for entry in self.read_changelog_entry(version)],
                         [self.words(entry) for entry in published],
                         'CHANGELOG.md and the @changelog block must say the same thing')

    def test_the_comparison_notices_a_changed_word(self):
        published = self.read_published_changelog()
        changed = published[:1] + ['Nothing visible changed'] + published[1:]
        self.assertNotEqual([self.words(entry) for entry in published],
                            [self.words(entry) for entry in changed])

    def test_reapack_tag_matches_the_jsfx_version(self):
        import re
        text = (ROOT / 'ccscope/ccscope.jsfx').read_text()
        tag = re.search(r'^//\s*@version\s+(\S+)', text, re.M)
        meta = re.search(r'^version:\s*(\S+)', text, re.M)
        self.assertIsNotNone(tag, 'ReaPack reads @version, not the JSFX metadata line')
        self.assertIsNotNone(meta)
        self.assertEqual(tag.group(1), meta.group(1),
                         'the tag ReaPack publishes and the plugin version must be the same')
        changelog = (ROOT / 'ccscope/CHANGELOG.md').read_text()
        self.assertIn(f'## {meta.group(1)} ', changelog,
                      'a released version needs its entry in CHANGELOG.md')

    def test_the_version_the_plugin_shows_is_the_released_one(self):
        # The status line prints CCSCOPE_VERSION at the right edge. REAPER cannot read
        # the file's own @version, so this is a third copy of the number -- and the only
        # thing keeping it honest is this assertion.
        import re
        text = (ROOT / 'ccscope/ccscope.jsfx').read_text()
        tag = re.search(r'^//\s*@version\s+(\S+)', text, re.M)
        shown = re.search(r'^CCSCOPE_VERSION\s*=\s*"([^"]+)"', text, re.M)
        self.assertIsNotNone(shown, 'the status line needs a version string to print')
        self.assertEqual(shown.group(1), tag.group(1),
                         'the version on screen and the published version must be the same')


class CrossSplitProbeTests(unittest.TestCase):
    def test_pre_split_package_builds_with_a_compatibility_shim(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'ccscope_acceptance_probe', ROOT / 'tools/ccscope_acceptance_probe.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        legacy = dict(instrument=module.instrument, shim=module.LEGACY_SHIM)
        self.assertIn('cbm_cell_x(i)', legacy['shim'])
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / 'legacy'
            base.mkdir()
            for name in ('ccscope.jsfx', 'ccscope_utils.jsfx-inc', 'ccscope_metrics.jsfx-inc'):
                shutil.copy2(ROOT / 'ccscope' / name, base / name)
            text = (base / 'ccscope.jsfx').read_text()
            built = legacy['instrument'](text, 'baseline', legacy=True)
            self.assertIn('function cbm_cell_x(i)', built)
            self.assertIn('cbm_cell_x(accept_i)', built)
            self.assertNotIn('function cbm_cell_x(i)',
                             legacy['instrument'](text, 'candidate'))


class AcceptanceRunnerCleanupTests(unittest.TestCase):
    def test_real_cleanup_is_registered_and_idempotent(self):
        lua = shutil.which('lua5.4') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua interpreter unavailable')
        text = (ROOT / 'tools/ccscope_acceptance_runner.lua').read_text()
        start = text.index('local function native_input(')
        end = text.index('local function say(', start)
        actual_functions = text[start:end]
        setup = '''
local dir,root = "",1
local original_mouse_x,original_mouse_y = 7,9
local held_left,held_right = false,false
local calls,restores,exit_hook = {},0,nil
local response = "0\\ninput-ok"
reaper = {
 JS_Window_AddressFromHandle = function() return 1 end,
 ExecProcess = function(cmd) calls[#calls+1]=cmd; return response end,
 JS_Mouse_SetPosition = function(x,y) assert(x==7 and y==9); restores=restores+1 end,
 atexit = function(fn) exit_hook=fn end,
}
'''
        checks = '''
assert(type(exit_hook)=="function")
native_input("left-down")
assert(held_left and #calls==1)
exit_hook()
assert(not held_left and #calls==2 and calls[2]:find("left-up",1,true))
assert(restores==1)
exit_hook()
assert(#calls==2 and restores==1)
response="2\\n"
assert(not pcall(native_input,"right-down"))
response="0\\n"
exit_hook()
assert(#calls==3 and not held_right)
'''
        result = subprocess.run([lua, '-'], input=setup+actual_functions+checks,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_status_is_reset_before_project_mutation(self):
        text = (ROOT / 'tools/ccscope_acceptance_runner.lua').read_text()
        self.assertLess(text.index("write_status('RUNNING')"),
                        text.index('reaper.InsertTrackAtIndex'))
        self.assertIn('run_id=', text)


if __name__ == '__main__':
    unittest.main()
