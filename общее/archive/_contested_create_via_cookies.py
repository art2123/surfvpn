# -*- coding: utf-8 -*-
"""Create remaining contested TG Ads using Cursor-browser cookies + Playwright."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
SECRETS = ROOT.parent / "secrets"
CHUNKS = SECRETS / "contested_chunks"
COOKIES = SECRETS / "_cursor_tgads_cookies.json"
PAYLOADS = SECRETS / "contested_vpn_create_payloads.json"
RESULTS = SECRETS / "contested_create_results.json"

SV_CREATE = r"""
window.__svTargetCache = window.__svTargetCache || {};
window.__svCreate = async function(items) {
  const owner_id = Aj.state.ownerId;
  const targetCache = window.__svTargetCache;
  const results = [];
  const api = (method, data) => new Promise(res => Aj.apiRequest(method, data, res));
  async function resolveTarget(item) {
    const key = item.target_type + ':' + item.login.toLowerCase();
    if (targetCache[key]) return targetCache[key];
    const r = await api('searchChannel', { owner_id, query: 'https://t.me/' + item.login, field: 'channels' });
    if (r.error || !r.channel) { targetCache[key] = { error: (r && r.error) || 'no channel' }; return targetCache[key]; }
    targetCache[key] = { val: r.channel.val };
    return targetCache[key];
  }
  for (const item of items) {
    try {
      const t = await resolveTarget(item);
      if (t.error) { results.push({ ok:false, start_param:item.start_param, error:t.error, stage:'target' }); continue; }
      const params = {
        owner_id, title: item.title || item.start_param, text: item.text, button: item.button || 'open',
        promote_url: item.promote_url, website_name:'', website_photo:'', media:'', ad_info:'',
        cpm: item.cpm, views_per_user: item.views_per_user || 1, budget: item.budget, daily_budget: item.daily_budget,
        active: item.active != null ? item.active : 1, target_type: 'channels', placement: item.placement || 'channel_post',
        device: item.device || '', channels: t.val
      };
      const r = await api('createAd', params);
      if (r.error) results.push({ ok:false, start_param:item.start_param, error:r.error, field:r.field, stage:'create' });
      else results.push({ ok:true, start_param:item.start_param, ad_id: (r.ad&& (r.ad.ad_id||r.ad.id)) || r.ad_id, status: 'Active', redirect: r.redirect_to||null });
      await new Promise(r => setTimeout(r, 450));
    } catch(e) { results.push({ ok:false, start_param:item.start_param, error:String(e), stage:'exception' }); }
  }
  return results;
};
"""

LIST_ADS = r"""
async () => {
  const owner_id = Aj.state.ownerId;
  const api = (method, data) => new Promise(res => Aj.apiRequest(method, data, res));
  let ads = [];
  let offset_id = 0;
  for (let i = 0; i < 30; i++) {
    const r = await api('getAdsList', { owner_id, offset_id });
    if (r.error) return { error: r.error, ads };
    const batch = r.ads || (r.ad_list) || [];
    if (!batch.length) break;
    ads = ads.concat(batch);
    const last = batch[batch.length - 1];
    offset_id = last.ad_id || last.id || offset_id;
    if (batch.length < 20) break;
  }
  // also merge Aj.state.adsList if present
  if (Aj.state && Aj.state.adsList && Aj.state.adsList.length) {
    const byId = {};
    for (const a of ads) byId[a.ad_id || a.id] = a;
    for (const a of Aj.state.adsList) byId[a.ad_id || a.id] = a;
    ads = Object.values(byId);
  }
  return { owner_id, n: ads.length, ads };
}
"""


def main() -> None:
    cookies_raw = json.loads(COOKIES.read_text(encoding="utf-8"))
    payloads = json.loads(PAYLOADS.read_text(encoding="utf-8"))
    wanted = {p["start_param"] for p in payloads}
    print("wanted", len(wanted))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context()
        # Playwright cookies need url or domain without leading dot issues
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
        # wait for Aj.state.ownerId
        for i in range(40):
            probe = page.evaluate(
                """() => ({
                  url: location.href,
                  hasAj: typeof Aj !== 'undefined',
                  owner: (typeof Aj !== 'undefined' && Aj.state && Aj.state.ownerId) || null,
                  nAds: (typeof Aj !== 'undefined' && Aj.state && Aj.state.adsList && Aj.state.adsList.length) || 0
                })"""
            )
            print("probe", i, probe)
            if probe.get("owner"):
                break
            if "auth" in (probe.get("url") or ""):
                raise SystemExit("NOT_LOGGED_IN: redirected to auth")
            time.sleep(1)
        else:
            raise SystemExit("NO_OWNER_ID")

        page.evaluate(f"() => {{ {SV_CREATE} }}")
        page.evaluate("() => { window.__svAllResults = []; }")
        has = page.evaluate("() => typeof window.__svCreate")
        print("__svCreate", has)

        all_chunk_meta = []
        for i in range(7):
            path = CHUNKS / f"inj_{i:02d}.js"
            expr = path.read_text(encoding="utf-8").strip()
            print(f"=== running {path.name} ===")
            # inj files are already async IIFEs: (() => new Promise(...))()
            result = page.evaluate(f"async () => {{ return await {expr}; }}")
            print(
                f"chunk {i}: n={result.get('n')} ok={result.get('ok')} fail={result.get('fail')} total={result.get('total')}"
            )
            all_chunk_meta.append({"chunk": i, **{k: result.get(k) for k in ("n", "ok", "fail", "total")}})
            # persist intermediate
            interim = page.evaluate("() => window.__svAllResults")
            RESULTS.write_text(
                json.dumps(
                    {"interim": True, "chunks": all_chunk_meta, "results": interim},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        create_results = page.evaluate("() => window.__svAllResults")
        print("create_results", len(create_results))

        # reload ads list
        page.goto("https://ads.telegram.org/account", wait_until="domcontentloaded", timeout=90000)
        time.sleep(2)
        for i in range(30):
            owner = page.evaluate("() => typeof Aj !== 'undefined' && Aj.state && Aj.state.ownerId")
            if owner:
                break
            time.sleep(0.5)
        listing = page.evaluate(LIST_ADS)
        print("listing n=", listing.get("n"), "error=", listing.get("error"))

        browser.close()

    # Map contested titles
    ads = listing.get("ads") or []
    by_title = {}
    for a in ads:
        title = a.get("title") or a.get("ad_title") or ""
        if title in wanted:
            by_title[title] = {
                "ad_id": a.get("ad_id") or a.get("id"),
                "status": a.get("status")
                or ("Active" if a.get("active") in (1, "1", True) else a.get("status")),
                "cpm": a.get("cpm"),
                "budget": a.get("budget"),
                "daily_budget": a.get("daily_budget"),
                "active": a.get("active"),
                "title": title,
            }

    # Normalize create results + fill from listing
    ok = [r for r in create_results if r.get("ok")]
    fail = [r for r in create_results if not r.get("ok")]
    # include already-created t05 if in listing
    already = "tga_c_x_t05_s_itopvpnru_eur"
    if already in by_title and already not in {r.get("start_param") for r in create_results}:
        create_results = [
            {
                "ok": True,
                "start_param": already,
                "ad_id": by_title[already]["ad_id"],
                "status": "Active",
                "note": "preexisting",
            }
        ] + create_results

    out = {
        "ok_count": sum(1 for r in create_results if r.get("ok")),
        "fail_count": sum(1 for r in create_results if not r.get("ok")),
        "chunks": all_chunk_meta,
        "create_results": create_results,
        "cabinet_by_title": by_title,
        "cabinet_n_matched": len(by_title),
        "fails": [
            {"start_param": r.get("start_param"), "error": r.get("error"), "stage": r.get("stage"), "field": r.get("field")}
            for r in create_results
            if not r.get("ok")
        ],
    }
    RESULTS.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", RESULTS)
    print("ok", out["ok_count"], "fail", out["fail_count"], "cabinet_matched", out["cabinet_n_matched"])
    for f in out["fails"]:
        print("FAIL", f)


if __name__ == "__main__":
    main()
