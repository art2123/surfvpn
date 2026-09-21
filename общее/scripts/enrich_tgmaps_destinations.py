# -*- coding: utf-8 -*-
"""Enrich TgMaps destinations with t.me / tgadsspy audience; unique-text report."""
from __future__ import annotations

import csv
import json
import re
import ssl
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "tgads-snapshots"
UA = "Mozilla/5.0 (compatible; SurfVPN-research/1.0)"
ctx = ssl.create_default_context()


def compact_num(value) -> int | None:
    if value in (None, ""):
        return None
    raw = str(value).strip().replace("\xa0", " ").replace(" ", "").replace(",", ".")
    if not raw or raw.upper() in {"N/A", "NA"}:
        return None
    mult = 1
    if raw.upper().endswith("K"):
        mult = 1_000
        raw = raw[:-1]
    elif raw.upper().endswith("M"):
        mult = 1_000_000
        raw = raw[:-1]
    try:
        return int(float(raw) * mult)
    except ValueError:
        digits = re.sub(r"\D", "", str(value))
        return int(digits) if digits else None


def is_bot(login: str) -> bool:
    login = login.lower()
    return login.endswith("bot") or login.endswith("robot")


def fetch_tg_stats(login: str) -> dict:
    kind_bot = is_bot(login)
    url = f"https://t.me/{login}"
    out = {
        "login": login,
        "kind": "bot" if kind_bot else "channel",
        "name": "",
        "mau": None,
        "subscribers": None,
        "extra": "",
        "ok": False,
        "error": "",
    }
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        out["error"] = str(exc)[:120]
        return out
    out["ok"] = True
    title = re.search(r'og:title"\s+content="([^"]+)"', html)
    if title:
        out["name"] = re.sub(r"\s+", " ", title.group(1)).strip()
    extra_m = re.search(r'class="tgme_page_extra"[^>]*>([^<]+)', html)
    if extra_m:
        out["extra"] = extra_m.group(1).strip()
    mau = re.search(r">([\d\s\.,MK]+)monthly users<", html, re.I)
    if not mau:
        mau = re.search(r"([\d\s\.,MK]+)\s*monthly users", html, re.I)
    if mau:
        out["mau"] = compact_num(mau.group(1))
    subs = re.search(r"([\d\s\.,MK]+)\s*subscribers", html, re.I)
    if not subs and out["extra"]:
        subs = re.search(r"([\d\s\.,MK]+)\s*subscribers", out["extra"], re.I)
    if subs:
        out["subscribers"] = compact_num(subs.group(1))
    # members (groups)
    members = re.search(r"([\d\s\.,MK]+)\s*members", html, re.I)
    if members and not out["subscribers"] and not kind_bot:
        out["subscribers"] = compact_num(members.group(1))
    # detect bot via page
    if "Start Bot" in html or "Send Message" in html:
        out["kind"] = "bot"
    elif out["subscribers"]:
        out["kind"] = "channel"
    return out


def load_spy_mau() -> dict[str, int]:
    """destination.lower() -> max bot_mau from tgadsspy creatives / snapshots."""
    out: dict[str, int] = {}
    csv_path = ROOT / "tgads-competitor-creatives.csv"
    if csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                dest = (row.get("destination") or "").strip().lstrip("@").lower()
                mau = compact_num(row.get("bot_mau"))
                if dest and mau:
                    out[dest] = max(out.get(dest, 0), mau)
    for path in SNAP.glob("*_tgadsspy_ads_vpn_ru_*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = payload.get("data") if isinstance(payload, dict) else payload
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            dest = (
                row.get("destinationUsername")
                or row.get("destination")
                or row.get("ctaUrl")
                or ""
            )
            dest = str(dest)
            dest = re.sub(r"^https?://t\.me/", "", dest, flags=re.I).lstrip("@")
            dest = dest.split("?")[0].split("/")[0].lower()
            mau = (
                row.get("targetBotActiveUsers")
                or row.get("botActiveUsers")
                or row.get("botMau")
                or row.get("mau")
            )
            mau_i = compact_num(mau)
            if dest and mau_i:
                out[dest] = max(out.get(dest, 0), mau_i)
    return out


def normalize_text(text: str) -> str:
    t = (text or "").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def phrase_stats(texts: list[str]) -> list[tuple[str, int, float]]:
    """Rough common-offer phrases for later creative work."""
    patterns = [
        ("N дней бесплатно / триал", r"(\d+)\s*дн[яей].{0,12}бесплат|бесплатн.{0,20}(\d+)\s*дн|триал|пробн"),
        ("от X ₽/мес", r"от\s*\d+[\s\u00a0]*[₽р]|\/\s*мес|\d+\s*₽"),
        ("обход белых списков", r"бел(ый|ые|ых)\s*спис|white.?list"),
        ("глушилки", r"глушил"),
        ("YouTube", r"youtube|ютуб"),
        ("Happ / клиенты", r"\bhapp\b|v2raytun|v2box|hiddify"),
        ("все устройства", r"устройств|iphone|android|windows|mac|тв\b|tv\b"),
        ("реферал / друг", r"друг|реферал|приглас"),
        ("без логов", r"без\s*лог|no\s*log"),
        ("скорость", r"скорост|быстр|лета"),
        ("работает в РФ / блокировки", r"росси|рф\b|блокир|ркн"),
    ]
    n = len(texts) or 1
    rows = []
    for label, rx in patterns:
        c = sum(1 for t in texts if re.search(rx, t, re.I))
        rows.append((label, c, 100.0 * c / n))
    return sorted(rows, key=lambda x: -x[1])


def main() -> None:
    creatives_csv = ROOT / "tgmaps-vpn-creatives.csv"
    if not creatives_csv.exists():
        raise SystemExit(f"no {creatives_csv}")
    creatives = list(csv.DictReader(creatives_csv.open(encoding="utf-8")))
    dests = sorted(
        {
            (r.get("destination") or "").strip().lstrip("@")
            for r in creatives
            if (r.get("destination") or "").strip()
        },
        key=str.lower,
    )
    print(f"destinations: {len(dests)} creatives: {len(creatives)}")

    # unique texts
    texts_raw = [normalize_text(r.get("text") or "") for r in creatives]
    texts_raw = [t for t in texts_raw if t]
    unique_exact = set(texts_raw)
    # softer unique: collapse whitespace + lower
    unique_soft = set(re.sub(r"\s+", " ", t).strip().lower() for t in texts_raw)
    print(f"unique texts exact: {len(unique_exact)}")
    print(f"unique texts soft(lower+ws): {len(unique_soft)}")

    spy_mau = load_spy_mau()
    print(f"tgadsspy mau map: {len(spy_mau)}")

    stats: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(fetch_tg_stats, d): d for d in dests}
        done = 0
        for fut in as_completed(futs):
            done += 1
            row = fut.result()
            login = row["login"].lower()
            if spy_mau.get(login) and not row.get("mau"):
                row["mau"] = spy_mau[login]
                row["mau_source"] = "tgadsspy"
            elif row.get("mau"):
                row["mau_source"] = "t.me"
            else:
                row["mau_source"] = ""
            if spy_mau.get(login):
                row["spy_mau"] = spy_mau[login]
            stats[login] = row
            if done % 40 == 0 or done == len(dests):
                print(f"  t.me {done}/{len(dests)}")

    # audience decision
    for login, row in stats.items():
        kind = row.get("kind") or ("bot" if is_bot(login) else "channel")
        mau = row.get("mau")
        subs = row.get("subscribers")
        if kind == "bot":
            if mau is None:
                gate = "unknown"
            elif mau >= 10_000:
                gate = "pass_10k"
            elif mau >= 5_000:
                gate = "pass_5k"
            else:
                gate = "fail"
            row["audience"] = mau
            row["audience_metric"] = "mau"
        else:
            if subs is None:
                gate = "unknown"
            elif subs >= 10_000:
                gate = "pass_10k"
            else:
                gate = "fail"
            row["audience"] = subs
            row["audience_metric"] = "subscribers"
        row["gate"] = gate
        row["kind"] = kind

    # creatives count per dest
    by_dest = Counter((r.get("destination") or "").lower() for r in creatives)
    max_ch = defaultdict(int)
    sample_text = {}
    for r in creatives:
        d = (r.get("destination") or "").lower()
        max_ch[d] = max(max_ch[d], int(r.get("channels_count") or 0))
        sample_text.setdefault(d, r.get("text") or "")

    out_csv = ROOT / "tgmaps-vpn-destinations.csv"
    fields = [
        "destination",
        "kind",
        "name",
        "creatives",
        "max_channels_count",
        "mau",
        "subscribers",
        "audience",
        "audience_metric",
        "mau_source",
        "spy_mau",
        "gate",
        "extra",
        "sample_text",
    ]
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for login in sorted(stats.keys()):
            row = stats[login]
            w.writerow(
                {
                    "destination": login,
                    "kind": row.get("kind"),
                    "name": row.get("name") or "",
                    "creatives": by_dest.get(login, 0),
                    "max_channels_count": max_ch.get(login, 0),
                    "mau": row.get("mau") or "",
                    "subscribers": row.get("subscribers") or "",
                    "audience": row.get("audience") or "",
                    "audience_metric": row.get("audience_metric") or "",
                    "mau_source": row.get("mau_source") or "",
                    "spy_mau": row.get("spy_mau") or "",
                    "gate": row.get("gate") or "",
                    "extra": row.get("extra") or "",
                    "sample_text": (sample_text.get(login) or "")[:200],
                }
            )

    gate_c = Counter(r.get("gate") for r in stats.values())
    kind_c = Counter(r.get("kind") for r in stats.values())
    phrases = phrase_stats(list(unique_exact))

    digest = ROOT / "tgmaps-vpn-texts-and-audience.md"
    lines = [
        f"# TgMaps VPN — тексты и аудитория посадочных",
        "",
        f"Креативов: **{len(creatives)}**. Destination: **{len(dests)}**.",
        f"Уникальных текстов (exact): **{len(unique_exact)}**.",
        f"Уникальных текстов (lower+ws): **{len(unique_soft)}**.",
        "",
        "## Посадочные: gate (боты MAU, каналы subscribers)",
        "",
        f"- kind: {dict(kind_c)}",
        f"- gate: {dict(gate_c)}",
        "",
        "Критерии: бот `pass_10k` если MAU≥10k, `pass_5k` если ≥5k; канал `pass_10k` если subs≥10k.",
        "MAU с публичного t.me часто скрыт — тогда берём `bot_mau` из tgadsspy, иначе `unknown`.",
        "",
        "### pass_10k",
        "",
    ]
    for login, row in sorted(
        stats.items(),
        key=lambda kv: (-(kv[1].get("audience") or 0), kv[0]),
    ):
        if row.get("gate") != "pass_10k":
            continue
        lines.append(
            f"- **@{login}** ({row.get('kind')}) {row.get('audience_metric')}="
            f"{row.get('audience')} — _{row.get('name') or ''}_"
        )
    lines += ["", "### pass_5k (только боты 5–10k)", ""]
    for login, row in sorted(
        stats.items(),
        key=lambda kv: (-(kv[1].get("audience") or 0), kv[0]),
    ):
        if row.get("gate") != "pass_5k":
            continue
        lines.append(
            f"- **@{login}** MAU={row.get('audience')} — _{row.get('name') or ''}_"
        )
    lines += ["", "### fail (<порога)", ""]
    fails = [kv for kv in stats.items() if kv[1].get("gate") == "fail"]
    lines.append(f"Всего fail: **{len(fails)}**")
    for login, row in sorted(fails, key=lambda kv: (-(kv[1].get("audience") or 0), kv[0]))[:40]:
        lines.append(
            f"- @{login} ({row.get('kind')}) {row.get('audience_metric')}="
            f"{row.get('audience')}"
        )
    lines += ["", "### unknown (нет цифры)", ""]
    unk = [kv for kv in stats.items() if kv[1].get("gate") == "unknown"]
    lines.append(f"Всего unknown: **{len(unk)}** — нужна Telemetr/Ads Spy догрузка")
    for login, row in sorted(unk, key=lambda kv: kv[0])[:50]:
        lines.append(f"- @{login} ({row.get('kind')})")

    lines += ["", "## Черновой разрез текстов (до полного структурирования)", ""]
    lines.append(f"База: {len(unique_exact)} уник. текстов.")
    for label, c, pct in phrases:
        lines.append(f"- **{label}**: {c} ({pct:.0f}%)")

    lines += [
        "",
        "## Файлы",
        "",
        "- `общее/tgmaps-vpn-destinations.csv`",
        "- `общее/tgmaps-vpn-creatives.csv`",
        "",
    ]
    digest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", out_csv)
    print("wrote", digest)
    print("gates", dict(gate_c))


if __name__ == "__main__":
    main()
