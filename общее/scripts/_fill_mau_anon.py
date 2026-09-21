# -*- coding: utf-8 -*-
"""Fill destination MAU via tgadsspy ANON /bots (no API key — key is 429'd)."""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "tgads-snapshots" / "_tgadsspy_vpn_bots_mau.json"
UA = "SurfVPN-research/1.0"


def api_anon(params: dict) -> dict:
    q = urllib.parse.urlencode(params)
    url = f"https://tgadsspy.com/api/v1/bots?{q}"
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


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
    cache: dict[str, int] = {}
    if CACHE_PATH.exists():
        cache = {
            k.lower(): int(v)
            for k, v in json.loads(CACHE_PATH.read_text(encoding="utf-8")).items()
        }
    offset = 0
    while offset < 1500:
        print(f"ANON bots offset={offset}", flush=True)
        j = api_anon({"niche": "vpn", "limit": 50, "offset": offset})
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
        time.sleep(1.1)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print("cache written", len(cache), flush=True)

    path = ROOT / "tgmaps-vpn-destinations.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    filled = 0
    for row in rows:
        if row.get("gate") != "unknown":
            continue
        if row.get("kind") == "channel":
            continue
        login = row["destination"].lower()
        if login not in cache:
            continue
        row["mau"] = str(cache[login])
        row["spy_mau"] = str(cache[login])
        row["mau_source"] = "tgadsspy_bots_anon"
        apply_gate(row)
        filled += 1
    print(f"filled {filled}", flush=True)

    # remaining unknown bots: try q= one by one via ANON
    still = [r for r in rows if r.get("gate") == "unknown" and r.get("kind") == "bot"]
    print(f"still unknown bots {len(still)}", flush=True)
    for i, row in enumerate(still, 1):
        login = row["destination"]
        try:
            j = api_anon({"q": login, "limit": 10})
        except Exception as exc:
            print("stop lookups", exc, flush=True)
            break
        mau = None
        for item in j.get("data") or []:
            if (item.get("username") or "").lower() == login.lower():
                mau = item.get("botActiveUsers")
                break
        if mau is not None:
            row["mau"] = str(int(mau))
            row["spy_mau"] = str(int(mau))
            row["mau_source"] = "tgadsspy_bots_anon_q"
            apply_gate(row)
            cache[login.lower()] = int(mau)
            filled += 1
        if i % 20 == 0:
            print(f"  lookup {i}/{len(still)} filled={filled}", flush=True)
        time.sleep(1.05)

    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print("gates", dict(Counter(r.get("gate") for r in rows)), flush=True)
    import subprocess

    subprocess.check_call(
        [sys.executable, str(ROOT / "_refresh_texts_audience_md.py")]
    )


if __name__ == "__main__":
    main()
