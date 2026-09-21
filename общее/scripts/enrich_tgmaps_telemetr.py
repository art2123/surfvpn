# -*- coding: utf-8 -*-
"""Enrich TgMaps VPN destinations via Telemetr.me (+ t.me MAU for bots).

Uses authenticated Telemetr session cookies from:
  общее/tgads-snapshots/_telemetr_cookies.json

Channels: exact username match in /api/v1/catalog/channels/search → subscribers.
Bots: Telemetr usually has no bot index → t.me monthly users (no tgadsspy).
"""
from __future__ import annotations

import csv
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "tgads-snapshots"
COOKIES_PATH = SNAP / "_telemetr_cookies.json"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
CTX = ssl.create_default_context()


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


def is_bot_login(login: str) -> bool:
    login = login.lower()
    return login.endswith("bot") or login.endswith("robot")


# TgMaps sponsor_type_id: 1=bot, 2=channel, 3=site, 4=dm, 5=webapp
TGMAPS_KIND = {1: "bot", 2: "channel", 3: "site", 4: "dm", 5: "webapp"}


def load_telemetr_cookies() -> dict[str, str]:
    if not COOKIES_PATH.exists():
        raise SystemExit(
            f"нет {COOKIES_PATH} — сначала python общее/scripts/_tmp_telemetr_cookie_export.py"
        )
    payload = json.loads(COOKIES_PATH.read_text(encoding="utf-8"))
    return payload.get("map") or payload


def cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items() if v)


def nested_total(obj) -> int | None:
    """Unwrap Telemetr {total: N} / nested count shapes."""
    if obj is None:
        return None
    if isinstance(obj, (int, float)):
        return int(obj)
    if isinstance(obj, dict):
        if "total" in obj:
            return nested_total(obj["total"])
        if "count" in obj:
            return nested_total(obj["count"])
    return compact_num(obj)


class TelemetrClient:
    def __init__(self, cookies: dict[str, str], sleep: float = 0.25):
        self.cookies = cookies
        self.sleep = sleep
        self._last = 0.0

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": UA,
            "Accept": "application/json",
            "Cookie": cookie_header(self.cookies),
            "Referer": "https://telemetr.me/",
            "Origin": "https://telemetr.me",
        }

    def _throttle(self) -> None:
        now = time.monotonic()
        wait = self.sleep - (now - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def get_json(self, path: str) -> dict:
        self._throttle()
        url = "https://telemetr.me" + path
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"HTTP {exc.code} {path}: {body}") from exc

    def search_exact(self, login: str) -> dict | None:
        """Return catalog search item whose username matches login exactly."""
        q = urllib.parse.quote(login)
        data = self.get_json(f"/api/v1/catalog/channels/search?query={q}")
        items = data.get("items") or []
        login_l = login.lower().lstrip("@")
        for item in items:
            uname = (
                (item.get("links") or {}).get("userName")
                or item.get("username")
                or ""
            ).lower()
            if uname == login_l:
                return item
        # fallback: quoted catalog query
        q2 = urllib.parse.quote(f'"{login_l}"')
        data2 = self.get_json(
            f"/api/v1/catalog/channels?query={q2}&page=1&per_page=10"
        )
        for item in data2.get("items") or []:
            uname = (item.get("username") or "").lower()
            if uname == login_l:
                return item
        return None


def extract_subscribers(item: dict) -> int | None:
    stats = item.get("statistics") or {}
    # search API shape
    subs = nested_total((stats.get("subscribers") or {}).get("count"))
    if subs:
        return subs
    # catalog shape
    parts = nested_total((stats.get("participants") or {}).get("count"))
    if parts:
        return parts
    return nested_total(item.get("participants_count"))


def fetch_tg_stats(login: str, kind_hint: str | None = None) -> dict:
    kind_bot = (kind_hint == "bot") if kind_hint else is_bot_login(login)
    out = {
        "login": login,
        "kind": kind_hint or ("bot" if kind_bot else "channel"),
        "name": "",
        "mau": None,
        "subscribers": None,
        "extra": "",
        "ok": False,
        "error": "",
    }
    url = f"https://t.me/{login}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, context=CTX, timeout=20) as resp:
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
    members = re.search(r"([\d\s\.,MK]+)\s*members", html, re.I)
    if members and not out["subscribers"] and not kind_bot:
        out["subscribers"] = compact_num(members.group(1))
    # Only infer kind from HTML when TgMaps didn't tell us
    if not kind_hint:
        if "Start Bot" in html or "Send Message" in html or is_bot_login(login):
            out["kind"] = "bot"
        elif out["subscribers"]:
            out["kind"] = "channel"
    return out


def normalize_text(text: str) -> str:
    t = (text or "").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def phrase_stats(texts: list[str]) -> list[tuple[str, int, float]]:
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


def gate_for(kind: str, mau: int | None, subs: int | None) -> tuple[str, int | None, str]:
    if kind == "bot":
        if mau is None:
            return "unknown", None, "mau"
        if mau >= 10_000:
            return "pass_10k", mau, "mau"
        if mau >= 5_000:
            return "pass_5k", mau, "mau"
        return "fail", mau, "mau"
    if subs is None:
        return "unknown", None, "subscribers"
    if subs >= 10_000:
        return "pass_10k", subs, "subscribers"
    return "fail", subs, "subscribers"


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
    # majority sponsor_type_id per destination
    type_votes: dict[str, Counter] = defaultdict(Counter)
    for r in creatives:
        d = (r.get("destination") or "").strip().lstrip("@").lower()
        try:
            st = int(r.get("sponsor_type_id") or 0)
        except ValueError:
            st = 0
        if d and st:
            type_votes[d][st] += 1
    kind_by_dest: dict[str, str] = {}
    for d, votes in type_votes.items():
        top = votes.most_common(1)[0][0]
        kind_by_dest[d] = TGMAPS_KIND.get(top, "bot" if is_bot_login(d) else "channel")
    print(f"destinations: {len(dests)} creatives: {len(creatives)}")
    print("tgmaps kinds", dict(Counter(kind_by_dest.values())))

    texts_raw = [normalize_text(r.get("text") or "") for r in creatives]
    texts_raw = [t for t in texts_raw if t]
    unique_exact = set(texts_raw)
    unique_soft = {re.sub(r"\s+", " ", t).strip().lower() for t in texts_raw}
    print(f"unique texts exact: {len(unique_exact)} soft: {len(unique_soft)}")

    cookies = load_telemetr_cookies()
    print(f"telemetr cookies: {len(cookies)} keys={list(cookies)[:8]}")
    client = TelemetrClient(cookies, sleep=0.22)

    # smoke auth
    smoke = client.search_exact("technoinsider")
    if not smoke:
        raise SystemExit("Telemetr auth failed — search technoinsider empty")
    print("telemetr smoke ok, technoinsider subs=", extract_subscribers(smoke))

    tele: dict[str, dict] = {}
    for i, login in enumerate(dests, 1):
        try:
            item = client.search_exact(login)
            if item:
                tele[login.lower()] = {
                    "subscribers": extract_subscribers(item),
                    "title": item.get("title") or "",
                    "hit": True,
                }
            else:
                tele[login.lower()] = {"subscribers": None, "title": "", "hit": False}
        except Exception as exc:
            tele[login.lower()] = {
                "subscribers": None,
                "title": "",
                "hit": False,
                "error": str(exc)[:160],
            }
        if i % 25 == 0 or i == len(dests):
            hits = sum(1 for v in tele.values() if v.get("hit"))
            print(f"  telemetr {i}/{len(dests)} hits={hits}")

    # t.me for all (name + bot MAU + channel fallback)
    tg: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {
            pool.submit(fetch_tg_stats, d, kind_by_dest.get(d.lower())): d
            for d in dests
        }
        done = 0
        for fut in as_completed(futs):
            done += 1
            row = fut.result()
            tg[row["login"].lower()] = row
            if done % 40 == 0 or done == len(dests):
                print(f"  t.me {done}/{len(dests)}")

    by_dest = Counter((r.get("destination") or "").lower() for r in creatives)
    max_ch: dict[str, int] = defaultdict(int)
    sample_text: dict[str, str] = {}
    for r in creatives:
        d = (r.get("destination") or "").lower()
        max_ch[d] = max(max_ch[d], int(r.get("channels_count") or 0))
        sample_text.setdefault(d, r.get("text") or "")

    stats: dict[str, dict] = {}
    for login in dests:
        key = login.lower()
        trow = tg.get(key) or {}
        tel = tele.get(key) or {}
        kind = kind_by_dest.get(key) or trow.get("kind") or (
            "bot" if is_bot_login(login) else "channel"
        )
        # treat webapp like bot for MAU gate
        gate_kind = "bot" if kind in {"bot", "webapp", "dm"} else "channel"
        mau = trow.get("mau")
        # channels: prefer Telemetr subscribers; fallback t.me
        subs = None
        source = ""
        if gate_kind != "bot":
            if tel.get("hit") and tel.get("subscribers") is not None:
                subs = tel["subscribers"]
                source = "telemetr"
            elif trow.get("subscribers") is not None:
                subs = trow["subscribers"]
                source = "t.me"
        else:
            # bots: Telemetr almost never indexes; use t.me MAU
            if mau is not None:
                source = "t.me"
        name = trow.get("name") or tel.get("title") or ""
        gate, audience, metric = gate_for(gate_kind, mau, subs)
        stats[key] = {
            "kind": kind,
            "name": name,
            "mau": mau,
            "subscribers": subs,
            "audience": audience,
            "audience_metric": metric,
            "mau_source": source,
            "telemetr_hit": bool(tel.get("hit")),
            "telemetr_subs": tel.get("subscribers"),
            "gate": gate,
            "extra": trow.get("extra") or "",
            "error": tel.get("error") or trow.get("error") or "",
        }

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
        "telemetr_hit",
        "telemetr_subs",
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
                    "kind": row["kind"],
                    "name": row["name"],
                    "creatives": by_dest.get(login, 0),
                    "max_channels_count": max_ch.get(login, 0),
                    "mau": row["mau"] or "",
                    "subscribers": row["subscribers"] or "",
                    "audience": row["audience"] or "",
                    "audience_metric": row["audience_metric"],
                    "mau_source": row["mau_source"],
                    "telemetr_hit": int(row["telemetr_hit"]),
                    "telemetr_subs": row["telemetr_subs"] or "",
                    "gate": row["gate"],
                    "extra": row["extra"],
                    "sample_text": (sample_text.get(login) or "")[:200],
                }
            )

    gate_c = Counter(r["gate"] for r in stats.values())
    kind_c = Counter(r["kind"] for r in stats.values())
    src_c = Counter(r["mau_source"] for r in stats.values())
    tel_hits = sum(1 for r in stats.values() if r["telemetr_hit"])
    phrases = phrase_stats(list(unique_exact))

    digest = ROOT / "tgmaps-vpn-texts-and-audience.md"
    lines = [
        "# TgMaps VPN — тексты и аудитория посадочных",
        "",
        f"Креативов: **{len(creatives)}**. Destination: **{len(dests)}**.",
        f"Уникальных текстов (exact): **{len(unique_exact)}**.",
        f"Уникальных текстов (lower+ws): **{len(unique_soft)}**.",
        "",
        "## Посадочные: gate (боты MAU, каналы subscribers)",
        "",
        f"- kind: {dict(kind_c)}",
        f"- gate: {dict(gate_c)}",
        f"- source: {dict(src_c)}",
        f"- telemetr exact hits: **{tel_hits}** / {len(dests)}",
        "",
        "Критерии: бот `pass_10k` если MAU≥10k, `pass_5k` если ≥5k; канал `pass_10k` если subs≥10k.",
        "Каналы: **Telemetr.me** (`/api/v1/catalog/channels/search`, exact username).",
        "Боты: Telemetr почти не индексирует → MAU с публичного **t.me** (без tgadsspy).",
        "",
        "### pass_10k",
        "",
    ]
    for login, row in sorted(
        stats.items(), key=lambda kv: (-(kv[1].get("audience") or 0), kv[0])
    ):
        if row["gate"] != "pass_10k":
            continue
        lines.append(
            f"- **@{login}** ({row['kind']}) {row['audience_metric']}="
            f"{row['audience']} [{row['mau_source']}] — _{row['name']}_"
        )
    lines += ["", "### pass_5k (только боты 5–10k)", ""]
    for login, row in sorted(
        stats.items(), key=lambda kv: (-(kv[1].get("audience") or 0), kv[0])
    ):
        if row["gate"] != "pass_5k":
            continue
        lines.append(
            f"- **@{login}** MAU={row['audience']} [{row['mau_source']}] — _{row['name']}_"
        )
    lines += ["", "### fail (<порога)", ""]
    fails = [kv for kv in stats.items() if kv[1]["gate"] == "fail"]
    lines.append(f"Всего fail: **{len(fails)}**")
    for login, row in sorted(fails, key=lambda kv: (-(kv[1].get("audience") or 0), kv[0]))[
        :40
    ]:
        lines.append(
            f"- @{login} ({row['kind']}) {row['audience_metric']}={row['audience']} [{row['mau_source']}]"
        )
    lines += ["", "### unknown (нет цифры)", ""]
    unk = [kv for kv in stats.items() if kv[1]["gate"] == "unknown"]
    lines.append(
        f"Всего unknown: **{len(unk)}** — у ботов t.me скрыл MAU; у каналов нет в Telemetr"
    )
    for login, row in sorted(unk, key=lambda kv: kv[0])[:60]:
        lines.append(f"- @{login} ({row['kind']})")

    lines += ["", "## Черновой разрез текстов", ""]
    lines.append(f"База: {len(unique_exact)} уник. текстов.")
    for label, c, pct in phrases:
        lines.append(f"- **{label}**: {c} ({pct:.0f}%)")

    lines += [
        "",
        "## Файлы",
        "",
        "- `общее/tgmaps-vpn-destinations.csv`",
        "- `общее/tgmaps-vpn-creatives.csv`",
        "- `общее/tgads-snapshots/_telemetr_cookies.json`",
        "",
    ]
    digest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", out_csv)
    print("wrote", digest)
    print("gates", dict(gate_c), "sources", dict(src_c), "telemetr_hits", tel_hits)


if __name__ == "__main__":
    main()
