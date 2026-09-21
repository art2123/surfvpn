# -*- coding: utf-8 -*-
"""One-off / reusable: merge sheet Связки + cabinet scrape into dated snapshot."""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google.oauth2.service_account import Credentials
import gspread

CREDS = Path(r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json")
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
OUT_DIR = Path(__file__).resolve().parents[1] / "tgads-snapshots"
TZ = ZoneInfo("Europe/Berlin")
LIVE = {"On Hold", "Active"}

# Parsed from ads.telegram.org/account row_text:
# title url views clicks actions … cpm … spent spent budget budget target status date
ROW_RE = re.compile(
    r"^(?P<title>tga_\S+)\s+"
    r"(?P<url>\S+)\s+"
    r"(?P<views>\d+)\s+(?P<clicks>\d+)\s+(?P<actions>\d+)\s+"
    r".*?"
    r"€(?P<cpm>[\d.]+)\s+"
    r".*?"
    r"€(?P<spent>[\d.]+)\s+€(?P<spent2>[\d.]+)\s+"
    r"€(?P<budget>[\d.]+)\s+€(?P<daily>[\d.]+)\s+"
    r"(?P<target>.+?)\s+"
    r"(?P<status>On Hold|Active|Stopped)\s+"
    r"(?P<date_added>.+)$"
)


def parse_cabinet_ads(ads: list[dict]) -> list[dict]:
    out = []
    for a in ads:
        text = a.get("row_text") or ""
        m = ROW_RE.match(text)
        if not m:
            out.append({"title": a.get("title"), "raw": text, "parse_ok": False})
            continue
        d = m.groupdict()
        views = int(d["views"])
        clicks = int(d["clicks"])
        ctr = round(100.0 * clicks / views, 2) if views else None
        out.append(
            {
                "start_param": d["title"],
                "promote_url": a.get("href") or d["url"],
                "views": views,
                "clicks": clicks,
                "actions": int(d["actions"]),
                "ctr_pct": ctr,
                "cpm": float(d["cpm"]),
                "spent": float(d["spent"]),
                "budget": float(d["budget"]),
                "daily_budget": float(d["daily"]),
                "target": d["target"].strip(),
                "status": d["status"],
                "date_added": d["date_added"].strip(),
                "parse_ok": True,
                "flags": {
                    "ctr_ge_10": bool(ctr is not None and views >= 1000 and ctr >= 10),
                    "zero_delivery": views == 0 and d["status"] == "Active",
                    "budget_almost_gone": float(d["budget"]) > 0
                    and float(d["spent"]) / float(d["budget"]) >= 0.8,
                },
            }
        )
    return out


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    now = datetime.now(TZ)
    stamp = now.strftime("%Y-%m-%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cabinet_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    cabinet = None
    if cabinet_path and cabinet_path.exists():
        cabinet = json.loads(cabinet_path.read_text(encoding="utf-8-sig"))

    ss = gspread.authorize(
        Credentials.from_service_account_file(str(CREDS), scopes=SCOPES)
    ).open_by_key(SHEET_ID)
    vals = ss.worksheet("Связки").get_all_values()
    header = vals[0]
    rows = []
    for raw in vals[1:]:
        while len(raw) < len(header):
            raw.append("")
        rows.append(dict(zip(header, raw)))

    by_status: dict[str, int] = {}
    live = []
    for r in rows:
        st = (r.get("статус") or "").strip() or "(empty)"
        by_status[st] = by_status.get(st, 0) + 1
        if st in LIVE:
            live.append(r)

    cabinet_ads = []
    account_budget = None
    if cabinet:
        cabinet_ads = parse_cabinet_ads(cabinet.get("ads") or [])
        account_budget = cabinet.get("budgetLink")

    payload = {
        "snapshot_at": now.isoformat(timespec="seconds"),
        "timezone": "Europe/Berlin",
        "label": "pre-activate-baseline",
        "purpose": (
            "Baseline before Active: compare later for CTR≥10% (склик), "
            "0 views after Active (raise CPM), spend burn, age since snapshot_at"
        ),
        "account_budget": account_budget,
        "sheet": {
            "id": SHEET_ID,
            "tab": "Связки",
            "total_rows": len(rows),
            "by_status": by_status,
            "live_count": len(live),
            "live_start_params": [r.get("start_param") for r in live],
            "rows": rows,
        },
        "cabinet": {
            "url": "https://ads.telegram.org/account",
            "ads_count": len(cabinet_ads),
            "ads": cabinet_ads,
        },
        "checks": {
            "ctr_ge_10": "pause On Hold if views≥1000 and CTR≥10%",
            "zero_views_4_6h_after_active": "raise CPM +€0.30–0.50",
            "spend_80pct_under_3h": "likely CPM overpay — cut CPM ~20%; see tgads_pace_check.py",
        },
    }

    json_path = OUT_DIR / f"{stamp}_Europe-Berlin.json"
    csv_path = OUT_DIR / f"{stamp}_Europe-Berlin.csv"
    cab_csv = OUT_DIR / f"{stamp}_cabinet.csv"
    latest = OUT_DIR / "latest.json"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    if cabinet_ads:
        fields = [
            "start_param",
            "views",
            "clicks",
            "actions",
            "ctr_pct",
            "cpm",
            "spent",
            "budget",
            "daily_budget",
            "target",
            "status",
            "date_added",
            "promote_url",
        ]
        with cab_csv.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for a in cabinet_ads:
                if a.get("parse_ok"):
                    w.writerow(a)

    print(json_path)
    print(csv_path)
    if cabinet_ads:
        print(cab_csv)
    print(f"snapshot_at={payload['snapshot_at']} live={len(live)} cabinet={len(cabinet_ads)}")


if __name__ == "__main__":
    main()
