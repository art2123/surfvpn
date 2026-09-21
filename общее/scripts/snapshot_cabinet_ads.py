# -*- coding: utf-8 -*-
"""Snapshot Telegram Ads cabinet from adsList JSON (or live dump file).

Usage:
  # from a previously saved Aj.state.adsList dump:
  python общее/scripts/snapshot_cabinet_ads.py path/to/adslist.json

  # stdin / default: reads JSON array or {ads: [...], snapshot_at?: ...}
  python общее/scripts/snapshot_cabinet_ads.py adslist.json

Writes:
  общее/tgads-snapshots/YYYY-MM-DD_HHMMSS_cabinet_ads.json
  общее/tgads-snapshots/latest_cabinet_ads.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

OUT_DIR = Path(__file__).resolve().parents[1] / "tgads-snapshots"
TZ = ZoneInfo("Europe/Berlin")


def normalize_ads(raw) -> list[dict]:
    if isinstance(raw, dict):
        ads = raw.get("ads") or raw.get("adsList") or []
        snap_at = raw.get("snapshot_at")
    elif isinstance(raw, list):
        ads = raw
        snap_at = None
    else:
        raise ValueError("expected list or {ads: [...]} JSON")

    out = []
    for a in ads:
        title = (a.get("title") or a.get("start_param") or "").strip()
        if not title.startswith("tga_"):
            continue
        out.append(
            {
                "ad_id": a.get("ad_id"),
                "title": title,
                "status": a.get("status"),
                "views": int(a.get("views") or 0),
                "clicks": int(a.get("clicks") or 0),
                "cpm": float(a.get("cpm") or 0),
                "spent": float(a.get("spent") or 0),
                "budget": float(a.get("budget") or 0),
                "daily_budget": float(a.get("daily_budget") or 0),
            }
        )
    return out, snap_at


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) < 2:
        print(
            "Usage: python общее/scripts/snapshot_cabinet_ads.py path/to/adslist.json",
            file=sys.stderr,
        )
        sys.exit(2)

    src = Path(sys.argv[1])
    raw = json.loads(src.read_text(encoding="utf-8-sig"))
    ads, snap_at_in = normalize_ads(raw)

    now = datetime.now(TZ)
    snap_at = snap_at_in or now.isoformat(timespec="seconds")
    stamp = now.strftime("%Y-%m-%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "snapshot_at": snap_at,
        "timezone": "Europe/Berlin",
        "source": str(src),
        "ads_count": len(ads),
        "ads": ads,
    }

    dated = OUT_DIR / f"{stamp}_cabinet_ads.json"
    latest = OUT_DIR / "latest_cabinet_ads.json"
    prev = OUT_DIR / "prev_cabinet_ads.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2)

    # Rotate: previous latest becomes prev (for tgads_pace_check.py defaults)
    if latest.exists():
        prev.write_text(latest.read_text(encoding="utf-8"), encoding="utf-8")

    dated.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")

    print(dated)
    print(latest)
    if prev.exists():
        print(prev)
    print(f"snapshot_at={snap_at} ads={len(ads)}")


if __name__ == "__main__":
    main()
