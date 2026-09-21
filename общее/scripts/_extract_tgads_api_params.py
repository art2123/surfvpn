# -*- coding: utf-8 -*-
"""Pull params blocks for Aj.apiRequest methods from promote.js."""
from __future__ import annotations

import re
import sys
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "secrets" / "tgads-js" / "promote.js"


def brace_object(text: str, start: int) -> str | None:
    """Return object literal starting at text[start]=='{'."""
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_str = None
    esc = False
    for i in range(start, min(len(text), start + 2500)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in "'\"":
            in_str = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    t = JS.read_text(encoding="utf-8", errors="replace")

    for m in re.finditer(r"""Aj\.apiRequest\(\s*['\"]([a-zA-Z0-9_]+)['\"]\s*,\s*""", t):
        name = m.group(1)
        after = t[m.end() : m.end() + 5]
        window = t[max(0, m.start() - 900) : m.start()]
        params_src = None
        if after.startswith("{"):
            params_src = brace_object(t, m.end())
        else:
            # find last `var params = {` or `params = {` in window
            for pm in reversed(list(re.finditer(r"(?:var\s+)?params\s*=\s*\{", window))):
                abs_start = max(0, m.start() - 900) + pm.end() - 1
                params_src = brace_object(t, abs_start)
                if params_src:
                    break
            # also look for assignments params.x =
            assigns = re.findall(r"params\.(\w+)\s*=", window + t[m.start() : m.start() + 200])
        fields = re.findall(r"""\.field\(\s*['\"](\w+)['\"]\s*\)""", window)
        print("=" * 60)
        print(name)
        if params_src:
            compact = re.sub(r"\s+", " ", params_src)
            print(compact[:700])
        else:
            print("(no object)")
            print(re.sub(r"\s+", " ", after[:80]))
        if fields:
            print("fields:", ", ".join(dict.fromkeys(fields)))


if __name__ == "__main__":
    main()
