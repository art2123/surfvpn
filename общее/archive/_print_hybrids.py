# -*- coding: utf-8 -*-
import json
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "imports" / "ti_hybrid_expanded.json"
d = json.loads(p.read_text(encoding="utf-8"))
for key in ["hybrid_media", "hybrid_vpn_brand", "vpnish_media"]:
    rows = d.get(key, [])
    print(f"=== {key} ({len(rows)}) ===")
    for r in rows[:30]:
        title = (r.get("title") or "")[:55]
        print(f"  @{r['login']}: {title} flags={r.get('flags')}")
