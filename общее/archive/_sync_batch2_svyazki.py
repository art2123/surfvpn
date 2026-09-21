# -*- coding: utf-8 -*-
"""Sync cabinet adsList → Связки for batch2 create results."""
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

FAILS = {
    "tga_b_x_t01_s_v2raytunbot_eur": "fail: Target bot MAU < 1000/day",
    "tga_b_x_t04_s_v2raytunbot_eur": "fail: Target bot MAU < 1000/day",
    "tga_c_x_t01_s_atelecomprov_eur": "fail: Target channel < 1000 subscribers",
    "tga_c_x_t04_s_atelecomprov_eur": "fail: Target channel < 1000 subscribers",
}

CABINET_JSON = Path(__file__).resolve().parent.parent / "secrets" / "batch2_cabinet_ads.json"


def main() -> None:
    ads = json.loads(CABINET_JSON.read_text(encoding="utf-8"))
    by_title = {a["title"]: a for a in ads}

    ss = gspread.authorize(
        Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    ).open_by_key(SHEET_ID)
    ws = ss.worksheet("Связки")
    vals = ws.get_all_values()
    h = vals[0]
    idx = {c: i for i, c in enumerate(h)}

    updates = []  # (row_1based, col_1based, value)
    synced = 0
    failed = 0
    skipped = 0

    for r_i, row in enumerate(vals[1:], start=2):
        while len(row) < len(h):
            row.append("")
        sp = row[idx["start_param"]].strip()
        if not sp.startswith("tga_"):
            continue

        if sp in FAILS:
            note = FAILS[sp]
            if row[idx["статус"]] != "fail" or row[idx.get("заметка", -1)] != note:
                updates.append((r_i, idx["статус"] + 1, "fail"))
                if "заметка" in idx:
                    updates.append((r_i, idx["заметка"] + 1, note))
                failed += 1
            continue

        ad = by_title.get(sp)
        if not ad:
            skipped += 1
            continue

        ad_id = str(ad["ad_id"])
        ads_url = f"https://ads.telegram.org/account/ad/{ad_id}"
        status = ad["status"]
        cpm = str(ad["cpm"]).replace(".", ",") if isinstance(ad["cpm"], float) else str(ad["cpm"])
        # keep euro-dot for consistency with existing sheet if they use dot
        cpm = str(ad["cpm"])
        budget = str(ad["budget"])
        daily = str(ad["daily_budget"])

        fields = {
            "ad_id": ad_id,
            "ads_url": ads_url,
            "статус": status,
            "cpm": cpm,
            "budget": budget,
            "daily_budget": daily,
        }
        changed = False
        for col, val in fields.items():
            if col not in idx:
                continue
            if row[idx[col]].strip() != str(val).strip():
                updates.append((r_i, idx[col] + 1, str(val)))
                changed = True
        if changed:
            synced += 1

    # batch update via cells
    if updates:
        cells = []
        for r, c, v in updates:
            cells.append(gspread.Cell(r, c, v))
        # chunk 500
        for i in range(0, len(cells), 400):
            ws.update_cells(cells[i : i + 400], value_input_option="USER_ENTERED")

    print(f"synced_rows={synced} fail_marked={failed} skipped_no_cabinet={skipped} cells={len(updates)}")


if __name__ == "__main__":
    main()
