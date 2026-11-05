#!/usr/bin/env python3
"""Build a test-only native tooltip fixture; never starts REAPER or deploys a plugin."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from ccscope_acceptance_probe import provides


def build(source: Path, output: Path) -> Path:
    main = (source / 'ccscope.jsfx').read_text()
    marker = '@gfx 1000 720'
    if main.count(marker) != 1 or 'import ccscope_tooltip.jsfx-inc' not in main:
        raise ValueError('Unexpected tooltip package/pipeline')
    files = provides(source)
    if output.exists():
        raise ValueError('Use a new temporary output directory')
    driver = Path(__file__).with_suffix('.txt').read_text()
    main = main.split(marker)[0]
    main = main.replace('desc:CCScope', 'desc:CCScope tooltip checks')
    main = main.replace('options:no_meter', 'options:no_meter\noptions:gmem=CCScopeTooltip18')
    output.mkdir(parents=True)
    for file in files:
        shutil.copy2(file, output / file.name)
    target = output / 'tooltip_checks.jsfx'
    target.write_text(main + marker + '\n' + driver)
    return target


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=Path(__file__).resolve().parent.parent / 'ccscope')
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    print(build(args.source, args.output))


if __name__ == '__main__':
    main()
