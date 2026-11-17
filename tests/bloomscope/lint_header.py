#!/usr/bin/env python3
"""Offline BloomScope package checks; not JSFX compilation or ReaPack validation."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'bloomscope'


def check(package=PACKAGE):
    errors = []
    main = package / 'bloomscope.jsfx'
    text = main.read_text()
    header = text.split('options:no_meter', 1)[0]
    if text.splitlines()[0] != 'desc:BloomScope':
        errors.append('desc:BloomScope must be on line 1')
    for tag in ('description', 'author', 'version', 'about', 'provides', 'changelog'):
        if not re.search(r'^// @' + tag + r'\b', header, re.MULTILINE):
            errors.append('missing @' + tag)
    imports = re.findall(r'^import (\S+)$', text, re.MULTILINE)
    if len(imports) != 9 or len(set(imports)) != 9:
        errors.append('expected nine distinct package-local includes')
    for name in imports:
        if not name.startswith('bloomscope_') or not (package / name).is_file():
            errors.append('missing or unowned include: ' + name)
        if '//   ' + name + '\n' not in header:
            errors.append('include missing from @provides: ' + name)
    if '//   [script main=main] bloomscope_loop_companion.lua\n' not in header:
        errors.append('companion must be provided as a Main script')
    action = package / 'bloomscope_loop_companion.lua'
    if not action.is_file() or '-- @noindex\n' not in action.read_text():
        errors.append('companion must exist and avoid standalone indexing')
    for pin in ('in_pin:left input', 'in_pin:right input',
                'out_pin:left output', 'out_pin:right output'):
        if pin not in text:
            errors.append('missing stereo pin: ' + pin)
    for path in package.iterdir():
        if path.suffix not in ('.jsfx', '.jsfx-inc', '.lua'):
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if path.suffix == '.jsfx' and len(line) > 200:
                errors.append(f'{path.name}:{number}: header/conductor line exceeds 200 characters')
    return errors


if __name__ == '__main__':
    failures = check()
    for failure in failures:
        print('ERROR:', failure, file=sys.stderr)
    print(f'BloomScope package: {len(failures)} error(s)')
    raise SystemExit(bool(failures))
