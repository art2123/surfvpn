# -*- coding: utf-8 -*-
"""A) Retry Outline ads with budget=0 then top-up.
B) Prepare + create 15 pack2 ads on new VPN channels.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import date
from pathlib import Path

from google.oauth2.service_account import Credentials
import gspread
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
SECRETS = ROOT.parent / "secrets"
COOKIES = SECRETS / "_cursor_tgads_cookies.json"
OUTLINE_RESULTS = SECRETS / "outline_budget0_results.json"
PACK2_RESULTS = SECRETS / "contested_pack2_results.json"
PACK2_CODES = ROOT / "tgads-contested-vpn-pack2-codes.txt"

CREDS = r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json"
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

OUTLINE_LOGIN = "getoutlinevpn_channel"
OUTLINE_TEXTS = [f"t{n:02d}" for n in range(5, 12)]  # t05..t11
OUTLINE_SPS = [f"tga_c_x_{tx}_s_getoutlinevp_eur" for tx in OUTLINE_TEXTS]

PACK2_CHANNELS = [
    {"login": "safe_runet", "title": "Общество Защиты Интернета"},
    {"login": "vpndrift", "title": "DriftVPN - Новости"},
    {"login": "sotavpn", "title": "Sota VPN — Канал"},
    {"login": "runvpn", "title": "Run VPN Run"},
    {"login": "purrnet_news", "title": "Новости PurrNet VPN"},
]
PACK2_TEXTS = ["t05", "t08", "t06"]  # order as requested

SV_HELPERS = r"""
window.__svTargetCache = window.__svTargetCache || {};
window.__svApi = (method, data) => new Promise(res => Aj.apiRequest(method, data, res));
window.__svResolveChannel = async function(login) {
  const owner_id = Aj.state.ownerId;
  const key = 'channels:' + login.toLowerCase();
  if (window.__svTargetCache[key]) return window.__svTargetCache[key];
  const r = await window.__svApi('searchChannel', { owner_id, query: 'https://t.me/' + login, field: 'channels' });
  if (r.error || !r.channel) {
    window.__svTargetCache[key] = { error: (r && r.error) || 'no channel' };
    return window.__svTargetCache[key];
  }
  window.__svTargetCache[key] = { val: r.channel.val };
  return window.__svTargetCache[key];
};
window.__svCreateOne = async function(item) {
  const owner_id = Aj.state.ownerId;
  const t = await window.__svResolveChannel(item.login);
  if (t.error) return { ok:false, start_param:item.start_param, error:t.error, stage:'target' };
  const params = {
    owner_id,
    title: item.title || item.start_param,
    text: item.text,
    button: item.button || 'open',
    promote_url: item.promote_url,
    website_name: '', website_photo: '', media: '', ad_info: '',
    cpm: item.cpm,
    views_per_user: item.views_per_user != null ? item.views_per_user : 1,
    budget: item.budget,
    daily_budget: item.daily_budget,
    active: item.active != null ? item.active : 1,
    target_type: 'channels',
    placement: item.placement || 'channel_post',
    device: item.device || '',
    channels: t.val
  };
  const r = await window.__svApi('createAd', params);
  if (r.error) return { ok:false, start_param:item.start_param, error:r.error, field:r.field, stage:'create', raw:r };
  const ad_id = (r.ad && (r.ad.ad_id || r.ad.id)) || r.ad_id || null;
  return { ok:true, start_param:item.start_param, ad_id, redirect: r.redirect_to||null, raw_keys: Object.keys(r||{}) };
};
window.__svTopUp = async function(ad_id, amount, daily) {
  const owner_id = Aj.state.ownerId;
  const out = { ad_id };
  const inc = await window.__svApi('incrAdBudget', { owner_id, ad_id, amount, popup: 1 });
  out.incr = inc;
  if (inc && inc.error) { out.ok = false; out.error = inc.error; out.stage = 'incr'; return out; }
  const dailyR = await window.__svApi('editAdDailyBudget', { owner_id, ad_id, daily_budget: daily, popup: 1 });
  out.daily = dailyR;
  if (dailyR && dailyR.error) { out.ok = false; out.error = dailyR.error; out.stage = 'daily'; return out; }
  const st = await window.__svApi('editAdStatus', { owner_id, ad_id, active: 1 });
  out.status = st;
  if (st && st.error) { out.ok = false; out.error = st.error; out.stage = 'status'; return out; }
  out.ok = true;
  return out;
};
window.__svFindAdByTitle = async function(title) {
  const owner_id = Aj.state.ownerId;
  let ads = [];
  let offset_id = 0;
  for (let i = 0; i < 40; i++) {
    const r = await window.__svApi('getAdsList', { owner_id, offset_id });
    if (r.error) return { error: r.error };
    const batch = r.ads || r.ad_list || [];
    if (!batch.length) break;
    ads = ads.concat(batch);
    const last = batch[batch.length - 1];
    offset_id = last.ad_id || last.id || offset_id;
    if (batch.length < 20) break;
  }
  if (Aj.state && Aj.state.adsList && Aj.state.adsList.length) {
    const byId = {};
    for (const a of ads) byId[a.ad_id || a.id] = a;
    for (const a of Aj.state.adsList) byId[a.ad_id || a.id] = a;
    ads = Object.values(byId);
  }
  const hit = ads.find(a => (a.title || a.ad_title) === title);
  return { n: ads.length, ad: hit || null, ad_id: hit ? (hit.ad_id || hit.id) : null };
};
"""


def slugify(login: str) -> str:
    return re.sub(r"[^a-z0-9]", "", login.lower())[:12]


def open_sheet():
    return gspread.authorize(
        Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    ).open_by_key(SHEET_ID)


def load_creatives(ss) -> dict[str, str]:
    cre = ss.worksheet("Креативы").get_all_values()
    h = cre[0]
    i_code = h.index("код")
    i_text = h.index("содержимое")
    out = {}
    for row in cre[1:]:
        if len(row) <= max(i_code, i_text):
            continue
        code = (row[i_code] or "").strip().lower()
        if code.startswith("t"):
            out[code] = row[i_text]
    return out


def pad(row: list, n: int) -> list:
    while len(row) < n:
        row.append("")
    return row


def upsert_slugs_and_vpn(ss, channels: list[dict]) -> dict[str, str]:
    """Return login → slug map; upsert Слаги + VPN-сервисы."""
    slug_ws = ss.worksheet("Слаги")
    slug_vals = slug_ws.get_all_values()
    sh = slug_vals[0]
    si = {c: i for i, c in enumerate(sh)}
    login_to_slug: dict[str, str] = {}
    used = set()
    login_row: dict[str, int] = {}  # 1-based sheet row
    for idx, row in enumerate(slug_vals[1:], start=2):
        row = pad(list(row), len(sh))
        login = row[si["логин"]].lstrip("@").strip().lower()
        slug = (row[si["slug"]] or "").strip().lower()
        if login:
            login_to_slug[login] = slug
            login_row[login] = idx
        if slug:
            used.add(slug)

    new_slug_rows = []
    for ch in channels:
        login = ch["login"].lower()
        if login in login_to_slug and login_to_slug[login]:
            continue
        slug = slugify(login)
        base = slug
        n = 2
        while slug in used:
            suffix = str(n)
            slug = (base[: 12 - len(suffix)] + suffix) if len(base) + len(suffix) > 12 else base + suffix
            n += 1
        used.add(slug)
        login_to_slug[login] = slug
        new_slug_rows.append([login, slug, "канал", f"pack2 {date.today().isoformat()}"])
        print("SLUG new", login, "->", slug)

    if new_slug_rows:
        slug_ws.append_rows(new_slug_rows, value_input_option="USER_ENTERED")

    # VPN-сервисы
    vpn_ws = ss.worksheet("VPN-сервисы")
    vpn_vals = vpn_ws.get_all_values()
    vh = vpn_vals[0]
    # columns: Тип, Название, Логин, Ссылка, ...
    existing_logins = set()
    for row in vpn_vals[1:]:
        if len(row) < 3:
            continue
        existing_logins.add(row[2].lstrip("@").strip().lower())
    new_vpn = []
    for ch in channels:
        login = ch["login"].lower()
        if login in existing_logins:
            continue
        new_vpn.append(
            [
                "Канал",
                ch["title"],
                login,
                f"https://t.me/{login}",
                "",
                "",
                "",
                "",
            ]
        )
        print("VPN-сервисы new", login)
    if new_vpn:
        # pad to header width
        new_vpn = [pad(r, len(vh)) for r in new_vpn]
        vpn_ws.append_rows(new_vpn, value_input_option="USER_ENTERED")

    return login_to_slug


def append_pack2_svyazki(ss, login_to_slug: dict[str, str], creatives: dict[str, str]) -> list[dict]:
    sv = ss.worksheet("Связки")
    vals = sv.get_all_values()
    h = vals[0]
    si = {c: i for i, c in enumerate(h)}
    existing = {(row[0] if row else "") for row in vals[1:]}

    items = []
    rows_to_append = []
    today = date.today().isoformat()
    for ch in PACK2_CHANNELS:
        login = ch["login"].lower()
        slug = login_to_slug[login]
        for tx in PACK2_TEXTS:
            sp = f"tga_c_x_{tx}_s_{slug}_eur"
            promote = f"https://t.me/surfvpn?start={sp}"
            item = {
                "start_param": sp,
                "login": login,
                "slug": slug,
                "tx": tx,
                "text": creatives[tx],
                "title": sp,
                "promote_url": promote,
                "cpm": 5,
                "budget": 5,
                "daily_budget": 5,
                "views_per_user": 1,
                "active": 1,
                "button": "open",
                "placement": "channel_post",
            }
            items.append(item)
            if sp in existing:
                print("Связки exists", sp)
                continue
            row = [""] * len(h)
            row[si["start_param"]] = sp
            row[si["cab"]] = "eur"
            row[si["pl"]] = "c"
            row[si["cr"]] = "x"
            row[si["tx"]] = tx
            row[si["scope"]] = "s"
            row[si["slug"]] = slug
            row[si["дата"]] = today
            row[si["статус"]] = "к заливке"
            row[si["cpm"]] = "5"
            row[si["budget"]] = "5"
            row[si["daily_budget"]] = "5"
            row[si["promote_url"]] = promote
            row[si["промокод в админке"]] = "нет"
            row[si["заметка"]] = f"pack2 {today}; @{login}"
            rows_to_append.append(row)

    if rows_to_append:
        sv.append_rows(rows_to_append, value_input_option="USER_ENTERED")
        print("Связки appended", len(rows_to_append))

    # write codes file
    codes = [it["start_param"] for it in items]
    PACK2_CODES.write_text("\n".join(codes) + "\n", encoding="utf-8")
    print("CODES FILE", PACK2_CODES)
    for c in codes:
        print("CODE", c)

    # mark promo добавлен (user pouring / go-ahead)
    vals2 = sv.get_all_values()
    updates = []
    for ridx, row in enumerate(vals2[1:], start=2):
        row = pad(list(row), len(h))
        if row[si["start_param"]] in codes:
            if row[si["промокод в админке"]] != "добавлен":
                updates.append({"range": f"P{ridx}", "values": [["добавлен"]]})  # may be wrong col
    # safer: find column letter by index
    from gspread.utils import rowcol_to_a1

    batch = []
    for ridx, row in enumerate(vals2[1:], start=2):
        row = pad(list(row), len(h))
        if row[si["start_param"]] not in codes:
            continue
        cell = rowcol_to_a1(ridx, si["промокод в админке"] + 1)
        batch.append({"range": cell, "values": [["добавлен"]]})
    if batch:
        sv.batch_update(batch, value_input_option="USER_ENTERED")
        print("promo marked добавлен", len(batch))

    return items


def update_svyazki_results(ss, results: list[dict], note_prefix: str = "") -> None:
    from gspread.utils import rowcol_to_a1

    sv = ss.worksheet("Связки")
    vals = sv.get_all_values()
    h = vals[0]
    si = {c: i for i, c in enumerate(h)}
    by_sp = {r["start_param"]: r for r in results if r.get("start_param")}
    batch = []
    for ridx, row in enumerate(vals[1:], start=2):
        row = pad(list(row), len(h))
        sp = row[si["start_param"]]
        if sp not in by_sp:
            continue
        r = by_sp[sp]
        status = "Active" if r.get("ok") else "fail"
        ad_id = r.get("ad_id") or ""
        ads_url = f"https://ads.telegram.org/account/ad/{ad_id}" if ad_id else ""
        note = r.get("note") or ""
        if r.get("error"):
            note = f"{note_prefix}{r.get('error')}"[:500]
        elif note_prefix and not note:
            note = note_prefix.rstrip(": ")
        mapping = {
            "ad_id": str(ad_id) if ad_id else "",
            "ads_url": ads_url,
            "статус": status,
            "cpm": str(r.get("cpm", 5) if r.get("ok") else row[si["cpm"]] or "5"),
            "budget": str(r.get("budget", 5) if r.get("ok") else row[si["budget"]] or "5"),
            "daily_budget": str(r.get("daily_budget", 5) if r.get("ok") else row[si["daily_budget"]] or "5"),
            "промокод в админке": "добавлен",
            "заметка": note or row[si["заметка"]],
        }
        for col, val in mapping.items():
            if col not in si:
                continue
            batch.append({"range": rowcol_to_a1(ridx, si[col] + 1), "values": [[val]]})
    if batch:
        # chunk
        for i in range(0, len(batch), 80):
            sv.batch_update(batch[i : i + 80], value_input_option="USER_ENTERED")
        print("Связки updated cells", len(batch))


def launch_cabinet_page(playwright):
    cookies_raw = json.loads(COOKIES.read_text(encoding="utf-8"))
    browser = playwright.chromium.launch(channel="msedge", headless=True)
    context = browser.new_context()
    pw_cookies = []
    for c in cookies_raw:
        domain = c["domain"]
        if domain.startswith("."):
            domain = domain[1:]
        pw_cookies.append(
            {
                "name": c["name"],
                "value": c["value"],
                "domain": domain,
                "path": c.get("path") or "/",
                "secure": bool(c.get("secure", True)),
                "httpOnly": False,
            }
        )
    context.add_cookies(pw_cookies)
    page = context.new_page()
    page.goto("https://ads.telegram.org/account", wait_until="domcontentloaded", timeout=90000)
    for i in range(40):
        probe = page.evaluate(
            """() => ({
              url: location.href,
              hasAj: typeof Aj !== 'undefined',
              owner: (typeof Aj !== 'undefined' && Aj.state && Aj.state.ownerId) || null
            })"""
        )
        print("probe", i, probe)
        if probe.get("owner"):
            break
        if "auth" in (probe.get("url") or ""):
            browser.close()
            raise SystemExit("NOT_LOGGED_IN")
        time.sleep(1)
    else:
        browser.close()
        raise SystemExit("NO_OWNER_ID")
    page.evaluate(f"() => {{ {SV_HELPERS} }}")
    return browser, page


def run_outline(page, creatives: dict[str, str]) -> list[dict]:
    results = []
    for tx in OUTLINE_TEXTS:
        sp = f"tga_c_x_{tx}_s_getoutlinevp_eur"
        item = {
            "start_param": sp,
            "title": sp,
            "login": OUTLINE_LOGIN,
            "text": creatives[tx],
            "promote_url": f"https://t.me/surfvpn?start={sp}",
            "cpm": 5,
            "budget": 0,
            "daily_budget": 0,
            "views_per_user": 1,
            "active": 1,
            "button": "open",
            "placement": "channel_post",
        }
        print("=== Outline create budget=0", sp)
        created = page.evaluate("(item) => window.__svCreateOne(item)", item)
        print("create", created)
        if not created.get("ok"):
            results.append(
                {
                    "ok": False,
                    "start_param": sp,
                    "error": created.get("error"),
                    "stage": created.get("stage"),
                    "field": created.get("field"),
                    "tx": tx,
                }
            )
            print("STOP Outline — create with budget=0 failed")
            # still record remaining as skipped
            remaining = OUTLINE_TEXTS[OUTLINE_TEXTS.index(tx) + 1 :]
            for tx2 in remaining:
                results.append(
                    {
                        "ok": False,
                        "start_param": f"tga_c_x_{tx2}_s_getoutlinevp_eur",
                        "error": f"skipped after fail on {sp}: {created.get('error')}",
                        "stage": "skipped",
                        "tx": tx2,
                    }
                )
            break

        ad_id = created.get("ad_id")
        if not ad_id:
            found = page.evaluate("(title) => window.__svFindAdByTitle(title)", sp)
            print("find by title", found)
            ad_id = found.get("ad_id")
        if not ad_id:
            results.append(
                {
                    "ok": False,
                    "start_param": sp,
                    "error": "created but no ad_id",
                    "stage": "ad_id",
                    "tx": tx,
                }
            )
            print("STOP Outline — no ad_id")
            break

        top = page.evaluate("(args) => window.__svTopUp(args.ad_id, args.amount, args.daily)", {"ad_id": ad_id, "amount": 5, "daily": 5})
        print("topup", top)
        if not top.get("ok"):
            results.append(
                {
                    "ok": False,
                    "start_param": sp,
                    "ad_id": ad_id,
                    "error": top.get("error"),
                    "stage": top.get("stage") or "topup",
                    "tx": tx,
                    "budget": 0,
                    "daily_budget": 0,
                    "cpm": 5,
                    "note": f"created budget=0 ad_id={ad_id}; topup fail: {top.get('error')}",
                }
            )
            # user said: if create with budget=0 also fails, stop. Top-up fail after success create — continue? Instruction: "If create with budget=0 also fails, record error and stop Outline." So topup fail doesn't necessarily stop all — but practically we should stop if topup is also blocked for this target.
            print("STOP Outline — topup failed (same replenishment block likely)")
            remaining = OUTLINE_TEXTS[OUTLINE_TEXTS.index(tx) + 1 :]
            for tx2 in remaining:
                results.append(
                    {
                        "ok": False,
                        "start_param": f"tga_c_x_{tx2}_s_getoutlinevp_eur",
                        "error": f"skipped after topup fail on {sp}: {top.get('error')}",
                        "stage": "skipped",
                        "tx": tx2,
                    }
                )
            break

        results.append(
            {
                "ok": True,
                "start_param": sp,
                "ad_id": ad_id,
                "status": "Active",
                "cpm": 5,
                "budget": 5,
                "daily_budget": 5,
                "tx": tx,
                "note": "outline budget0+topup ok",
            }
        )
        time.sleep(0.5)
    return results


def run_pack2(page, items: list[dict]) -> list[dict]:
    results = []
    for item in items:
        print("=== pack2 create", item["start_param"], "@" + item["login"])
        created = page.evaluate("(item) => window.__svCreateOne(item)", item)
        print("create", created)
        if not created.get("ok"):
            results.append(
                {
                    "ok": False,
                    "start_param": item["start_param"],
                    "login": item["login"],
                    "error": created.get("error"),
                    "stage": created.get("stage"),
                    "field": created.get("field"),
                }
            )
            time.sleep(0.45)
            continue
        ad_id = created.get("ad_id")
        if not ad_id:
            found = page.evaluate("(title) => window.__svFindAdByTitle(title)", item["start_param"])
            ad_id = found.get("ad_id")
        results.append(
            {
                "ok": True,
                "start_param": item["start_param"],
                "login": item["login"],
                "ad_id": ad_id,
                "status": "Active",
                "cpm": 5,
                "budget": 5,
                "daily_budget": 5,
                "note": "pack2 create ok",
            }
        )
        time.sleep(0.45)
    return results


def main() -> None:
    ss = open_sheet()
    creatives = load_creatives(ss)
    for tx in set(OUTLINE_TEXTS + PACK2_TEXTS):
        if tx not in creatives or not creatives[tx]:
            raise SystemExit(f"missing creative {tx}")
        print("creative", tx, creatives[tx][:60], "...")

    # --- B prepare sheet first (codes needed before create) ---
    print("\n=== B prepare sheet ===")
    login_to_slug = upsert_slugs_and_vpn(ss, PACK2_CHANNELS)
    # ensure outline slug present
    if "getoutlinevpn_channel" not in login_to_slug:
        login_to_slug.update(upsert_slugs_and_vpn(ss, [{"login": OUTLINE_LOGIN, "title": "Outline VPN"}]))
    pack2_items = append_pack2_svyazki(ss, login_to_slug, creatives)

    with sync_playwright() as p:
        browser, page = launch_cabinet_page(p)

        print("\n=== A Outline budget=0 retry ===")
        outline_results = run_outline(page, creatives)
        OUTLINE_RESULTS.write_text(
            json.dumps({"results": outline_results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        update_svyazki_results(ss, outline_results, note_prefix="outline-budget0: ")

        print("\n=== B pack2 create ===")
        pack2_results = run_pack2(page, pack2_items)
        # reload listing for missing ad_ids
        for r in pack2_results:
            if r.get("ok") and not r.get("ad_id"):
                found = page.evaluate("(title) => window.__svFindAdByTitle(title)", r["start_param"])
                r["ad_id"] = found.get("ad_id")

        out = {
            "ok_count": sum(1 for r in pack2_results if r.get("ok")),
            "fail_count": sum(1 for r in pack2_results if not r.get("ok")),
            "results": pack2_results,
            "codes_file": str(PACK2_CODES),
            "outline_summary": {
                "ok": sum(1 for r in outline_results if r.get("ok")),
                "fail": sum(1 for r in outline_results if not r.get("ok")),
            },
        }
        PACK2_RESULTS.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        update_svyazki_results(ss, pack2_results, note_prefix="pack2: ")

        browser.close()

    print("\n=== SUMMARY Outline ===")
    for r in outline_results:
        print(("OK" if r.get("ok") else "FAIL"), r.get("start_param"), r.get("ad_id"), r.get("error") or r.get("note"))
    print("\n=== SUMMARY pack2 ===")
    for r in pack2_results:
        print(("OK" if r.get("ok") else "FAIL"), r.get("start_param"), r.get("ad_id"), r.get("error") or "")
    print("codes", PACK2_CODES)
    print("outline json", OUTLINE_RESULTS)
    print("pack2 json", PACK2_RESULTS)


if __name__ == "__main__":
    main()
