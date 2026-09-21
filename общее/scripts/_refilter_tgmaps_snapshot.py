# -*- coding: utf-8 -*-
"""Re-filter latest TgMaps snapshot and rewrite CSV/digest."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from scrape_tgmaps_vpn import (  # noqa: E402
    build_digest,
    destination_from_row,
    is_vpn_candidate,
    looks_ru,
    write_outputs,
)

SNAP = Path(__file__).resolve().parents[1] / "tgads-snapshots"
latest = sorted(SNAP.glob("*_tgmaps_vpn_creatives.json"))[-1]
print("latest", latest.name)
payload = json.loads(latest.read_text(encoding="utf-8"))
creatives = payload.get("creatives") or []
placements = payload.get("placements") or []
snap_at = payload.get("snapshot_at") or ""

kept = []
kept_uuids = set()
for row in creatives:
    if not is_vpn_candidate(row):
        continue
    if not looks_ru(row):
        continue
    dest = row.get("_destination") or destination_from_row(row)
    if not dest:
        continue
    row["_destination"] = dest
    kept.append(row)
    kept_uuids.add(row.get("uuid"))

placements = [p for p in placements if p.get("creative_uuid") in kept_uuids]
print(
    f"kept creatives={len(kept)} brands={len({c['_destination'].lower() for c in kept})} "
    f"placements={len(placements)}"
)
raw, c_csv, p_csv, digest = write_outputs(kept, placements, snap_at)
# also refresh snapshot content
payload["creatives"] = kept
payload["placements"] = placements
payload["filtered"] = True
latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print("updated", latest)
print("wrote", digest)
print(build_digest(kept, placements, snap_at)[:1200])
