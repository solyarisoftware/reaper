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
        for name in ('ccscope_utils.jsfx-inc', 'ccscope_metrics.jsfx-inc'):
            shutil.copy2(ROOT / 'MIDI/ccscope' / name, self.source / name)

    def replace(self, old, new):
        path = self.source / 'ccscope_utils.jsfx-inc'
        text = path.read_text()
        self.assertEqual(text.count(old), 1)
        path.write_text(text.replace(old, new))

    def test_current_ranges_fit(self):
        self.assertEqual(MEMORY.check(self.source), [])

    def test_temporal_history_overlap_is_rejected(self):
        self.replace('MEM_TIME_HISTORY = 3120000;', 'MEM_TIME_HISTORY = 30000;')
        self.assertTrue(any('overlaps' in error for error in MEMORY.check(self.source)))

    def test_temporal_history_must_cover_thirty_seconds(self):
        self.replace('TIME_HISTORY_BUCKETS = 301;', 'TIME_HISTORY_BUCKETS = 300;')
        self.assertTrue(any('30-second' in error for error in MEMORY.check(self.source)))

    def test_temporal_history_must_fit_default_memory(self):
        self.replace('TIME_HISTORY_BUCKETS = 301;', 'TIME_HISTORY_BUCKETS = 1000;')
        self.assertTrue(any('8M-slot' in error for error in MEMORY.check(self.source)))

    def test_detects_graph_index_overlap(self):
        self.replace('MEM_GRAPH_Y = 22772;', 'MEM_GRAPH_Y = 20772;')
        self.assertTrue(any('MEM_GRAPH' in error and 'overlaps' in error
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
            module.build(ROOT / 'MIDI/ccscope', output)
            text = (output / 'history_checks.jsfx').read_text()
            self.assertIn('function draw_temporal_point(', text)
            self.assertIn('middle = (max(first_t, g_time_start)', text)
            self.assertIn('history_verify(history_dots==1)', text)
            self.assertNotIn('1e20', text)  # Unsupported EEL2 literal caused a native false start.
            self.assertEqual((output / 'ccscope_utils.jsfx-inc').read_bytes(),
                             (ROOT / 'MIDI/ccscope/ccscope_utils.jsfx-inc').read_bytes())
            with self.assertRaises(ValueError):
                module.build(ROOT / 'MIDI/ccscope', output)

    def test_old_exact_event_probe_rejects_temporal_renderer(self):
        module = self.load_tool('ccscope_rendering_probe')
        with self.assertRaisesRegex(ValueError, 'ccscope_history_probe'):
            module.graph_function((ROOT / 'MIDI/ccscope/ccscope.jsfx').read_text())

    def test_acceptance_seed_populates_both_temporal_and_raw_history(self):
        module = self.load_tool('ccscope_acceptance_probe')
        source = (ROOT / 'MIDI/ccscope/ccscope.jsfx').read_text()
        seeded = module.instrument(source, 'candidate')
        self.assertIn('g_clock_sec = 200;', seeded)
        self.assertIn('add_temporal_history(accept_t,', seeded)
        unseeded = module.instrument(source, 'candidate', seed_history=False)
        self.assertNotIn('add_temporal_history(accept_t,', unseeded)
        self.assertNotIn('g_clock_sec = 200;', unseeded)


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
