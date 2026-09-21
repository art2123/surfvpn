# -*- coding: utf-8 -*-
"""Create €250 large pack ads in TG Ads cabinet + sync Связки.

Requires Marketing Panel paste first (промокод в админке=добавлен), or --assume-pasted.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
SECRETS = ROOT.parent / "secrets"
COOKIES = SECRETS / "_cursor_tgads_cookies.json"
CODES = ROOT / "tgads-large50-pack-codes.txt"
RESULTS = SECRETS / "large50_create_results.json"

CREDS = r"C:\Users\Admin\Documents\Antigravity\kapital\backend\credentials.json"
SHEET_ID = "1wvTt9-o6-ojwUA7CxuEYagKlzOey7WJNlvs5OKrUdVI"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
NOTE_MARK = "pack €250 large"

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
window.__svResolveBot = async function(login) {
  const key = 'bots:' + login.toLowerCase();
  if (window.__svTargetCache[key]) return window.__svTargetCache[key];
  const r = await window.__svApi('searchBot', { query: 'https://t.me/' + login, field: 'bots' });
  if (r.error || !r.bot || !r.bot.val) {
    window.__svTargetCache[key] = { error: (r && r.error) || 'no bot' };
    return window.__svTargetCache[key];
  }
  window.__svTargetCache[key] = { val: r.bot.val, username: r.bot.username };
  return window.__svTargetCache[key];
};
window.__svCreateOne = async function(item) {
  const owner_id = Aj.state.ownerId;
  const isBot = item.pl === 'b';
  const t = isBot
    ? await window.__svResolveBot(item.login)
    : await window.__svResolveChannel(item.login);
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
    target_type: isBot ? 'bots' : 'channels',
    placement: item.placement || (isBot ? 'bot' : 'channel_post'),
    device: item.device || '',
  };
  if (isBot) params.bots = t.val;
  else params.channels = t.val;
  const r = await window.__svApi('createAd', params);
  if (r.error) return { ok:false, start_param:item.start_param, error:r.error, field:r.field, stage:'create', raw:r };
  const ad_id = (r.ad && (r.ad.ad_id || r.ad.id)) || r.ad_id || null;
  return { ok:true, start_param:item.start_param, ad_id, redirect: r.redirect_to||null };
};
window.__svFindAdByTitle = async function(title) {
  const ads = (Aj.state && Aj.state.adsList) || [];
  const hit = ads.find(a => (a.title || a.ad_title) === title);
  return { n: ads.length, ad: hit || null, ad_id: hit ? (hit.ad_id || hit.id) : null };
};
window.__svReloadAds = async function() {
  const owner_id = Aj.state.ownerId;
  const r = await window.__svApi('getAdsList', { owner_id, offset_id: 0 });
  return { error: r.error || null, n: ((r.ads || r.ad_list || Aj.state.adsList || []).length) };
};
"""

LOGIN_BY_SLUG = {
    "shukavpn": "shukavpn",
    "quattrovpnne": "quattrovpn_news",
    "sotavpn": "sotavpn",
    "amneziavpnne": "amnezia_vpn_news_ru",
    "sota": "sota",
    "velvetvpnbot": "velvet_vpn_bot",
    "atlantavpnbo": "atlantavpn_bot",
    "barryvpn": "barryvpn",
}


def open_sheet():
    return gspread.authorize(
        Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    ).open_by_key(SHEET_ID)


def load_creatives(ss) -> dict[str, str]:
    cre = ss.worksheet("Креативы").get_all_values()
    h = cre[0]
    i_code, i_text = h.index("код"), h.index("содержимое")
    out = {}
    for row in cre[1:]:
        if len(row) <= max(i_code, i_text):
            continue
        code = (row[i_code] or "").strip().lower()
        if code.startswith("t"):
            out[code] = row[i_text]
    return out


def load_pack_items(ss, creatives: dict[str, str], assume_pasted: bool) -> list[dict]:
    codes = {
        x.strip()
        for x in CODES.read_text(encoding="utf-8").splitlines()
        if x.strip()
    }
    sv = ss.worksheet("Связки")
    vals = sv.get_all_values()
    h = vals[0]
    si = {c: i for i, c in enumerate(h)}
    items = []
    for row in vals[1:]:
        while len(row) < len(h):
            row.append("")
        sp = (row[si["start_param"]] or "").strip()
        if sp not in codes:
            continue
        status = (row[si["статус"]] or "").strip()
        promo = (row[si["промокод в админке"]] or "").strip().lower()
        ad_id = (row[si["ad_id"]] or "").strip()
        if ad_id:
            print("SKIP already has ad_id", sp, ad_id)
            continue
        if status not in ("к заливке", "On Hold", ""):
            print("SKIP status", sp, status)
            continue
        if not assume_pasted and promo not in ("добавлен", "да", "yes", "1"):
            raise SystemExit(
                f"Admin gate: {sp} has промокод={promo!r}. "
                "Paste codes into Marketing Panel, then re-run with --assume-pasted "
                "or set промокод в админке=добавлен."
            )
        pl = (row[si["pl"]] or "").strip()
        tx = (row[si["tx"]] or "").strip().lower()
        slug = (row[si["slug"]] or "").strip().lower()
        login = LOGIN_BY_SLUG.get(slug)
        if not login:
            raise SystemExit(f"no login for slug {slug}")
        if tx not in creatives or not creatives[tx]:
            raise SystemExit(f"missing creative {tx}")
        cpm = float(str(row[si["cpm"]] or ("2" if pl == "b" else "1.5")).replace(",", "."))
        budget = float(str(row[si["budget"]] or "5").replace(",", "."))
        daily = float(str(row[si["daily_budget"]] or "5").replace(",", "."))
        promote = (row[si["promote_url"]] or "").strip() or (
            f"https://t.me/getSurfVpnBot?start={sp}"
        )
        items.append(
            {
                "start_param": sp,
                "title": sp,
                "pl": pl,
                "tx": tx,
                "slug": slug,
                "login": login,
                "text": creatives[tx],
                "promote_url": promote,
                "cpm": cpm,
                "budget": budget,
                "daily_budget": daily,
                "views_per_user": 1,
                "active": 1,
                "button": "open",
            }
        )
    return items


def mark_promo_added(ss, codes: set[str]) -> None:
    sv = ss.worksheet("Связки")
    vals = sv.get_all_values()
    h = vals[0]
    si = {c: i for i, c in enumerate(h)}
    batch = []
    for ridx, row in enumerate(vals[1:], start=2):
        while len(row) < len(h):
            row.append("")
        if row[si["start_param"]] not in codes:
            continue
        batch.append(
            {"range": rowcol_to_a1(ridx, si["промокод в админке"] + 1), "values": [["добавлен"]]}
        )
    for i in range(0, len(batch), 80):
        sv.batch_update(batch[i : i + 80], value_input_option="USER_ENTERED")
    print("promo marked добавлен", len(batch))


def sync_results(ss, results: list[dict]) -> None:
    sv = ss.worksheet("Связки")
    vals = sv.get_all_values()
    h = vals[0]
    si = {c: i for i, c in enumerate(h)}
    by_sp = {r["start_param"]: r for r in results}
    batch = []
    for ridx, row in enumerate(vals[1:], start=2):
        while len(row) < len(h):
            row.append("")
        sp = row[si["start_param"]]
        if sp not in by_sp:
            continue
        r = by_sp[sp]
        ad_id = r.get("ad_id") or ""
        ok = bool(r.get("ok"))
        note = (row[si["заметка"]] or "")
        if r.get("error"):
            note = f"{NOTE_MARK}; FAIL: {r.get('error')}"[:500]
        elif ok:
            note = f"{NOTE_MARK}; created Active"
        mapping = {
            "ad_id": str(ad_id) if ad_id else "",
            "ads_url": f"https://ads.telegram.org/account/ad/{ad_id}" if ad_id else "",
            "статус": "Active" if ok else "к заливке",
            "cpm": str(r.get("cpm", row[si["cpm"]])),
            "budget": str(r.get("budget", row[si["budget"]])),
            "daily_budget": str(r.get("daily_budget", row[si["daily_budget"]])),
            "промокод в админке": "добавлен",
            "заметка": note,
        }
        for col, val in mapping.items():
            if col not in si:
                continue
            batch.append({"range": rowcol_to_a1(ridx, si[col] + 1), "values": [[val]]})
    for i in range(0, len(batch), 80):
        sv.batch_update(batch[i : i + 80], value_input_option="USER_ENTERED")
    print("Связки sync cells", len(batch))


def launch_cabinet(playwright):
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
              owner: (typeof Aj !== 'undefined' && Aj.state && Aj.state.ownerId) || null,
              balance: (typeof Aj !== 'undefined' && Aj.state && Aj.state.budget) || null
            })"""
        )
        print("probe", i, probe)
        if probe.get("owner"):
            break
        if "auth" in (probe.get("url") or ""):
            browser.close()
            raise SystemExit("NOT_LOGGED_IN — refresh cookies")
        time.sleep(1)
    else:
        browser.close()
        raise SystemExit("NO_OWNER_ID")
    page.evaluate(f"() => {{ {SV_HELPERS} }}")
    return browser, page


def create_all(page, items: list[dict]) -> list[dict]:
    results = []
    for item in items:
        print("=== create", item["start_param"], "@" + item["login"], "pl=" + item["pl"])
        created = page.evaluate("(item) => window.__svCreateOne(item)", item)
        print("create", created)
        if not created.get("ok"):
            results.append(
                {
                    "ok": False,
                    "start_param": item["start_param"],
                    "error": created.get("error"),
                    "stage": created.get("stage"),
                    "field": created.get("field"),
                    "cpm": item["cpm"],
                    "budget": item["budget"],
                    "daily_budget": item["daily_budget"],
                }
            )
            time.sleep(0.4)
            continue
        ad_id = created.get("ad_id")
        if not ad_id:
            found = page.evaluate(
                "(title) => window.__svFindAdByTitle(title)", item["start_param"]
            )
            ad_id = found.get("ad_id")
        results.append(
            {
                "ok": True,
                "start_param": item["start_param"],
                "ad_id": ad_id,
                "cpm": item["cpm"],
                "budget": item["budget"],
                "daily_budget": item["daily_budget"],
            }
        )
        time.sleep(0.4)
    # reload + fill missing ad_ids
    page.evaluate("() => window.__svReloadAds()")
    time.sleep(1)
    page.goto("https://ads.telegram.org/account", wait_until="domcontentloaded", timeout=90000)
    time.sleep(2)
    page.evaluate(f"() => {{ {SV_HELPERS} }}")
    for r in results:
        if r.get("ok") and not r.get("ad_id"):
            found = page.evaluate(
                "(title) => window.__svFindAdByTitle(title)", r["start_param"]
            )
            r["ad_id"] = found.get("ad_id")
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--assume-pasted",
        action="store_true",
        help="Mark промокод=добавлен and Create Ad (only after Marketing Panel paste)",
    )
    args = ap.parse_args()

    codes = {
        x.strip()
        for x in CODES.read_text(encoding="utf-8").splitlines()
        if x.strip()
    }
    if len(codes) != 50:
        print("WARN codes count", len(codes))

    ss = open_sheet()
    creatives = load_creatives(ss)
    items = load_pack_items(ss, creatives, assume_pasted=args.assume_pasted)
    print("items to create", len(items))
    if not items:
        raise SystemExit("nothing to create")

    if args.assume_pasted:
        mark_promo_added(ss, {it["start_param"] for it in items})

    with sync_playwright() as p:
        browser, page = launch_cabinet(p)
        results = create_all(page, items)
        browser.close()

    out = {
        "ok": sum(1 for r in results if r.get("ok")),
        "fail": sum(1 for r in results if not r.get("ok")),
        "results": results,
    }
    RESULTS.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    sync_results(ss, results)
    print("SUMMARY ok", out["ok"], "fail", out["fail"])
    for r in results:
        print(
            ("OK" if r.get("ok") else "FAIL"),
            r.get("start_param"),
            r.get("ad_id"),
            r.get("error") or "",
        )
    print("wrote", RESULTS)


if __name__ == "__main__":
    main()
