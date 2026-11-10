"""Timing probe/oracle and source contract checks; EEL2 execution is native only."""
from pathlib import Path
import importlib.util
import math
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('metrics_probe', ROOT / 'tools/ccscope_metrics_probe.py')
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class MetricsProbeTests(unittest.TestCase):
    def test_generator_copies_actual_production_functions_without_instrumentation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'metrics'
            target = PROBE.build(ROOT / 'ccscope', output)
            text = target.read_text()
            self.assertIn('options:gmem=CCScopeMetricsTiming', text)
            self.assertIn('get_timing_cc_channel(0,0);', text)
            self.assertIn('calculate_time_window(); g_metrics_now=g_time_end;', text)
            self.assertIn('prune_old_metrics(2);', text)
            self.assertIn('gmem[2]=1;', text)
            self.assertIn('gmem[4] = metrics_case;', text)
            self.assertNotIn('function get_timing_cc_channel', text)
            self.assertNotIn('e-0', text)  # Generator emits decimal literals for EEL2.
            for name in ('utils', 'metrics', 'plot'):
                filename = f'ccscope_{name}.jsfx-inc'
                self.assertEqual((output / filename).read_bytes(),
                                 (ROOT / 'ccscope' / filename).read_bytes())
            with self.assertRaises(ValueError):
                PROBE.build(ROOT / 'ccscope', output)

    def test_native_cost_probe_measures_actual_work_for_each_pair_count(self):
        with tempfile.TemporaryDirectory() as directory:
            target = PROBE.build(ROOT / 'ccscope', Path(directory) / 'cost', benchmark=True)
            text = target.read_text()
            self.assertIn('options:gmem=CCScopeMetricsCost', text)
            self.assertIn('loop(MAX_EVENTS_PER_CC,', text)
            self.assertIn('metrics_case==0 ? 1 : metrics_case==1 ? 16 : 64', text)
            self.assertIn('get_timing_cc_channel(floor(metrics_pair/16),metrics_pair%16)', text)
            self.assertIn('time_precise()-metrics_start', text)
            self.assertIn('metrics_frame>=2', text)
            self.assertIn('metrics_frame==34', text)
            self.assertIn('gmem[3+metrics_case]=metrics_sum/32', text)
            self.assertIn('gmem[6]=metrics_case', text)
            self.assertNotIn('function timing_sort', text)

    def test_reference_fixtures_distinguish_uniform_and_coincident_streams(self):
        fixtures = {name: PROBE.intervals(times, now) for name, times, now in PROBE.CASES}
        uniform = fixtures['uniform']
        batches = fixtures['coincident batches']
        self.assertEqual(len(uniform), 99)
        self.assertTrue(all(abs(interval - 10) < 1e-9 for interval in uniform))
        self.assertEqual(len(batches), 99)
        self.assertEqual(batches.count(0), 90)
        self.assertEqual(batches[math.ceil(.5 * 99) - 1], 0)
        self.assertAlmostEqual(batches[math.ceil(.95 * 99) - 1], 100)
        self.assertAlmostEqual(100 * batches.count(0) / len(batches), 90.9090909)

    def test_reference_boundary_invalid_and_small_sample_contracts(self):
        raw = PROBE.intervals
        self.assertEqual(raw([0, 1], 1), [1000])  # Both closed endpoints, zero valid.
        self.assertEqual(raw([0, 0, 0], 0), [0, 0])
        self.assertEqual(raw([.9, 1.2], 2), [])
        self.assertEqual(raw([1.1, 2.1, 1.4, 1.5], 2), [100.00000000000009])
        self.assertEqual(raw([1.1, .9, 1.4], 2), [])  # Do not bridge exclusions.
        self.assertEqual(raw([-.1, 0, .1], .5), [100])
        self.assertEqual(raw([.3, .2, .2, .4], 1), [0, 200])
        for times in ([], [.5]):
            self.assertEqual(raw(times, 1), [])

    def test_native_probe_checks_all_sorted_elements_and_exact_quantile_ranks(self):
        text = PROBE.checks()
        self.assertIn('metrics_close(mem[MEM_TIMING_SCRATCH+498]', text)
        for label in ('exact ranks 20', 'exact ranks 21', 'capacity descending',
                      'capacity repeated', 'capacity permuted', 'future breaks adjacency',
                      'negative timestamps', 'non-monotonic', 'filtered pause'):
            self.assertIn(label, text)
        for count in (20, 21):
            times = [i * (i + 1) / 2000 for i in range(count + 1)]
            raw = PROBE.intervals(times, 1)
            self.assertAlmostEqual(raw[math.ceil(.5 * count) - 1], 10 if count == 20 else 11)
            self.assertAlmostEqual(raw[math.ceil(.95 * count) - 1], 19 if count == 20 else 20)
        self.assertIn('g_timing_jitter_intervals==90', text)
        self.assertIn('mem[metrics_base_ptr]==MAX_EVENTS_PER_CC', text)
        self.assertIn('g_clock_sec=30; calculate_time_window()', text)

    def test_production_uses_bounded_scratch_and_explicit_raw_endpoint_policy(self):
        text = (ROOT / 'ccscope/ccscope_metrics.jsfx-inc').read_text()
        self.assertIn('count = min(mem[base], MAX_EVENTS_PER_CC);', text)
        self.assertIn('time >= 0 && time >= cutoff && time <= g_metrics_now', text)
        self.assertIn('interval >= 0 ?', text)
        self.assertIn(') : have_previous = 0;', text)
        self.assertIn('ceil(0.50 * g_timing_intervals) - 1', text)
        self.assertIn('ceil(0.95 * g_timing_intervals) - 1', text)
        self.assertIn('limit = g_timing_min * GAP_FACTOR;', text)
        self.assertIn('sqrt(squared / used)', text)
        self.assertNotIn('get_jitter_quality', text)
        self.assertNotIn('get_jitter_ms_cc_channel', text)
        self.assertIn('event_time >= cutoff_time ? keep_started = 1;', text)


if __name__ == '__main__':
    unittest.main()
