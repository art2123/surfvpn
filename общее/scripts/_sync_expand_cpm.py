# -*- coding: utf-8 -*-
"""Sync cabinet dump → Связки after expand + CPM raises."""
import json
import sys
from pathlib import Path

from google.oauth2.service_account import Credentials
import gspread

sys.stdout.reconfigure(encoding="utf-8")

CREDS = r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json"
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
CABINET = Path(__file__).resolve().parents[1] / "secrets" / "_cabinet_sync_20260918.json"

EXPAND_IDS = {88, 49, 34, 29, 25, 6}
CPM_RAISE_IDS = {
    99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 87, 86, 85, 84, 83, 82,
    78, 75, 74, 72, 71, 70, 69, 68, 66, 65, 64, 63, 62, 59, 58, 55,
    54, 47, 43, 42, 38, 31, 27, 8,
}


def main() -> None:
    ads = {a["ad_id"]: a for a in json.loads(CABINET.read_text(encoding="utf-8"))}
    ss = gspread.authorize(
        Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    ).open_by_key(SHEET_ID)
    ws = ss.worksheet("Связки")
    vals = ws.get_all_values()
    h = vals[0]
    idx = {c: i for i, c in enumerate(h)}
    cells = []
    expanded = []
    cpm_rows = []

    for r_i, row in enumerate(vals[1:], start=2):
        while len(row) < len(h):
            row.append("")
        aid_s = row[idx["ad_id"]].strip()
        if not aid_s.isdigit():
            continue
        aid = int(aid_s)
        ad = ads.get(aid)
        if not ad:
            continue

        changed_fields = []
        for col, key in (
            ("cpm", "cpm"),
            ("budget", "budget"),
            ("daily_budget", "daily_budget"),
            ("статус", "status"),
        ):
            if col not in idx:
                continue
            new_v = str(ad[key])
            old_v = row[idx[col]].strip().replace(",", ".")
            # normalize compare
            try:
                same = abs(float(old_v) - float(new_v)) < 1e-9 if old_v and new_v else old_v == new_v
            except ValueError:
                same = old_v == new_v
            if col == "статус":
                same = old_v == new_v
            if not same:
                cells.append(gspread.Cell(r_i, idx[col] + 1, new_v))
                changed_fields.append(col)

        note_bits = []
        if aid in EXPAND_IDS:
            note_bits.append("бюджет +€8 (триал/продажа)")
            expanded.append(f"{aid}:{ad['title']}")
        if aid in CPM_RAISE_IDS:
            note_bits.append("CPM +0.5 (views<10)")
            cpm_rows.append(f"{aid}:{ad['title']}:{ad['cpm']}")

        if note_bits and "заметка" in idx:
            old_note = row[idx["заметка"]].strip()
            add = "; ".join(note_bits)
            if add not in old_note:
                new_note = (old_note + "; " + add).strip("; ").strip() if old_note else add
                cells.append(gspread.Cell(r_i, idx["заметка"] + 1, new_note))

    if cells:
        for i in range(0, len(cells), 400):
            ws.update_cells(cells[i : i + 400], value_input_option="USER_ENTERED")

    print(f"cells={len(cells)} expanded={len(expanded)} cpm_raise={len(cpm_rows)}")
    for e in expanded:
        print("EXPAND", e)
    print("cpm_sample", cpm_rows[:5], "...", len(cpm_rows))


if __name__ == "__main__":
    main()
