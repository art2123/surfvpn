# -*- coding: utf-8 -*-
"""Compare two cabinet adsList snapshots for CPM overpay / fast spend pace.

Flags (see общее/tgads-кабинет.md):
  быстрый_слив   — Δspent / daily_t0 >= 0.50 and Δhours < 6
  переплата_cpm  — Δspent / daily_t0 >= 0.80 and Δhours < 3

Usage:
  python общее/scripts/tgads_pace_check.py
  python общее/scripts/tgads_pace_check.py snap_t0.json snap_t1.json
  python общее/scripts/tgads_pace_check.py --apply snap_t0.json snap_t1.json

Default paths (if omitted):
  t0 = общее/tgads-snapshots/prev_cabinet_ads.json
  t1 = общее/tgads-snapshots/latest_cabinet_ads.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google.oauth2.service_account import Credentials
import gspread

ROOT = Path(__file__).resolve().parents[1]
SNAP_DIR = ROOT / "tgads-snapshots"
CREDS = Path(r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json")
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
TZ = ZoneInfo("Europe/Berlin")


def load_snap(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        return {
            "snapshot_at": None,
            "ads": [
                {
                    "ad_id": a.get("ad_id"),
                    "title": a.get("title") or a.get("start_param"),
                    "status": a.get("status"),
                    "views": int(a.get("views") or 0),
                    "clicks": int(a.get("clicks") or 0),
                    "cpm": float(a.get("cpm") or 0),
                    "spent": float(a.get("spent") or 0),
                    "budget": float(a.get("budget") or 0),
                    "daily_budget": float(a.get("daily_budget") or 0),
                }
                for a in data
                if str(a.get("title") or a.get("start_param") or "").startswith("tga_")
            ],
        }
    ads = data.get("ads") or []
    return {
        "snapshot_at": data.get("snapshot_at"),
        "ads": [
            {
                "ad_id": a.get("ad_id"),
                "title": a.get("title") or a.get("start_param"),
                "status": a.get("status"),
                "views": int(a.get("views") or 0),
                "clicks": int(a.get("clicks") or 0),
                "cpm": float(a.get("cpm") or 0),
                "spent": float(a.get("spent") or 0),
                "budget": float(a.get("budget") or 0),
                "daily_budget": float(a.get("daily_budget") or 0),
            }
            for a in ads
            if str(a.get("title") or a.get("start_param") or "").startswith("tga_")
        ],
    }


def parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt
    except ValueError:
        return None


def by_key(ads: list[dict]) -> dict[str, dict]:
    out = {}
    for a in ads:
        key = str(a.get("ad_id") or a.get("title"))
        out[key] = a
    return out


def compare(t0: dict, t1: dict) -> list[dict]:
    ts0 = parse_ts(t0.get("snapshot_at"))
    ts1 = parse_ts(t1.get("snapshot_at"))
    if ts0 and ts1:
        delta_hours = max((ts1 - ts0).total_seconds() / 3600.0, 0.0)
    else:
        delta_hours = None

    m0 = by_key(t0["ads"])
    m1 = by_key(t1["ads"])
    rows = []
    for key, a1 in m1.items():
        a0 = m0.get(key)
        if not a0:
            continue
        if str(a1.get("status")) not in ("Active", "On Hold", "In Review"):
            continue
        daily = float(a0.get("daily_budget") or 0)
        if daily <= 0.01:
            continue
        d_spent = float(a1.get("spent") or 0) - float(a0.get("spent") or 0)
        if d_spent < 0:
            # spent reset / new day noise — skip negative
            continue
        d_views = int(a1.get("views") or 0) - int(a0.get("views") or 0)
        burn_pct = d_spent / daily if daily else 0.0
        dh = delta_hours if delta_hours is not None else 0.0

        flags = []
        if delta_hours is not None and delta_hours > 0:
            if burn_pct >= 0.8 and delta_hours < 3:
                flags.append("переплата_cpm")
            elif burn_pct >= 0.5 and delta_hours < 6:
                flags.append("быстрый_слив")

        rows.append(
            {
                "ad_id": a1.get("ad_id"),
                "title": a1.get("title"),
                "status": a1.get("status"),
                "cpm": a1.get("cpm"),
                "daily_t0": round(daily, 4),
                "delta_spent": round(d_spent, 4),
                "delta_views": d_views,
                "burn_pct": round(burn_pct, 4),
                "delta_hours": round(dh, 3) if delta_hours is not None else None,
                "flags": flags,
            }
        )

    rows.sort(key=lambda r: (-len(r["flags"]), -r["burn_pct"]))
    return rows


def note_for(row: dict, when: datetime) -> str | None:
    if not row["flags"]:
        return None
    label = "переплата CPM" if "переплата_cpm" in row["flags"] else "быстрый слив"
    dh = row["delta_hours"]
    dh_s = f"{dh:.1f}h" if dh is not None else "?h"
    return (
        f"{label} {when.strftime('%Y-%m-%d %H:%M')} "
        f"(Δ€{row['delta_spent']} / daily €{row['daily_t0']} за {dh_s}, cpm={row['cpm']})"
    )


def apply_sheet(rows: list[dict], t1: dict) -> int:
    when = parse_ts(t1.get("snapshot_at")) or datetime.now(TZ)
    flagged = [r for r in rows if r["flags"]]
    if not flagged:
        return 0

    by_id = {str(r["ad_id"]): r for r in flagged if r.get("ad_id") is not None}
    by_title = {r["title"]: r for r in flagged}

    ss = gspread.authorize(
        Credentials.from_service_account_file(str(CREDS), scopes=SCOPES)
    ).open_by_key(SHEET_ID)
    ws = ss.worksheet("Связки")
    vals = ws.get_all_values()
    h = vals[0]
    idx = {c: i for i, c in enumerate(h)}
    if "заметка" not in idx:
        raise SystemExit("column заметка missing in Связки")

    # optional sync budget/cpm/daily from t1
    t1_by_id = {str(a["ad_id"]): a for a in t1["ads"] if a.get("ad_id") is not None}

    cells = []
    applied = 0
    for r_i, row in enumerate(vals[1:], start=2):
        while len(row) < len(h):
            row.append("")
        aid = row[idx["ad_id"]].strip()
        sp = row[idx["start_param"]].strip() if "start_param" in idx else ""
        hit = by_id.get(aid) or by_title.get(sp)
        if not hit:
            continue
        add = note_for(hit, when)
        if not add:
            continue
        old = row[idx["заметка"]].strip()
        if add not in old and "переплата CPM" not in old and "быстрый слив" not in old:
            new_note = (old + "; " + add).strip("; ").strip() if old else add
            cells.append(gspread.Cell(r_i, idx["заметка"] + 1, new_note))
            applied += 1

        cab = t1_by_id.get(aid)
        if cab:
            for col, key in (
                ("cpm", "cpm"),
                ("budget", "budget"),
                ("daily_budget", "daily_budget"),
                ("статус", "status"),
            ):
                if col not in idx:
                    continue
                new_v = str(cab.get(key, ""))
                old_v = row[idx[col]].strip()
                if new_v and old_v != new_v:
                    cells.append(gspread.Cell(r_i, idx[col] + 1, new_v))

    if cells:
        for i in range(0, len(cells), 400):
            ws.update_cells(cells[i : i + 400], value_input_option="USER_ENTERED")
    return applied


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description="TG Ads spend pace / CPM overpay check")
    ap.add_argument("t0", nargs="?", default=str(SNAP_DIR / "prev_cabinet_ads.json"))
    ap.add_argument("t1", nargs="?", default=str(SNAP_DIR / "latest_cabinet_ads.json"))
    ap.add_argument(
        "--apply",
        action="store_true",
        help="write flags into Связки.заметка (no auto CPM/status change)",
    )
    args = ap.parse_args()

    p0, p1 = Path(args.t0), Path(args.t1)
    if not p0.exists() or not p1.exists():
        print(
            f"Need two snapshots.\n  t0={p0} exists={p0.exists()}\n  t1={p1} exists={p1.exists()}\n"
            "Dump adsList twice via snapshot_cabinet_ads.py, keep dated files, then:\n"
            "  python общее/scripts/tgads_pace_check.py snap_t0.json snap_t1.json [--apply]",
            file=sys.stderr,
        )
        sys.exit(1)

    t0, t1 = load_snap(p0), load_snap(p1)
    rows = compare(t0, t1)
    flagged = [r for r in rows if r["flags"]]

    print(f"t0={t0.get('snapshot_at')} ({p0.name})")
    print(f"t1={t1.get('snapshot_at')} ({p1.name})")
    print(f"compared={len(rows)} flagged={len(flagged)}")
    print(
        "ad_id\ttitle\tcpm\tdΔspent\tdaily\tburn%\tdh\tflags\tdΔviews"
    )
    for r in rows:
        if not r["flags"] and r["burn_pct"] < 0.2:
            continue
        print(
            f"{r['ad_id']}\t{r['title']}\t{r['cpm']}\t{r['delta_spent']}\t"
            f"{r['daily_t0']}\t{r['burn_pct']:.0%}\t{r['delta_hours']}\t"
            f"{','.join(r['flags']) or '-'}\t{r['delta_views']}"
        )

    out = SNAP_DIR / "latest_pace_report.json"
    out.write_text(
        json.dumps(
            {
                "t0": t0.get("snapshot_at"),
                "t1": t1.get("snapshot_at"),
                "flagged": flagged,
                "all": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(out)

    if args.apply:
        n = apply_sheet(rows, t1)
        print(f"sheet_notes_applied={n}")


if __name__ == "__main__":
    main()
