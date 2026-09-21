# -*- coding: utf-8 -*-
"""Export tga_… codes from Связки for Marketing Panel promo/campaigns.

Paste into admin: one code per line = campaign name + code.
Optional CSV: code;percent → bot promo {SLUG}{percent} from segment before last _.

Usage:
  python общее/scripts/export_tgads_admin_campaigns.py
      # On Hold + Active, where «промокод в админке» ≠ добавлен
  python общее/scripts/export_tgads_admin_campaigns.py --all
      # все уникальные tga_ из архива
  python общее/scripts/export_tgads_admin_campaigns.py --csv 50
      # те же коды в формате код;50
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from google.oauth2.service_account import Credentials
import gspread

CREDS = Path(r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json")
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
TAB = "Связки"
LIVE = {"On Hold", "Active", "к заливке"}
ADDED = {"добавлен", "да", "yes", "1"}
PROMO_COLS = ("промокод в админке", "админка")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="Все уникальные tga_, любой статус")
    ap.add_argument("--csv", type=int, metavar="PERCENT", help="Печать код;процент")
    args = ap.parse_args()

    ss = gspread.authorize(
        Credentials.from_service_account_file(str(CREDS), scopes=SCOPES)
    ).open_by_key(SHEET_ID)
    vals = ss.worksheet(TAB).get_all_values()
    if not vals:
        raise SystemExit("Связки empty")

    header = vals[0]
    i_sp = header.index("start_param")
    i_st = header.index("статус")
    i_promo = next((header.index(c) for c in PROMO_COLS if c in header), None)
    if i_promo is None:
        raise SystemExit(f"Need column {PROMO_COLS} in {header}")

    codes: list[str] = []
    seen: set[str] = set()
    for raw in vals[1:]:
        while len(raw) < len(header):
            raw.append("")
        sp = (raw[i_sp] or "").strip()
        if not sp.startswith("tga_") or sp in seen:
            continue
        status = (raw[i_st] or "").strip()
        promo = (raw[i_promo] or "").strip().lower()
        if not args.all:
            if status not in LIVE:
                continue
            if promo in ADDED:
                continue
        seen.add(sp)
        codes.append(sp)

    if args.csv is not None:
        for code in codes:
            print(f"{code};{args.csv}")
    else:
        for code in codes:
            print(code)

    print(f"# count={len(codes)}", file=sys.stderr)


if __name__ == "__main__":
    main()
