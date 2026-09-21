# -*- coding: utf-8 -*-
"""Normalize tgadsspy VPN ads JSON into competitor creatives CSV + digest."""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "tgads-snapshots"
OUT_CSV = ROOT / "tgads-competitor-creatives.csv"
OUT_DIGEST = ROOT / "tgads-competitor-digest.md"

OWN = re.compile(r"surf|blanc|fck.?rkn", re.I)


def cabinet(payment: str) -> str:
    p = (payment or "").upper()
    if "TON" in p:
        return "ton"
    if "EUR" in p or "EURO" in p:
        return "eur"
    return payment or ""


def start_param(url: str) -> str:
    if not url:
        return ""
    try:
        q = parse_qs(urlparse(url).query)
        vals = q.get("start") or q.get("startapp") or []
        return vals[0] if vals else ""
    except Exception:
        return ""


def angle(text: str) -> str:
    t = (text or "").lower()
    tags = []
    if re.search(r"бел(ый|ые|ых)\s*спис|white.?list|бс\b", t):
        tags.append("white_lists")
    if re.search(r"youtube|ютуб", t):
        tags.append("youtube")
    if re.search(r"триал|бесплатн|free|дн(я|ей|ь) знаком|тест|пробн", t):
        tags.append("trial_free")
    if re.search(r"скорост|быстр|gigabit|гигабит", t):
        tags.append("speed")
    if re.search(r"министер|одобрен|гос|рф\b|легальн", t):
        tags.append("gov_legal")
    if re.search(r"розыгрыш|giveaway|выигра|iphone|айфон", t):
        tags.append("giveaway")
    if re.search(r"ai|gpt|gemini|нейро", t):
        tags.append("ai")
    if re.search(r"обход|блокир|рпн|рпкн|роскомнадзор", t):
        tags.append("bypass_blocks")
    return "|".join(tags) if tags else "other"


def load_ads() -> list[dict]:
    paths = sorted(SNAP.glob("*_tgadsspy_ads_vpn_ru_*.json"), reverse=True)
    by_id: dict[str, dict] = {}
    for path in paths:
        if "merged" in path.name or "advertiser" in path.name:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("data") if isinstance(payload, dict) else payload
        window = "7d" if "_7d" in path.name else ("30d" if "_30d" in path.name else "")
        for row in rows or []:
            rid = row.get("id") or f"{row.get('text','')}|{row.get('ctaUrl','')}"
            prev = by_id.get(rid)
            if not prev:
                row = dict(row)
                row["_windows"] = {window} if window else set()
                row["_sources"] = {"tgadsspy"}
                by_id[rid] = row
            else:
                prev["_windows"].add(window)
                # keep later lastSeen
                if (row.get("lastSeenAt") or "") > (prev.get("lastSeenAt") or ""):
                    for k, v in row.items():
                        if k.startswith("_"):
                            continue
                        prev[k] = v
    return list(by_id.values())


def main() -> None:
    ads = load_ads()
    snap_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fields = [
        "snapshot_at",
        "source",
        "windows",
        "advertiser",
        "destination",
        "title",
        "text",
        "cta",
        "cta_url",
        "start_param",
        "cabinet",
        "payment_source",
        "geo",
        "lang",
        "first_seen",
        "last_seen",
        "media_type",
        "angle",
        "impressions",
        "placements",
        "bot_mau",
        "ad_id",
    ]
    rows = []
    for ad in ads:
        adv = (ad.get("advertiser") or {})
        advertiser = (adv.get("name") or ad.get("advertiserName") or "").lstrip("@")
        dest = (ad.get("ctaTargetUsername") or advertiser or "").lstrip("@")
        text = ad.get("text") or ""
        title = ad.get("title") or ad.get("targetTitle") or ""
        if OWN.search(f"{advertiser} {dest} {title}"):
            continue
        cta_url = ad.get("ctaUrl") or ""
        rows.append(
            {
                "snapshot_at": snap_at,
                "source": "tgadsspy",
                "windows": ",".join(sorted(ad.get("_windows") or [])),
                "advertiser": advertiser,
                "destination": dest,
                "title": title,
                "text": text.replace("\n", " ").strip(),
                "cta": ad.get("ctaButtonText") or "",
                "cta_url": cta_url,
                "start_param": start_param(cta_url),
                "cabinet": cabinet(ad.get("paymentSource") or ""),
                "payment_source": ad.get("paymentSource") or "",
                "geo": ad.get("geo") or "",
                "lang": ad.get("lang") or "",
                "first_seen": (ad.get("firstSeenAt") or "")[:19],
                "last_seen": (ad.get("lastSeenAt") or "")[:19],
                "media_type": ad.get("mediaType") or "",
                "angle": angle(f"{title} {text}"),
                "impressions": ad.get("impressionCount") or "",
                "placements": ad.get("placementCount") or "",
                "bot_mau": ad.get("targetBotActiveUsers") or "",
                "ad_id": ad.get("id") or "",
            }
        )

    # dedupe by text+cta+dest
    seen = set()
    deduped = []
    for r in rows:
        key = (r["destination"].lower(), r["text"], r["cta"], r["cta_url"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    deduped.sort(key=lambda r: (r["last_seen"], r["advertiser"]), reverse=True)

    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(deduped)

    # digest
    by_adv = Counter(r["advertiser"] or r["destination"] for r in deduped)
    by_angle = Counter()
    for r in deduped:
        for a in (r["angle"] or "other").split("|"):
            by_angle[a] += 1
    by_cab = Counter(r["cabinet"] or "?" for r in deduped)
    by_cta = Counter((r["cta"] or "").strip() for r in deduped if r["cta"])
    start_prefixes = Counter()
    for r in deduped:
        sp = r["start_param"]
        if not sp:
            continue
        pref = sp.split("_")[0] if "_" in sp else sp[:12]
        start_prefixes[pref] += 1

    # sample texts per top advertiser
    samples = defaultdict(list)
    for r in deduped:
        key = r["advertiser"] or r["destination"]
        if len(samples[key]) < 2:
            samples[key].append(r["text"][:180])

    lines = [
        f"# VPN TG Ads competitors — {snap_at}",
        "",
        f"Источник: tgadsspy `/ads?niche=vpn&geo=RU` (7d полный съём + 30d срез). Уникальных креативов после дедупа: **{len(deduped)}**.",
        "",
        "## Кабинеты",
        "",
    ]
    for k, v in by_cab.most_common():
        lines.append(f"- `{k}`: {v}")
    lines += ["", "## Углы офферов", ""]
    for k, v in by_angle.most_common():
        lines.append(f"- `{k}`: {v}")
    lines += ["", "## Топ рекламодателей (уник. креативы)", ""]
    for name, n in by_adv.most_common(25):
        lines.append(f"- **@{name}** — {n}")
        for s in samples.get(name, [])[:1]:
            lines.append(f"  - _{s}_")
    lines += ["", "## Частые CTA", ""]
    for k, v in by_cta.most_common(15):
        lines.append(f"- «{k}» — {v}")
    lines += ["", "## Префиксы `?start`", ""]
    for k, v in start_prefixes.most_common(15):
        lines.append(f"- `{k}_…` — {v}")
    lines += ["", f"CSV: `{OUT_CSV.name}`"]
    OUT_DIGEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"rows={len(deduped)} -> {OUT_CSV}", flush=True)
    print(f"digest -> {OUT_DIGEST}", flush=True)
    print("TOP_ADV", by_adv.most_common(12), flush=True)
    print("ANGLES", by_angle.most_common(), flush=True)


if __name__ == "__main__":
    main()
