"""Enrich curated hybrid shortlist with Telemetr public page metrics via stdin logins."""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "imports" / "ti_hybrid_telemetr_er.json"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def parse_metrics(text: str) -> dict:
    def num(s: str) -> int | None:
        s = s.replace("\u00a0", " ").replace("'", "").replace(" ", "").replace(",", ".")
        m = re.search(r"[\d.]+", s)
        if not m:
            return None
        try:
            return int(float(m.group()))
        except ValueError:
            return None

    out: dict = {}
    m = re.search(
        r"Подписчиков\s*Всего\s*([\d\s'’]+)",
        text,
        re.I,
    )
    if m:
        out["subs"] = num(m.group(1))
    m = re.search(r"Просмотров на пост\s*([\d\s'’]+)", text, re.I)
    if m:
        out["views"] = num(m.group(1))
    m = re.search(r"\bER\s*([\d.,]+)\s*%", text, re.I)
    if m:
        out["er"] = float(m.group(1).replace(",", "."))
    m = re.search(r"Суточный\s*([\d.,]+)\s*%", text, re.I)
    if m:
        out["er_daily"] = float(m.group(1).replace(",", "."))
    return out


def fetch(login: str) -> dict:
    url = f"https://telemetr.me/@{login}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode("utf-8", "ignore")
    except Exception as e:
        return {"login": login, "error": str(e)}
    # strip tags roughly for regex
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"\n+", "\n", text)
    metrics = parse_metrics(text)
    title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
    return {
        "login": login,
        "url": url,
        "title": title_m.group(1).strip() if title_m else None,
        **metrics,
        "has_auth_wall": "Авторизуйтесь" in html,
    }


def main() -> None:
    logins = [ln.strip().lstrip("@") for ln in sys.stdin if ln.strip()]
    rows = [fetch(x) for x in logins]
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} rows)")
    for r in rows:
        print(
            f"{r.get('login')}: subs={r.get('subs')} views={r.get('views')} "
            f"er={r.get('er')} err={r.get('error')}"
        )


if __name__ == "__main__":
    main()
