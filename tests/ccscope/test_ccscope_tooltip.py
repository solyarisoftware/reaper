"""Issue #18 offline source/geometry regressions; native EEL2/font checks are separate."""
from pathlib import Path
import hashlib
import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE = ROOT / 'ccscope'


def code(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)


def digest(text):
    return hashlib.sha256(re.sub(r'\s+', '', code(text)).encode()).hexdigest()


def function(text, name):
    """Get one function through the next definition (the fixtures below are pure)."""
    start = text.index('function ' + name + '(')
    end = text.find('\nfunction ', start + 1)
    return code(text[start:end if end >= 0 else len(text)])


def expression(text, values):
    """Evaluate only a production arithmetic/boolean expression, not EEL2 execution."""
    return eval('(' + text.replace('&&', ' and ').replace('||', ' or ') + ')',
                {'__builtins__': {}, 'min': min, 'max': max}, values)


class MetricAlgorithmRegressionTests(unittest.TestCase):
    def test_metric_code_is_identical_to_a023aa0_ignoring_comments(self):
        # The whole module: window, count/delta/gap filters, variance, thresholds.
        self.assertEqual(digest((SOURCE / 'ccscope_metrics.jsfx-inc').read_text()),
                         'f4a5ed237a279ad4a392bf06f1ef5eada7361498b29b2803192e884b9d3b8e11')

    def test_midi_acquisition_freeze_pruning_and_passthrough_are_unchanged(self):
        main = (SOURCE / 'ccscope.jsfx').read_text()
        midi = main[main.index('function process_midi_messages('):main.index('\n@block')]
        self.assertEqual(digest(midi),
                         '5f733d8451f306214a73e8dfec21213a1813d65debeac828fbb7ac8ced24b3f4')
        self.assertIn('g_metrics_now = g_time_end;', main)
        self.assertIn('slider2 ? g_freeze_time = g_clock_sec;', main)

    def test_actual_quality_expressions_at_and_above_every_threshold(self):
        text = (SOURCE / 'ccscope_metrics.jsfx-inc').read_text()
        for name, variable, cases in (
            ('get_rate_quality', 'rate_value', [(0, 'slow'), (15, 'slow'), (16, 'moderate'),
             (40, 'moderate'), (41, 'brisk'), (70, 'brisk'), (71, 'fast')]),
            ('get_jitter_quality', 'jitter_ms', [(0, 'steady'), (5, 'steady'), (5.001, 'even'),
             (15, 'even'), (15.001, 'uneven'), (30, 'uneven'), (30.001, 'loose'),
             (50, 'loose'), (50.001, 'erratic')]),
        ):
            actual = function(text, name).split(') (', 1)[1].split('\n);', 1)[0].strip()
            # These functions are nested, side-effect-free EEL2 conditional expressions.
            def choose(piece, value):
                if '?' not in piece:
                    return expression(piece.strip(), {variable: value})
                condition, rest = piece.split('?', 1)
                yes, no = rest.split(':', 1)
                return (expression(yes.strip(), {}) if expression(condition, {variable: value})
                        else choose(no, value))
            for value, expected in cases:
                self.assertEqual(choose(actual, value), expected)


class MetricHoverTests(unittest.TestCase):
    def setUp(self):
        self.rows = (SOURCE / 'ccscope_rows.jsfx-inc').read_text()
        self.layout = (SOURCE / 'ccscope_layout.jsfx-inc').read_text()
        hit = function(self.rows, 'metric_help_hit')
        self.hit = hit.split(') (', 1)[1].split(';', 1)[0].strip()

    def test_actual_hit_expression_is_half_open_and_canvas_bounded(self):
        bounds = dict(left=40, right=100, top=196, bottom=212, gfx_w=300, gfx_h=500)
        for x, y, expected in [(40, 196, True), (99.9, 211.9, True), (39.9, 200, False),
                               (100, 200, False), (50, 195.9, False), (50, 212, False)]:
            self.assertEqual(expression(self.hit, dict(bounds, mouse_x=x, mouse_y=y)), expected)
        # Visible text in the final canvas pixels remains targetable; only the
        # actual viewport clips it, not an artificial right-hand inset.
        for x in (292, 299):
            self.assertTrue(expression(self.hit, dict(bounds, right=400, mouse_x=x, mouse_y=200)))
        for x, y in [(-1, 200), (300, 200), (50, 500)]:
            self.assertFalse(expression(self.hit, dict(bounds, left=-20, right=400,
                                                       bottom=600, mouse_x=x, mouse_y=y)))

    def test_tier_one_has_its_own_visible_starts_and_no_invented_cells(self):
        compact = self.layout.split('g_metrics_tier = 1;', 1)[1]
        self.assertIn('g_col_mot_x = g_col_msg_r + gap;', compact)
        self.assertIn('g_col_tmg_x = g_col_mot_r + gap;', compact)
        capture = function(self.rows, 'capture_metric_help')
        self.assertIn('events <= 0 || g_metrics_tier == 0', capture)
        self.assertIn('gfx_measurestr(#help_field, tw, th);', capture)
        self.assertIn('g_metrics_tier == 3 && jitter >= 0 && intervals < 20', capture)
        self.assertIn('g_help_hit = pair * 5 + metric;', capture)

    def test_hit_bounds_include_actual_left_aligned_numeric_extents(self):
        capture = function(self.rows, 'capture_metric_help')
        self.assertIn('sprintf(#help_field, "%d u/s", motion);', capture)
        self.assertIn('right = max(g_col_mot_q_r, g_col_mot_v_x + tw);', capture)
        self.assertIn('sprintf(#help_field, "%.1fms", jitter);', capture)
        self.assertIn('right = max(g_col_tmg_q_r, g_col_tmg_v_x + tw);', capture)
        self.assertIn('g_help_right = min(gfx_w, right);', capture)
        fixture = (ROOT / 'tools/ccscope_tooltip_probe.txt').read_text()
        self.assertIn('162.4', fixture)
        self.assertIn('63500', fixture)
        self.assertIn('help_annotation_end - 1', fixture)

    def test_every_displayed_value_and_quality_uses_a_fixed_left_edge(self):
        draw = function(self.rows, 'draw_row_metrics')
        for field in ('msg_v_x', 'mot_v_x', 'mot_q_x', 'tmg_v_x', 'tmg_q_x'):
            self.assertIn(f'gfx_x = g_col_{field};', draw)
        self.assertNotRegex(draw, r'gfx_x\s*=\s*g_col_\w+_r\s*-')
        for reading in ('500/s', '63500 u/s', '999.9ms'):
            self.assertIn(f'gfx_measurestr("{reading}"', self.layout)
        self.assertIn('g_col_msg_v_x = g_col_msg_x;', self.layout)
        self.assertIn('g_col_mot_v_x = g_col_mot_x;', self.layout)
        self.assertIn('g_col_tmg_v_x = g_col_tmg_x;', self.layout)

    def test_identity_and_value_targets_reuse_existing_row_data(self):
        capture = function(self.rows, 'capture_row_help')
        self.assertIn('metric_help_hit(g_bar_x, g_bar_x + g_bar_width, y, y + BAR_HEIGHT)', capture)
        self.assertIn('metric_help_hit(g_value_x, g_value_x + value_w, top, bottom)', capture)
        self.assertIn('metric_help_hit(g_label_x, g_label_x + tw, top, bottom)', capture)
        self.assertIn('gfx_measurestr("127", tw, th);', capture)
        self.assertIn('g_help_metric = kind; g_help_pair = pair; g_help_value = value;', capture)
        self.assertNotRegex(capture, r'get_(events_per_second|rate_per_second|jitter_ms|cc_channel_value)')
        self.assertIn('capture_row_help(cc_channel_pair, val, y_pos);', self.rows)
        for phrase in ('CC / MIDI channel', 'CC value', 'Leading zeroes are formatting',
                       'Colors and shades can repeat', 'not automatic identification of a physical device',
                       'minimum visible stub remains at zero', 'does not confirm that the device sent zero'):
            self.assertIn(phrase, self.rows)

    def test_five_subject_ids_are_unique_for_every_pair(self):
        metric = re.search(r'g_help_hit = ([^;]+);', function(self.rows, 'capture_metric_help'))[1]
        row = re.search(r'g_help_hit = ([^;]+);', function(self.rows, 'capture_row_help'))[1]
        ids = []
        for pair in range(2048):
            ids.extend(expression(metric, dict(pair=pair, metric=subject)) for subject in (1, 2, 3))
            ids.extend(expression(row, dict(pair=pair, kind=subject)) for subject in (4, 5))
        self.assertEqual(len(set(ids)), 2048 * 5)
        self.assertEqual((min(ids), max(ids)), (1, 10240))

    def test_cache_is_captured_before_the_next_row_without_metric_recalculation(self):
        capture = function(self.rows, 'capture_metric_help')
        prepare = function(self.rows, 'prepare_metric_help')
        self.assertNotRegex(capture + prepare, r'get_(events_per_second|rate_per_second|jitter_ms)')
        self.assertIn('g_help_intervals = intervals;', capture)
        self.assertIn('g_row_intervals = g_jitter_intervals;', self.rows)
        self.assertLess(self.rows.index('g_row_intervals = g_jitter_intervals;'),
                        self.rows.index('jitter_q = jitter_ms < 0'))
        main = (SOURCE / 'ccscope.jsfx').read_text()
        self.assertIn('g_help_hit = 0;\ndraw_cc_bars();', main)
        self.assertIn('metric_help_dwell(g_help_hit, time_precise(), cbm_open() > 0)', main)
        self.assertLess(main.index('prepare_metric_help();'), main.index('cbm_draw_menu();'))

    def test_dwell_contract_is_explicit_and_independent_of_the_metric_clock(self):
        dwell = function(self.rows, 'metric_help_dwell')
        self.assertIn('suppressed ? hit = 0;', dwell)
        self.assertIn('hit != g_help_previous', dwell)
        self.assertIn('g_help_since = now;', dwell)
        self.assertIn('hit > 0 && now - g_help_since >= 0.4;', dwell)
        self.assertNotIn('g_metrics_now', dwell)

    def test_live_reserve_uses_the_same_formatter_and_int_is_explicit(self):
        prepare = function(self.rows, 'prepare_metric_help')
        self.assertEqual(prepare.count('metric_help_reading('), 2)
        self.assertIn('sample_count = g_help_metric == 1 ? 2 : g_help_metric == 2 ? 5 : g_help_metric == 3 ? 6 : 1;', prepare)
        self.assertIn('CC127/CH16 - Frozen - ', prepare)
        self.assertIn('strcat(#help_samples, #help_reading);', prepare)
        self.assertEqual(prepare.count("'int' means accepted inter-message intervals"), 2)

    def test_display_help_and_docs_use_jitter_without_plus_minus(self):
        self.assertIn('gfx_drawstr("Jitter")', self.rows)
        self.assertIn('sprintf(#mtf, "%.1fms", jitter_ms)', self.rows)
        self.assertNotIn('±', self.rows)
        self.assertIn('gfx_measurestr("999.9ms", wv_tmg, th)', self.layout)
        for phrase in ['Message timing jitter', 'Population standard deviation',
                       'Intervals >4 times the shortest', 'at least 4 accepted intervals',
                       'steady <=5; even >5 to 15; uneven >15 to 30; loose >30 to 50; erratic >50',
                       'slow <=15; moderate >15 to 40; brisk >40 to 70; fast >70',
                       'no measured value travel', 'no data is not evidence of stability',
                       'insufficient data', 'Terms use unrounded values', 'See README']:
            self.assertIn(phrase, self.rows)
        self.assertNotIn('0 accepted intervals', self.rows)
        self.assertIn('slider2 ? strcat(#help_pair, "Frozen - ");', self.rows)


class TooltipRendererTests(unittest.TestCase):
    def setUp(self):
        self.renderer = (SOURCE / 'ccscope_tooltip.jsfx-inc').read_text()
        self.actual = code(self.renderer)

    def rhs(self, name):
        return re.search(r'^\s*' + name + r' = ([^;]+);', self.actual, re.M)[1]

    def test_renderer_is_reusable_no_metric_mouse_slider_or_memory_dependencies(self):
        self.assertNotRegex(self.actual, r'\b(?:mouse_\w+|slider\d*|mem|g_help_\w+|g_metrics_\w+|g_col_\w+)\b')
        self.assertNotRegex(self.actual, r'(?i)messages|jitter|motion|\bCC\b')
        self.assertIn('gfx_a = 1;', self.actual)
        self.assertIn('gfx_r = 0; gfx_g = 0; gfx_b = 0; gfx_a = 1;', self.actual)
        self.assertIn('gfx_setfont(2, "Arial", 16);', self.actual)
        self.assertIn('gfx_setfont(3, "Arial", 18,', self.actual)
        self.assertIn('gfx_mode = 0;', self.actual)
        self.assertIn('old_font = gfx_getfont() + 1;', self.actual)
        self.assertIn('gfx_setfont(old_font);', self.actual)
        self.assertIn('gfx_mode = old_mode;', self.actual)
        self.assertIn('gfx_r = old_r; gfx_g = old_g; gfx_b = old_b; gfx_a = old_a;', self.actual)
        self.assertIn('paint ? (', self.actual)  # identical wrapping for measure/paint

    def test_static_wrapping_is_cached_and_description_is_separate(self):
        self.assertIn('function tip_sample_lines(samples, width, leading)', self.actual)
        self.assertIn('tip_cache_live_lines = tip_sample_lines(samples, width, body_leading);', self.actual)
        for dependency in ('tip_cache_width != width', 'tip_cache_title_leading != title_leading',
                           'tip_cache_body_leading != body_leading',
                           'strcmp(#tip_cache_title, title)', 'strcmp(#tip_cache_full, full_body)',
                           'strcmp(#tip_cache_compact, compact_body)', 'strcmp(#tip_cache_samples, samples)'):
            self.assertIn(dependency, self.actual)
        self.assertIn('gfx_drawstr("Description:");', self.actual)
        self.assertIn('body_y += live_reserve * body_leading + 8;', self.actual)
        self.assertNotIn('6 * body_leading', self.actual)

    def test_actual_geometry_reserves_live_space_and_clamps_to_six_pixel_margins(self):
        # Execute the production arithmetic, independently of unverified native fonts.
        for canvas_w in (100, 251, 252, 300, 1000):
            width = expression(self.rhs('tip_w'), dict(gfx_w=canvas_w))
            self.assertEqual(width, min(520, canvas_w - 12))
            for anchor_x in (-10, 20, canvas_w + 50):
                x = expression(self.rhs('tip_x'), dict(ax=anchor_x, gfx_w=canvas_w, tip_w=width))
                self.assertGreaterEqual(x, 6)
                self.assertLessEqual(x + width, canvas_w - 6)
        for live_reserve in (1, 2, 3, 4, 5, 6):
            for live_lines in range(1, live_reserve + 1):
                values = dict(title_lines=1, full_lines=8, compact_lines=4,
                              live_lines=live_lines, live_reserve=live_reserve,
                              title_leading=22, body_leading=20)
                self.assertEqual(expression(self.rhs('full_h'), values),
                                 58 + (live_reserve + 9) * 20)
                self.assertEqual(expression(self.rhs('compact_h'), values),
                                 58 + (live_reserve + 5) * 20)
        self.assertIn('tip_w >= 240', self.actual)
        self.assertIn('live_lines <= live_reserve && tip_h <= room', self.actual)
        self.assertIn('room = max(top_room, bottom_room);', self.actual)
        self.assertIn('tip_compact = full_h > room;', self.actual)

    def test_new_native_fixture_builds_without_touching_the_package(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'fixture'
            cmd = [sys.executable, str(ROOT / 'tools/ccscope_tooltip_probe.py'),
                   '--source', str(SOURCE), '--output', str(output)]
            result = subprocess.run(cmd, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            fixture = (output / 'tooltip_checks.jsfx').read_text()
            for phrase in ['options:gmem=CCScopeTooltip18', 'help_tiers == 15',
                           'metric_help_dwell(1, 2.399, 0)', 'help_saved_h = tip_h',
                           'help_n == 4 ? 19 : 20', 'get_jitter_quality(5.001)',
                           'help_verify(!tip_visible)', 'gmem[2] = 1']:
                self.assertIn(phrase, fixture)
            self.assertEqual((output / 'ccscope_tooltip.jsfx-inc').read_bytes(),
                             (SOURCE / 'ccscope_tooltip.jsfx-inc').read_bytes())
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)

    def test_acceptance_builder_observes_real_visible_state_and_preserves_legacy_hook(self):
        spec = importlib.util.spec_from_file_location('acceptance', ROOT / 'tools/ccscope_acceptance_probe.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIn('gmem[70] = tip_visible;', module.instrument((SOURCE / 'ccscope.jsfx').read_text(), 'candidate'))
        self.assertEqual(module.instrument_rows((SOURCE / 'ccscope_rows.jsfx-inc').read_text()),
                         (SOURCE / 'ccscope_rows.jsfx-inc').read_text())
        self.assertIn('gmem[70] = hit;', module.instrument_rows('  hit && mouse_x > 0 && mouse_y > 0 ? ('))
        lua = (ROOT / 'tools/ccscope_acceptance_runner.lua').read_text()
        self.assertIn("g(22)==20,'Time-window ladder step failed'", lua)
        self.assertIn('wait(0.45)', lua)


if __name__ == '__main__':
    unittest.main()
