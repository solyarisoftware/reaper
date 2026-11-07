#!/usr/bin/env python3
"""Check every declared CCScope memory range, including GUI graph indexing.

This checks address arithmetic, not EEL2 execution or thread safety.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re


def check(root: Path) -> list[str]:
    utils = (root / 'ccscope_utils.jsfx-inc').read_text()
    metrics = (root / 'ccscope_metrics.jsfx-inc').read_text()
    controlbar = ''
    controlbar_path = root / 'ccscope_controlbar.jsfx-inc'
    if controlbar_path.exists():
        controlbar = controlbar_path.read_text()
    constants: dict[str, int] = {}
    for name, expr in re.findall(
        r'^\s*([A-Za-z_]\w*)\s*=\s*([A-Za-z_0-9+*/() \t-]+?)\s*;',
        utils + '\n' + metrics, re.M,
    ):
        # Expressions are limited to identifiers, integer literals and arithmetic;
        # no attribute access, calls, strings or indexing are accepted.
        try:
            constants[name] = int(eval(expr, {'__builtins__': {}}, constants))
        except (NameError, SyntaxError, TypeError, ZeroDivisionError):
            continue
    shift_match = re.search(
        r'function\s+make_cc_channel_key\b.*?\(\s*\(\s*cc_num\s*<<\s*(\d+)\s*\)\s*\|\s*channel\s*\)',
        utils, re.S,
    )
    if not shift_match:
        return ['Cannot identify dense pair-key encoding']
    shift = int(shift_match[1])
    c = constants
    pairs = c['MAX_CC_CHANNEL_PAIRS']
    history = c['MAX_HISTORY_ITEMS']
    sizes = {
        'MEM_CC_VALUES': 2048, 'MEM_CC_ACTIVE': 128, 'MEM_CC_CHANNEL_ACTIVE': 128,
        'MEM_CC_SORTED': pairs,
        'MEM_COLOR_PALETTE': c['COLOR_PALETTE_SIZE'] * 3,
        'MEM_HISTORY_BASE': history * 4,
        'MEM_HISTORY_WRITE': 1, 'MEM_HISTORY_COUNT': 1,
        'MEM_PAIR_LIST_COUNT': 1,
        'MEM_CBM_BASE': c['MEM_CBM_SIZE'],
        'MEM_WIN_LIST': c['MEM_WIN_LIST_SIZE'],
        'metrics_base': 128 * 16 * c['CC_BLOCK_SIZE'],
        'MEM_EVENT_COUNT': 1,
        'MEM_PLOT_STATE': pairs * c['PLOT_STATE_STRIDE'],
        'MEM_PLOT_COUNT': pairs,
        'MEM_PLOT_SLOT': pairs,
        'MEM_EVENT_RING': c['EVENT_CAPACITY'] * 2,
    }
    regions = sorted((c[name], c[name] + size, name) for name, size in sizes.items())
    errors = []
    for (_, end, name), (start, _, following) in zip(regions, regions[1:]):
        if end > start:
            errors.append(f'{name} overlaps {following}: {end} > {start}')
    if pairs != 128 * 16 or shift != 4 or ((127 << shift) | 15) >= sizes['MEM_CC_VALUES']:
        errors.append('Pair count or dense-key capacity does not fit')
    if c['CC_BLOCK_SIZE'] < 2 + c['MAX_EVENTS_PER_CC'] * 3:
        errors.append('Metric block cannot hold its declared events')
    if c['EVENT_CAPACITY'] < c['MIN_EVENT_HISTORY_SECONDS'] * c['EVENT_FLOOD_HZ']:
        errors.append('Event ring cannot retain the full 30-second window at the declared flood rate')
    # The state block must be exactly one stride per pair: a pair that indexes
    # past it lands in the next array, and the failure would be a wrong pixel,
    # never an error. Derived from the stride, not from a literal, so growing the
    # per-pair state stays a one-line change in the plugin.
    if c['MEM_PLOT_COUNT'] - c['MEM_PLOT_STATE'] != c['PLOT_STATE_STRIDE'] * pairs:
        errors.append('Per-pair plot state does not fit its declared stride')
    # The module declares its own block end; the host declares how much room it
    # reserved. A block that grew past its reservation would overwrite the list
    # tables placed after it, silently. A fixture that carries no module has
    # nothing to compare against, so the check is skipped rather than failed.
    if controlbar:
        block_end = re.search(r'^CBM_ARRAYS_END\s*=\s*(\d+)\s*;', controlbar, re.M)
        if not block_end:
            errors.append('Cannot identify the control-bar block size')
        elif c['MEM_CBM_SIZE'] < int(block_end[1]):
            errors.append(f"Control-bar block needs {block_end[1]} slots, "
                          f"MEM_CBM_SIZE reserves {c['MEM_CBM_SIZE']}")
    if max(end for _, end, _ in regions) > 8388608:
        errors.append('Memory ranges exceed the default JSFX 8M-slot capacity')
    if any(start < 0 or end <= start for start, end, _ in regions):
        errors.append('Invalid range bounds')
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path,
                    default=Path(__file__).resolve().parent.parent / 'ccscope')
    args = ap.parse_args()
    errors = check(args.source)
    for error in errors:
        print(f'FAIL: {error}')
    if not errors:
        print('PASS: all CCScope ranges, pair keys, control-bar block and metric capacity fit')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
