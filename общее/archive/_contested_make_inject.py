# -*- coding: utf-8 -*-
import base64
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
items = json.loads(
    (ROOT / "secrets/contested_vpn_create_payloads.json").read_text(encoding="utf-8")
)
DONE = {"tga_c_x_t05_s_itopvpnru_eur"}
rest = [i for i in items if i["start_param"] not in DONE]
txs = {i["tx"]: i["text"] for i in items}
specs = [
    {
        "start_param": i["start_param"],
        "login": i["login"],
        "tx": i["tx"],
        "promote_url": i["promote_url"],
        "cpm": 5,
        "budget": 5,
        "daily_budget": 5,
        "active": 1,
        "target_type": "channels",
        "placement": "channel_post",
        "button": "open",
    }
    for i in rest
]
payload = {"txs": txs, "specs": specs}
(ROOT / "secrets/contested_inject.json").write_text(
    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
)
b64 = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode(
    "ascii"
)
(ROOT / "secrets/contested_inject.b64").write_text(b64, encoding="ascii")
# chunks of 8 specs
chunk_dir = ROOT / "secrets/contested_chunks"
for i in range(0, len(specs), 8):
    part = {"txs": txs, "specs": specs[i : i + 8]}
    b = base64.b64encode(json.dumps(part, ensure_ascii=False).encode("utf-8")).decode()
    js = f"""(() => new Promise(async (resolve) => {{
  const b64 = "{b}";
  const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const data = JSON.parse(new TextDecoder().decode(bin));
  const items = data.specs.map(s => ({{
    ...s,
    title: s.start_param,
    text: data.txs[s.tx],
  }}));
  const results = await window.__svCreate(items);
  window.__svAllResults = (window.__svAllResults || []).concat(results);
  resolve({{n: items.length, ok: results.filter(r=>r.ok).length, fail: results.filter(r=>!r.ok).length, results, total: window.__svAllResults.length}});
}}))()"""
    (chunk_dir / f"inj_{i//8:02d}.js").write_text(js, encoding="utf-8")
    print(f"inj_{i//8:02d}.js", len(js), "specs", len(part["specs"]))
print("rest", len(rest), "b64", len(b64))
