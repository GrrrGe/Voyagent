#!/usr/bin/env python3
"""Scan every first-party frontend file, prompt, and backend copy string."""
from pathlib import Path
import sys
import re
import html
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.copy_policy import violations

def scan(root=ROOT):
    candidates = []
    for directory in ('templates', 'static', 'prompts', 'agents', 'tools'):
        candidates += [p for p in (root / directory).rglob('*') if p.suffix in {'.html', '.js', '.css', '.svg', '.txt', '.py', '.json'}
                       and 'fonts' not in p.parts and p.name != 'copy_policy.py']
    candidates += [root / name for name in ('app.py', 'backend.py', 'security.py') if (root / name).exists()]
    errors = []
    for path in candidates:
        for number, line in enumerate(path.read_text().splitlines(), 1):
            line = html.unescape(line)
            line = re.sub(r'\\u(?:201[34]|\{201[34]\})', lambda m: chr(int(m[0][2:].strip('{}'), 16)), line, flags=re.I)
            errors.extend(f'{path.relative_to(root)}:{number}: {word}' for word in violations(line))
    return errors

if __name__ == '__main__':
    errors = scan()
    print('\n'.join(errors) if errors else 'Copy lint passed.')
    raise SystemExit(bool(errors))
