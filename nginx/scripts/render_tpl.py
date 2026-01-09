#!/usr/bin/env python3
import sys
from pathlib import Path

def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: render_tpl.py <template> <output> [KEY=VALUE ...]", file=sys.stderr)
        return 2

    template_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    replacements = {}
    for arg in sys.argv[3:]:
        if "=" not in arg:
            print(f"Invalid arg: {arg} (expected KEY=VALUE)", file=sys.stderr)
            return 2
        key, value = arg.split("=", 1)
        replacements[key] = value

    text = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace("{{" + key + "}}", value)

    output_path.write_text(text, encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
