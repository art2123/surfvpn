# -*- coding: utf-8 -*-
"""Build CDP expression JS for each batch2 chunk."""
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "secrets" / "batch2_chunks"
TPL = """(() => new Promise(async (resolve) => {{
  const b64 = "{b64}";
  const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const items = JSON.parse(new TextDecoder().decode(bin));
  const results = await window.__svCreate(items);
  resolve({{n: items.length, ok: results.filter(r=>r.ok).length, fail: results.filter(r=>!r.ok).length, results}});
}}))()"""

for b64path in sorted(DIR.glob("chunk_*.b64")):
    b64 = b64path.read_text(encoding="ascii").strip()
    js = TPL.format(b64=b64)
    out = b64path.with_suffix(".js")
    out.write_text(js, encoding="utf-8")
    print(out.name, len(js))
