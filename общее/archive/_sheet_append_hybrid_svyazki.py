# -*- coding: utf-8 -*-
"""Append hybrid Связки (t01+t04, CPM/budget €5) and write codes for admin paste."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

CREDS = Path(r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json")
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
OUT = Path(__file__).resolve().parent / "tgads-hybrid-codes.txt"

# New hybrids to upload carefully (€5 / €5). Skip slugs that already have live rows
# with the same start_param — never duplicate codes.
PLATFORMS = [
    ("blokirovki_runeta", "blokiruneta"),
    ("tginfo", "tginfo"),
    ("rozetked", "rozetked"),
    ("roskomsvoboda", "roskomsvoboda"),
    # lagom/quattro/amnezia already have archive rows — skip unless recreating Deleted
]


def main() -> None:
    ss = gspread.authorize(
        Credentials.from_service_account_file(str(CREDS), scopes=SCOPES)
    ).open_by_key(SHEET_ID)
    sv = ss.worksheet("Связки")
    vals = sv.get_all_values()
    h = vals[0]
    existing = {
        (r[h.index("start_param")] or "").strip()
        for r in vals[1:]
        if len(r) > h.index("start_param") and r[h.index("start_param")]
    }

    today = date.today().isoformat()
    texts = ("t01", "t04")
    new_rows = []
    codes = []

    for login, slug in PLATFORMS:
        for tx in texts:
            code = f"tga_c_x_{tx}_s_{slug}_eur"
            codes.append(code)
            if code in existing:
                print(f"skip exists: {code}")
                continue
            row = [""] * len(h)

            def setc(name: str, val: str) -> None:
                if name in h:
                    row[h.index(name)] = val

            setc("start_param", code)
            setc("cab", "eur")
            setc("pl", "c")
            setc("cr", "x")
            setc("tx", tx)
            setc("scope", "s")
            setc("slug", slug)
            setc("дата", today)
            setc("статус", "к заливке")
            setc("cpm", "5")
            setc("budget", "5")
            setc("daily_budget", "5")
            setc("promote_url", f"https://t.me/surfvpn?start={code}")
            setc("промокод в админке", "нет")
            setc("заметка", f"TI-hybrid batch; @{login}; CPM/budget €5; On Hold")
            new_rows.append(row)

    if new_rows:
        sv.append_rows(new_rows, value_input_option="USER_ENTERED")
    OUT.write_text("\n".join(codes) + "\n", encoding="utf-8")
    print(f"Связки +{len(new_rows)}")
    print(f"codes file: {OUT}")
    for c in codes:
        print(c)


if __name__ == "__main__":
    main()
