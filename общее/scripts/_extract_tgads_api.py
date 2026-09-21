# -*- coding: utf-8 -*-
"""Extract Aj.apiRequest method names from downloaded Telegram Ads JS."""
from __future__ import annotations

import re
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parents[1] / "secrets" / "tgads-js"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    methods: dict[str, list[dict]] = {}
    for path in sorted(DIR.glob("*.js")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(
            r"""apiRequest\(\s*['\"]([a-zA-Z0-9_]+)['\"]\s*,\s*""",
            text,
        ):
            name = m.group(1)
            snippet = re.sub(r"\s+", " ", text[m.end() : m.end() + 420])[:300]
            methods.setdefault(name, []).append(
                {"file": path.name, "snippet": snippet}
            )

        for m in re.finditer(
            r"""method:\s*['\"]([a-zA-Z0-9_]+)['\"]""",
            text,
        ):
            # sometimes method is passed as data.method
            name = m.group(1)
            if name not in methods:
                ctx = re.sub(r"\s+", " ", text[max(0, m.start() - 80) : m.end() + 120])
                if "api" in ctx.lower() or "ajax" in ctx.lower():
                    methods.setdefault(name, []).append(
                        {"file": path.name, "snippet": ctx[:300]}
                    )

    print(f"count={len(methods)}")
    for name in sorted(methods):
        hits = methods[name]
        print(f"\n## {name}  ({len(hits)}x · {hits[0]['file']})")
        print(hits[0]["snippet"])


if __name__ == "__main__":
    main()
