# -*- coding: utf-8 -*-
"""List cabinet ads, match Outline+pack2 by title, top up Outline, sync sheet."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from google.oauth2.service_account import Credentials
import gspread
from gspread.utils import rowcol_to_a1
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
SECRETS = ROOT.parent / "secrets"
COOKIES = SECRETS / "_cursor_tgads_cookies.json"
OUTLINE_RESULTS = SECRETS / "outline_budget0_results.json"
PACK2_RESULTS = SECRETS / "contested_pack2_results.json"

CREDS = r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json"
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

OUTLINE_SPS = [f"tga_c_x_t{n:02d}_s_getoutlinevp_eur" for n in range(5, 12)]
PACK2_CODES = (ROOT / "tgads-contested-vpn-pack2-codes.txt").read_text(encoding="utf-8").strip().splitlines()
WANTED = set(OUTLINE_SPS + PACK2_CODES)

LIST_ADS = r"""
async () => {
  const owner_id = Aj.state.ownerId;
  const api = (method, data) => new Promise(res => Aj.apiRequest(method, data, res));
  let ads = [];
  let offset_id = 0;
  const samples = [];
  for (let i = 0; i < 50; i++) {
    const r = await api('getAdsList', { owner_id, offset_id });
    if (r.error) return { error: r.error, ads, offset_id, keys: Object.keys(r||{}) };
    const batch = r.ads || r.ad_list || [];
    if (i === 0 && batch[0]) samples.push(Object.keys(batch[0]));
    if (!batch.length) break;
    ads = ads.concat(batch);
    const last = batch[batch.length - 1];
    const next = last.ad_id || last.id;
    if (!next || next === offset_id) break;
    offset_id = next;
    if (batch.length < 10) break;
  }
  if (Aj.state && Aj.state.adsList && Aj.state.adsList.length) {
    const byId = {};
    for (const a of ads) byId[a.ad_id || a.id] = a;
    for (const a of Aj.state.adsList) byId[a.ad_id || a.id] = a;
    ads = Object.values(byId);
  }
  return { owner_id, n: ads.length, sample_keys: samples[0]||null, ads };
}
"""

TOPUP = r"""
async (ad_id) => {
  const owner_id = Aj.state.ownerId;
  const api = (method, data) => new Promise(res => Aj.apiRequest(method, data, res));
  const out = { ad_id };
  const inc = await api('incrAdBudget', { owner_id, ad_id, amount: 5, popup: 1 });
  out.incr = { error: inc && inc.error, keys: Object.keys(inc||{}), budget: inc && (inc.ad && inc.ad.budget) };
  if (inc && inc.error) { out.ok = false; out.error = inc.error; out.stage = 'incr'; return out; }
  const dailyR = await api('editAdDailyBudget', { owner_id, ad_id, daily_budget: 5, popup: 1 });
  out.daily = { error: dailyR && dailyR.error };
  if (dailyR && dailyR.error) { out.ok = false; out.error = dailyR.error; out.stage = 'daily'; return out; }
  const st = await api('editAdStatus', { owner_id, ad_id, active: 1 });
  out.status = { error: st && st.error };
  if (st && st.error) { out.ok = false; out.error = st.error; out.stage = 'status'; return out; }
  out.ok = true;
  return out;
}
"""


def pad(row, n):
    while len(row) < n:
        row.append("")
    return row


def main():
    cookies_raw = json.loads(COOKIES.read_text(encoding="utf-8"))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context()
        pw = []
        for c in cookies_raw:
            domain = c["domain"][1:] if c["domain"].startswith(".") else c["domain"]
            pw.append(
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": domain,
                    "path": c.get("path") or "/",
                    "secure": bool(c.get("secure", True)),
                    "httpOnly": False,
                }
            )
        context.add_cookies(pw)
        page = context.new_page()
        page.goto("https://ads.telegram.org/account", wait_until="domcontentloaded", timeout=90000)
        for i in range(40):
            owner = page.evaluate("() => typeof Aj !== 'undefined' && Aj.state && Aj.state.ownerId")
            if owner:
                break
            time.sleep(1)
        else:
            raise SystemExit("NO_OWNER")

        # prefer Aj.state.adsList after soft reload
        time.sleep(2)
        listing = page.evaluate(LIST_ADS)
        print("listing n=", listing.get("n"), "error=", listing.get("error"), "keys=", listing.get("sample_keys"))

        ads = listing.get("ads") or []
        by_title = {}
        for a in ads:
            title = a.get("title") or a.get("ad_title") or ""
            if title in WANTED:
                by_title[title] = {
                    "ad_id": a.get("ad_id") or a.get("id"),
                    "status": a.get("status"),
                    "cpm": a.get("cpm"),
                    "budget": a.get("budget"),
                    "daily_budget": a.get("daily_budget"),
                    "active": a.get("active"),
                    "title": title,
                }
        print("matched", len(by_title), "of", len(WANTED))
        missing = sorted(WANTED - set(by_title))
        print("missing", missing)

        # dump a few recent titles for debug
        titles = [(a.get("ad_id") or a.get("id"), a.get("title") or a.get("ad_title")) for a in ads]
        titles_sorted = sorted(titles, key=lambda x: -(x[0] or 0))[:25]
        print("recent titles:")
        for t in titles_sorted:
            print(" ", t)

        # Top up Outline ads that exist with budget 0
        outline_out = []
        for sp in OUTLINE_SPS:
            cab = by_title.get(sp)
            if not cab:
                outline_out.append({"ok": False, "start_param": sp, "error": "not found in cabinet after create"})
                continue
            ad_id = cab["ad_id"]
            budget = cab.get("budget")
            print("Outline found", sp, "ad_id", ad_id, "budget", budget, "status", cab.get("status"))
            # try topup if budget is 0 / empty / low
            try:
                bnum = float(budget) if budget is not None and budget != "" else 0
            except Exception:
                bnum = 0
            if bnum < 5:
                top = page.evaluate(TOPUP, ad_id)
                print("topup", sp, top)
                if not top.get("ok"):
                    outline_out.append(
                        {
                            "ok": False,
                            "start_param": sp,
                            "ad_id": ad_id,
                            "error": top.get("error"),
                            "stage": top.get("stage"),
                            "budget": bnum,
                            "cpm": 5,
                            "daily_budget": cab.get("daily_budget"),
                            "note": f"created; topup fail: {top.get('error')}",
                        }
                    )
                    # stop further outline topups if replenishment blocked
                    if "Budget replenishment" in str(top.get("error") or "") or "unavailable" in str(top.get("error") or "").lower():
                        for sp2 in OUTLINE_SPS[OUTLINE_SPS.index(sp) + 1 :]:
                            cab2 = by_title.get(sp2)
                            outline_out.append(
                                {
                                    "ok": False,
                                    "start_param": sp2,
                                    "ad_id": cab2["ad_id"] if cab2 else None,
                                    "error": f"skipped after topup fail on {sp}",
                                    "stage": "skipped",
                                    "note": f"ad exists budget={cab2.get('budget') if cab2 else '?'}; topup skipped",
                                }
                            )
                        break
                    continue
                outline_out.append(
                    {
                        "ok": True,
                        "start_param": sp,
                        "ad_id": ad_id,
                        "status": "Active",
                        "cpm": 5,
                        "budget": 5,
                        "daily_budget": 5,
                        "note": "outline budget0+topup ok",
                    }
                )
            else:
                outline_out.append(
                    {
                        "ok": True,
                        "start_param": sp,
                        "ad_id": ad_id,
                        "status": "Active",
                        "cpm": cab.get("cpm") or 5,
                        "budget": budget,
                        "daily_budget": cab.get("daily_budget") or 5,
                        "note": "outline already budgeted",
                    }
                )
            time.sleep(0.4)

        # pack2 results from listing
        pack2_out = []
        for sp in PACK2_CODES:
            cab = by_title.get(sp)
            if not cab:
                pack2_out.append({"ok": False, "start_param": sp, "error": "not found in cabinet"})
                continue
            pack2_out.append(
                {
                    "ok": True,
                    "start_param": sp,
                    "ad_id": cab["ad_id"],
                    "status": cab.get("status") or "Active",
                    "cpm": cab.get("cpm") or 5,
                    "budget": cab.get("budget") or 5,
                    "daily_budget": cab.get("daily_budget") or 5,
                    "note": "pack2 synced from cabinet",
                }
            )

        browser.close()

    # write results
    OUTLINE_RESULTS.write_text(json.dumps({"results": outline_out, "matched": len(by_title)}, ensure_ascii=False, indent=2), encoding="utf-8")
    PACK2_RESULTS.write_text(
        json.dumps(
            {
                "ok_count": sum(1 for r in pack2_out if r.get("ok")),
                "fail_count": sum(1 for r in pack2_out if not r.get("ok")),
                "results": pack2_out,
                "codes_file": str(ROOT / "tgads-contested-vpn-pack2-codes.txt"),
                "outline_summary": {
                    "ok": sum(1 for r in outline_out if r.get("ok")),
                    "fail": sum(1 for r in outline_out if not r.get("ok")),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # sync sheet
    ss = gspread.authorize(Credentials.from_service_account_file(CREDS, scopes=SCOPES)).open_by_key(SHEET_ID)
    sv = ss.worksheet("Связки")
    vals = sv.get_all_values()
    h = vals[0]
    si = {c: i for i, c in enumerate(h)}
    all_res = {r["start_param"]: r for r in outline_out + pack2_out}
    batch = []
    for ridx, row in enumerate(vals[1:], start=2):
        row = pad(list(row), len(h))
        sp = row[si["start_param"]]
        if sp not in all_res:
            continue
        r = all_res[sp]
        status = "Active" if r.get("ok") else "fail"
        ad_id = r.get("ad_id") or ""
        ads_url = f"https://ads.telegram.org/account/ad/{ad_id}" if ad_id else ""
        note = r.get("note") or ""
        if r.get("error"):
            note = (note + " " + str(r.get("error"))).strip()[:500]
        mapping = {
            "ad_id": str(ad_id) if ad_id else row[si["ad_id"]],
            "ads_url": ads_url or row[si["ads_url"]],
            "статус": status,
            "cpm": str(r.get("cpm") or 5),
            "budget": str(r.get("budget") if r.get("budget") is not None else (5 if r.get("ok") else row[si["budget"]])),
            "daily_budget": str(r.get("daily_budget") if r.get("daily_budget") is not None else (5 if r.get("ok") else row[si["daily_budget"]])),
            "промокод в админке": "добавлен",
            "заметка": note or row[si["заметка"]],
        }
        for col, val in mapping.items():
            batch.append({"range": rowcol_to_a1(ridx, si[col] + 1), "values": [[val]]})
    for i in range(0, len(batch), 80):
        sv.batch_update(batch[i : i + 80], value_input_option="USER_ENTERED")
    print("sheet cells", len(batch))

    print("\n=== Outline ===")
    for r in outline_out:
        print(("OK" if r.get("ok") else "FAIL"), r.get("start_param"), r.get("ad_id"), r.get("error") or r.get("note"))
    print("\n=== pack2 ===")
    for r in pack2_out:
        print(("OK" if r.get("ok") else "FAIL"), r.get("start_param"), r.get("ad_id"), r.get("error") or "")


if __name__ == "__main__":
    main()
