# -*- coding: utf-8 -*-
"""Refresh texts+audience markdown from current CSVs."""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]

creatives = list(csv.DictReader((ROOT / "tgmaps-vpn-creatives.csv").open(encoding="utf-8")))
rows = list(csv.DictReader((ROOT / "tgmaps-vpn-destinations.csv").open(encoding="utf-8")))
placements = list(
    csv.DictReader((ROOT / "tgmaps-vpn-placements.csv").open(encoding="utf-8"))
)
texts = [(r.get("text") or "").strip() for r in creatives if (r.get("text") or "").strip()]
unique = set(texts)
soft = {" ".join(t.lower().split()) for t in texts}
patterns = [
    ("N дней бесплатно / триал", r"(\d+)\s*дн[яей].{0,12}бесплат|бесплатн.{0,20}(\d+)\s*дн|триал|пробн"),
    ("от X ₽/мес", r"от\s*\d+[\s\u00a0]*[₽р]|/\s*мес|\d+\s*₽"),
    ("обход белых списков", r"бел(ый|ые|ых)\s*спис|white.?list"),
    ("глушилки", r"глушил"),
    ("YouTube", r"youtube|ютуб"),
    ("Happ / клиенты", r"\bhapp\b|v2raytun|v2box|hiddify"),
    ("все устройства", r"устройств|iphone|android|windows|mac|\bтв\b|\btv\b"),
    ("реферал / друг", r"друг|реферал|приглас"),
    ("без логов", r"без\s*лог|no\s*log"),
    ("скорость", r"скорост|быстр|лета"),
    ("работает в РФ / блокировки", r"росси|\bрф\b|блокир|ркн"),
]
n = len(unique) or 1
gates = Counter(r.get("gate") for r in rows)
kinds = Counter(r.get("kind") for r in rows)
ch_n = len({r["channel_login"].lower() for r in placements if r.get("channel_login")})


def aud(r):
    try:
        return int(float(r.get("audience") or 0))
    except ValueError:
        return 0


lines = [
    "# TgMaps VPN — тексты и аудитория посадочных",
    "",
    f"Креативов: **{len(creatives)}**. Destination: **{len(rows)}**.",
    f"Уникальных текстов (exact): **{len(unique)}**.",
    f"Уникальных текстов (lower+ws): **{len(soft)}**.",
    f"Placement-строк: **{len(placements)}**, уник. каналов показа: **{ch_n}**.",
    "",
    "## Посадочные: gate (боты MAU, каналы subscribers)",
    "",
    f"- kind: {dict(kinds)}",
    f"- gate: {dict(gates)}",
    "",
    "Критерии: бот `pass_10k` при MAU≥10k, `pass_5k` при ≥5k; канал `pass_10k` при subs≥10k.",
    "MAU: t.me почти не отдаёт + overlap с tgadsspy creatives. Догрузка `/bots` сейчас в 429 — unknown на повтор/Telemetr.",
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
for row in sorted(fails, key=lambda r: (-aud(r), r["destination"]))[:50]:
    lines.append(
        f"- @{row['destination']} ({row.get('kind')}) "
        f"{row.get('audience_metric')}={row.get('audience')}"
    )
unk = [r for r in rows if r.get("gate") == "unknown"]
lines += [
    "",
    "### unknown (нет цифры)",
    "",
    f"Всего unknown: **{len(unk)}** — догрузить MAU позже (tgadsspy `/bots` или Telemetr)",
]
for row in sorted(unk, key=lambda r: r["destination"])[:80]:
    lines.append(f"- @{row['destination']} ({row.get('kind')})")

lines += ["", "## Черновой разрез текстов (до полного структурирования)", ""]
lines.append(f"База: {len(unique)} уник. текстов.")
for label, rx in patterns:
    c = sum(1 for t in unique if re.search(rx, t, re.I))
    lines.append(f"- **{label}**: {c} ({100 * c / n:.0f}%)")
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
print("wrote", out)
print("unique", len(unique), "gates", dict(gates), "channels", ch_n)
