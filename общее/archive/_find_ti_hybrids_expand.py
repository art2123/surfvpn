# -*- coding: utf-8 -*-
"""Expand hybrid search: probe more media logins for tech+VPN/RKN."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "imports"
UA = "Mozilla/5.0"

# Extra media / blocks / internet-freedom candidates (not VPN brand status channels)
EXTRA = [
    "runet_blocks",
    "block_runet",
    "blokirovki",
    "blokirovki_runeta",
    "rkn_news",
    "roskomnadzor",
    "censornet",
    "digital_rights",
    "roskomsvoboda",
    "rublacklist",
    "netfreedom",
    "telegalka",
    "tginfo",
    "tginfo_ru",
    "telegramtips",
    "telegramnews",
    "habr_com",
    "habr",
    "tjournal",
    "tj_ru",
    "dtf_ru",
    "vc_ru",
    "wylsacom",
    "rozetked",
    "ixbt_com",
    "mobile_review",
    "mobile_reviewcom",
    "4pda",
    "trashbox_ru",
    "techno_novinki",
    "it_teech",
    "xor_journal",
    "ai_for_devs",
    "technoinsider",
    "blancvpn",
    "fck_rkn_bot",
    "papervpnchat",
    "shukavpn",
    "lagomvpn",
    "quattrovpn_news",
    "vpn1_news",
    "amnezia_vpn_news_ru",
    "dedvpn",
    "kolezev",
    "varlamov_news",
    "varlamov",
    "polit_doklad",
    "samfromusa",
    "ateobreaking",
    "estradavoice",
    "bbbreaking",
    "shot_shot",
    "meduzalive",
    "currenttime",
    "zona_media",
    "mediazzona",
    "holodmedia",
    "agents_media",
    "ovdinfo",
    "team29",
    "novaya_gazeta",
    "thebell_io",
    "moscowtimes_ru",
    "rbc_news",
    "forbesrussia",
    "kommersant",
    "technopark",
    "hightech_fm",
    "hightech_ru",
    "nplus1",
    "nplusone",
    "naked_science",
    "indicator_ru",
    "cnewsru",
    "3dnews",
    "ferranews",
    "androidinsider",
    "appleinsider_ru",
    "macdigger",
    "iphonesru",
    "apptractor",
    "appfollow",
    "app2top",
    "app2top_ru",
]

PAT = {
    "vpn": re.compile(r"\bvpn\b|впн", re.I),
    "rkn": re.compile(r"ркн|роскомнадзор", re.I),
    "block": re.compile(r"блокир|обход|белый список|замедл|цензур", re.I),
    "tech": re.compile(
        r"технолог|гаджет|нейросет|\bии\b|\bai\b|iphone|android|инновац|стартап|chatgpt|openai|telegram",
        re.I,
    ),
}


def fetch(login: str) -> dict | None:
    url = f"https://t.me/s/{login}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    except Exception as e:
        return {"login": login, "class": "missing", "err": str(e)}
    if "tgme_page_title" not in html and "og:title" not in html:
        return {"login": login, "class": "missing"}
    if "If you have <strong>Telegram</strong>" in html and "tgme_page_title" not in html:
        # might still be valid
        pass
    title_m = re.search(r'og:title" content="([^"]+)', html)
    desc_m = re.search(r'og:description" content="([^"]+)', html)
    extra_m = re.search(r'tgme_page_extra">([^<]+)', html)
    title = title_m.group(1) if title_m else ""
    if "Telegram: Contact @" in title or title == f"Telegram: Contact @{login}":
        return {"login": login, "class": "missing"}
    desc = desc_m.group(1) if desc_m else ""
    posts = re.findall(r'class="tgme_widget_message_text[^>]*>([\s\S]*?)</div>', html)
    texts = []
    for p in posts[:15]:
        t = re.sub(r"<[^>]+>", " ", p)
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            texts.append(t)
    if not texts and not desc:
        return {"login": login, "class": "empty", "title": title}
    blob = (" ".join(texts) + " " + desc).lower()
    flags = [k for k, rx in PAT.items() if rx.search(blob)]
    has_tech = "tech" in flags
    has_vpnish = bool({"vpn", "rkn", "block"} & set(flags))
    product = bool(
        re.search(r"@\w*vpn|конфиг|outline|vless|безлимитн|бот\s*[—:\-].*vpn", desc, re.I)
    )
    # media hybrid: tech OR general news voice + vpnish, not pure product pitch
    if has_tech and has_vpnish and not product:
        cls = "hybrid_media"
    elif has_tech and has_vpnish and product:
        cls = "hybrid_vpn_brand"
    elif has_vpnish and product:
        cls = "vpn_product"
    elif has_vpnish:
        cls = "vpnish_media"
    elif has_tech:
        cls = "tech_only"
    else:
        cls = "other"
    return {
        "login": login,
        "title": title,
        "desc": desc[:240],
        "extra": extra_m.group(1).strip() if extra_m else "",
        "flags": flags,
        "class": cls,
        "samples": texts[:2],
    }


def main() -> None:
    prev = {}
    scan_path = OUT / "ti_hybrid_scan.json"
    if scan_path.exists():
        prev = json.loads(scan_path.read_text(encoding="utf-8"))
    seen = {r["login"] for r in prev.get("all", [])}
    results = list(prev.get("all", []))
    for login in EXTRA:
        login = login.lower()
        if login in seen:
            continue
        seen.add(login)
        r = fetch(login)
        results.append(r)
        print(f"{r.get('class'):18} @{login} {r.get('title','')[:50]}")

    hybrids_media = [r for r in results if r.get("class") == "hybrid_media"]
    hybrids_brand = [r for r in results if r.get("class") == "hybrid_vpn_brand"]
    vpnish = [r for r in results if r.get("class") == "vpnish_media"]
    # remap old "hybrid" from first scan into brand vs media heuristically
    for r in results:
        if r.get("class") == "hybrid":
            desc = r.get("desc") or ""
            if re.search(r"@\w*vpn|конфиг|outline|vless", desc, re.I):
                r["class"] = "hybrid_vpn_brand"
            else:
                r["class"] = "hybrid_media"

    hybrids_media = [r for r in results if r.get("class") == "hybrid_media"]
    hybrids_brand = [r for r in results if r.get("class") == "hybrid_vpn_brand"]
    vpnish = [r for r in results if r.get("class") == "vpnish_media"]

    payload = {
        "hybrid_media": hybrids_media,
        "hybrid_vpn_brand": hybrids_brand,
        "vpnish_media": vpnish,
        "all": results,
    }
    (OUT / "ti_hybrid_expanded.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== hybrid_media (цель: как TI) ===")
    for r in hybrids_media:
        print(f"  @{r['login']}: {r.get('title')} | {r.get('flags')}")
    print("\n=== hybrid_vpn_brand ===")
    for r in hybrids_brand:
        print(f"  @{r['login']}: {r.get('title')} | {r.get('flags')}")
    print("\n=== vpnish_media (RKN/blocks без tech) ===")
    for r in vpnish:
        print(f"  @{r['login']}: {r.get('title')} | {r.get('flags')}")


if __name__ == "__main__":
    main()
