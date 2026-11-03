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
