# -*- coding: utf-8 -*-
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "secrets" / "contested_chunks"
TPL = """(() => new Promise(async (resolve) => {{
  const b64 = "{b64}";
  const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const items = JSON.parse(new TextDecoder().decode(bin));
  const results = await window.__svCreate(items);
  resolve({{n: items.length, ok: results.filter(r=>r.ok).length, fail: results.filter(r=>!r.ok).length, results}});
}}))()"""

for b64path in sorted(DIR.glob("chunk_*.b64")):
    b64 = b64path.read_text(encoding="ascii").strip()
    out = b64path.with_name(b64path.stem.replace("chunk_", "run") + ".js")
    out.write_text(TPL.format(b64=b64), encoding="utf-8")
    print(out.name, out.stat().st_size)
