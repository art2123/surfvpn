# -*- coding: utf-8 -*-
"""Fill unknown bot MAU from tgadsspy /bots with long backoff; rewrite destinations + digest."""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
KEY = (ROOT / "secrets" / "tgadsspy.key").read_text(encoding="utf-8").strip()
UA = "SurfVPN-research/1.0"
CACHE_PATH = ROOT / "tgads-snapshots" / "_tgadsspy_vpn_bots_mau.json"


def api(path: str, params: dict) -> dict:
    q = urllib.parse.urlencode(params)
    url = f"https://tgadsspy.com/api/v1/{path}?{q}"
    req = urllib.request.Request(
        url,
        headers={"X-Api-Key": KEY, "User-Agent": UA, "Accept": "application/json"},
    )
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = min(90, 15 * (attempt + 1))
                print(f"  429 wait {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("rate limited")


def load_cache() -> dict[str, int]:
    if CACHE_PATH.exists():
        return {
            k.lower(): int(v)
            for k, v in json.loads(CACHE_PATH.read_text(encoding="utf-8")).items()
        }
    return {}


def build_cache() -> dict[str, int]:
    cache = load_cache()
    if len(cache) >= 200:
        print(f"using existing cache {len(cache)}", flush=True)
        return cache
    offset = 0
    while offset < 1200:
        print(f"bots niche=vpn offset={offset}", flush=True)
        try:
            j = api("bots", {"niche": "vpn", "limit": 50, "offset": offset})
        except Exception as exc:
            print("stop cache build:", exc, flush=True)
            break
        batch = j.get("data") or []
        if not batch:
            break
        for row in batch:
            u = (row.get("username") or "").lower()
            mau = row.get("botActiveUsers")
            if u and mau is not None:
                cache[u] = int(mau)
        offset += len(batch)
        print(f"  cache={len(cache)}", flush=True)
        if len(batch) < 50:
            break
        time.sleep(1.5)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote cache", len(cache), flush=True)
    return cache


def apply_gate(row: dict) -> None:
    kind = row.get("kind") or "bot"
    try:
        mau = int(float(row["mau"])) if str(row.get("mau") or "").strip() else None
    except ValueError:
        mau = None
    try:
        subs = (
            int(float(row["subscribers"]))
            if str(row.get("subscribers") or "").strip()
            else None
        )
    except ValueError:
        subs = None
    if kind == "bot":
        row["audience_metric"] = "mau"
        row["audience"] = mau if mau is not None else ""
        if mau is None:
            row["gate"] = "unknown"
        elif mau >= 10_000:
            row["gate"] = "pass_10k"
        elif mau >= 5_000:
            row["gate"] = "pass_5k"
        else:
            row["gate"] = "fail"
    else:
        row["audience_metric"] = "subscribers"
        row["audience"] = subs if subs is not None else ""
        if subs is None:
            row["gate"] = "unknown"
        elif subs >= 10_000:
            row["gate"] = "pass_10k"
        else:
            row["gate"] = "fail"


def main() -> None:
    cache = build_cache()
    path = ROOT / "tgmaps-vpn-destinations.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    unknown = [r for r in rows if r.get("gate") == "unknown"]
    print(f"unknown={len(unknown)}", flush=True)

    filled = 0
    still = []
    for row in unknown:
        login = row["destination"].lower()
        if login in cache:
            row["mau"] = str(cache[login])
            row["mau_source"] = "tgadsspy_bots"
            row["spy_mau"] = str(cache[login])
            apply_gate(row)
            filled += 1
        else:
            still.append(row)

    print(f"filled from cache={filled}; still={len(still)}", flush=True)

    # per-bot lookup for remainder (slow, polite)
    for i, row in enumerate(still, 1):
        login = row["destination"]
        try:
            j = api("bots", {"q": login, "limit": 10})
        except Exception as exc:
            print(f"  give up lookups: {exc}", flush=True)
            break
        mau = None
        for item in j.get("data") or []:
            if (item.get("username") or "").lower() == login.lower():
                mau = item.get("botActiveUsers")
                break
        if mau is None and (j.get("data") or []):
            # sometimes exact match missing; skip
            pass
        if mau is not None:
            row["mau"] = str(int(mau))
            row["mau_source"] = "tgadsspy_bots_q"
            row["spy_mau"] = str(int(mau))
            apply_gate(row)
            cache[login.lower()] = int(mau)
            filled += 1
        if i % 10 == 0:
            print(f"  lookup {i}/{len(still)} filled_total={filled}", flush=True)
        time.sleep(1.6)

    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    gates = Counter(r.get("gate") for r in rows)
    print("gates", dict(gates), flush=True)

    # rewrite digest
    from enrich_tgmaps_destinations import phrase_stats

    creatives = list(
        csv.DictReader((ROOT / "tgmaps-vpn-creatives.csv").open(encoding="utf-8"))
    )
    texts = {(r.get("text") or "").strip() for r in creatives if (r.get("text") or "").strip()}
    soft = {" ".join(t.lower().split()) for t in texts}
    phrases = phrase_stats(list(texts))
    kind_c = Counter(r.get("kind") for r in rows)

    def aud(r):
        try:
            return int(float(r.get("audience") or 0))
        except ValueError:
            return 0

    lines = [
        "# TgMaps VPN — тексты и аудитория посадочных",
        "",
        f"Креативов: **{len(creatives)}**. Destination: **{len(rows)}**.",
        f"Уникальных текстов (exact): **{len(texts)}**.",
        f"Уникальных текстов (lower+ws): **{len(soft)}**.",
        "",
        "## Посадочные: gate (боты MAU, каналы subscribers)",
        "",
        f"- kind: {dict(kind_c)}",
        f"- gate: {dict(gates)}",
        "",
        "Критерии: бот `pass_10k` при MAU≥10k, `pass_5k` при ≥5k; канал `pass_10k` при subs≥10k.",
        "MAU: t.me → tgadsspy `/bots` (niche=vpn + точечный q).",
        "",
        "### pass_10k",
        "",
    ]
    for row in sorted(rows, key=lambda r: (-aud(r), r["destination"])):
        if row.get("gate") != "pass_10k":
            continue
        lines.append(
            f"- **@{row['destination']}** ({row.get('kind')}) "
            f"{row.get('audience_metric')}={row.get('audience')} — _{row.get('name') or ''}_"
        )
    lines += ["", "### pass_5k (боты 5–10k)", ""]
    for row in sorted(rows, key=lambda r: (-aud(r), r["destination"])):
        if row.get("gate") != "pass_5k":
            continue
        lines.append(
            f"- **@{row['destination']}** MAU={row.get('audience')} — _{row.get('name') or ''}_"
        )
    fails = [r for r in rows if r.get("gate") == "fail"]
    lines += ["", "### fail (<порога)", "", f"Всего fail: **{len(fails)}**"]
    for row in sorted(fails, key=lambda r: (-aud(r), r["destination"]))[:60]:
        lines.append(
            f"- @{row['destination']} ({row.get('kind')}) "
            f"{row.get('audience_metric')}={row.get('audience')}"
        )
    unk = [r for r in rows if r.get("gate") == "unknown"]
    lines += ["", "### unknown (нет цифры)", "", f"Всего unknown: **{len(unk)}**"]
    for row in sorted(unk, key=lambda r: r["destination"])[:80]:
        lines.append(f"- @{row['destination']} ({row.get('kind')})")
    lines += ["", "## Черновой разрез текстов (до полного структурирования)", ""]
    lines.append(f"База: {len(texts)} уник. текстов.")
    for label, c, pct in phrases:
        lines.append(f"- **{label}**: {c} ({pct:.0f}%)")
    lines += [
        "",
        "## Файлы",
        "",
        "- `общее/tgmaps-vpn-destinations.csv`",
        "- `общее/tgmaps-vpn-creatives.csv`",
        "- `общее/tgmaps-vpn-placements.csv`",
        "- `общее/tgmaps-vpn-digest.md`",
        "",
    ]
    out = ROOT / "tgmaps-vpn-texts-and-audience.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", out, flush=True)


if __name__ == "__main__":
    main()
