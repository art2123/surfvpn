# -*- coding: utf-8 -*-
import json
import re
import urllib.request

UA = "Mozilla/5.0"
LOGINS = [
    "newtech_digest",
    "denissexy",
    "sekretokanalo",
    "khmrchk",
    "sapiscience",
    "inno_scope",
    "dbeskromny",
    "lifegoodd1",
    "bmchn",
    "evgenmt",
    "lobushkin",
    "tolk_tolk",
    "sotavpn",
    "dedvpn",
    "grumarket",
    "aprelteam",
    "onlinerby",
    "pophistory",
    "scihubreal",
    "jichangtj",
    "technoinsider",
]


def classify(blob: str) -> list[str]:
    flags = []
    checks = [
        ("vpn", r"\bvpn\b|впн|впн\b"),
        ("rkn", r"ркн|роскомнадзор"),
        ("block", r"блокир|обход|белый список|white.?list|замедл"),
        ("tech", r"технолог|гаджет|нейросет|\bии\b|\bai\b|startup|инновац|iphone|android"),
        ("sci", r"наук|биолог|космос|медицин|физик"),
        ("scam", r"скам|мошен"),
        ("crypto", r"крипт|bitcoin|токен"),
        ("history", r"средневек|истори"),
        ("finance", r"акци|финанс|инвест|рынок"),
    ]
    for name, pat in checks:
        if re.search(pat, blob, re.I):
            flags.append(name)
    return flags


out = []
for login in LOGINS:
    url = f"https://t.me/s/{login}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
        title_m = re.search(r'og:title" content="([^"]+)', html)
        desc_m = re.search(r'og:description" content="([^"]+)', html)
        extra_m = re.search(r'tgme_page_extra">([^<]+)', html)
        posts = re.findall(
            r'class="tgme_widget_message_text[^>]*>([\s\S]*?)</div>', html
        )
        texts = []
        for p in posts[:5]:
            t = re.sub(r"<[^>]+>", " ", p)
            t = re.sub(r"\s+", " ", t).strip()
            texts.append(t[:140])
        desc = desc_m.group(1) if desc_m else ""
        blob = (" ".join(texts) + " " + desc).lower()
        out.append(
            {
                "login": login,
                "title": title_m.group(1) if title_m else "",
                "extra": extra_m.group(1).strip() if extra_m else "",
                "flags": classify(blob),
                "desc": desc[:160],
                "sample": texts[:2],
            }
        )
    except Exception as e:
        out.append({"login": login, "err": str(e)})

print(json.dumps(out, ensure_ascii=False, indent=2))
