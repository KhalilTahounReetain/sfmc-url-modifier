#!/usr/bin/env python3
"""
Test local sur fichier HTML
Usage: python test_local.py fichier.html [old] [new]
"""

import sys
import re


def replace_urls(content, old, new):
    changes = []
    result = content

    patterns = [
        (rf'/{re.escape(old)}/(?!-)', f'/{new}/'),
        (rf'/{re.escape(old)}"', f'/{new}"'),
        (rf"/{re.escape(old)}'", f"/{new}'"),
        (rf'/{re.escape(old)}<', f'/{new}<'),
        (rf'/{re.escape(old)}(\s)', f'/{new}\\1'),
        (rf'/{re.escape(old)}\)', f'/{new})'),
    ]

    for pattern, replacement in patterns:
        for m in re.finditer(pattern, content):
            prefix = content[max(0, m.start()-3):m.start()]
            if f'-{old}' in prefix:
                continue
            changes.append({
                'match': m.group(),
                'line': content[:m.start()].count('\n') + 1,
                'context': content[max(0, m.start()-20):m.end()+20].replace('\n', ' ')
            })
        result = re.sub(pattern, replacement, result)

    return result, changes


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_local.py fichier.html [old] [new]")
        sys.exit(1)

    f = sys.argv[1]
    old = sys.argv[2] if len(sys.argv) > 2 else 'fr'
    new = sys.argv[3] if len(sys.argv) > 3 else 'fr-fr'

    print(f"Test: /{old}/ -> /{new}/")
    print(f"Fichier: {f}\n")

    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()

    result, changes = replace_urls(content, old, new)

    print(f"Changements: {len(changes)}\n")
    for i, c in enumerate(changes, 1):
        print(f"{i}. L{c['line']}: {c['match']}")
        print(f"   ...{c['context'][:50]}...")

    out = f.replace('.html', '_modified.html')
    with open(out, 'w', encoding='utf-8') as file:
        file.write(result)
    print(f"\nSauvegardé: {out}")


if __name__ == '__main__':
    main()
