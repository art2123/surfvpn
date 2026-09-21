# -*- coding: utf-8 -*-
"""Словарь VPN-брендов для разбора нативной рекламы (Telemetr и т.п.).

Пополнять: (canonical, regex). canonical — как пишем в таблице.
"""
from __future__ import annotations

import re

# (canonical_name, compiled_regex) — порядок важен: более специфичные выше
_BRAND_SPECS: list[tuple[str, str]] = [
    # крупные / частые
    ("BlancVPN", r"\bblanc\s*vpn\b|blancvpn|blanc\.link|fck[_\\s-]?rkn[_\\s-]?bot|@fck_rkn_bot"),
    ("HideMyName", r"\bhide\s*my\s*name\b|hidemyname|hidemy\.name"),
    ("Amnezia", r"\bamnezia\b|амнези"),
    ("Red Shield", r"\bred\s*shield\b|redshield|ред\s*щилд|редшилд"),
    ("VPN Generator", r"\bvpn\s*generator\b|vpngen|генератор\s*vpn"),
    ("Paper VPN", r"\bpaper\s*vpn\b|papervpn|пейпер"),
    ("Skip VPN", r"\bskip\s*vpn\b|skipvpn"),
    ("Unlock VPN", r"\bunlock\s*vpn\b|unlockvpn"),
    ("DoDo", r"\bdodo\b|додо\s*vpn|dodovpn"),
    ("Green VPN", r"\bgreen[_\s-]*vpn\b|greenvpn"),
    ("Magnum", r"\bmagnum\b"),
    ("NeoVPN", r"\bneo\s*vpn\b|neovpn"),
    ("BoltVPN", r"\bbolt\s*vpn\b|boltvpn"),
    ("CloVPN", r"\bclo\s*vpn\b|clovpn"),
    ("VolnaLink", r"\bvolna(?:link)?\b|волна\s*vpn|vpnvolna"),
    ("Sirius VPN", r"\bsirius\s*vpn\b|siriusvpn"),
    ("Ural VPN", r"\bural\s*vpn\b|uralvpn"),
    ("OneGo", r"\bone\s*go\b|onego"),
    ("FRDM", r"\bfrdm\b|freedom\s*vpn"),
    ("Anonch", r"\banonch\b"),
    ("Platina", r"\bplatina\b|платин"),
    ("TurboGnom", r"\bturbognom\b|турбогном"),
    ("LumixVPN", r"\blumix\s*vpn\b|lumixvpn"),
    ("Step2Freedom", r"\bstep\s*2\s*freedom\b|step2freedom"),
    ("DEW VPN", r"\bdew\s*vpn\b"),
    ("Шарий VPN", r"шарий\s*vpn"),
    # из unknown-примеров
    ("Durev VPN", r"\bdurev\s*vpn\b|durevvpn|\bdurev\b"),
    ("AvalonVPN", r"\bavalon\s*vpn\b|avalonvpn"),
    ("VIPASS", r"\bvipass\b"),
    ("PEREC", r"@perec\b|\bperec\s*vpn\b|\bперец\s*vpn\b"),
    ("Titan VPS", r"\btitan\s*vps\b"),
    ("Spacy VPN", r"\bspacy\s*vpn\b"),
    ("VELTRO VPN", r"\bveltro\s*vpn\b|veltrovpn"),
    ("Родня VPN", r"родня\s*vpn"),
    ("ZeroVPN", r"\bzero\s*vpn\b|zerovpn"),
    ("ESIMPSON", r"\besimson\b|esimpson"),
    ("Bluxor VPN", r"\bbluxor\s*vpn\b|bluxorvpn|\bbluxor\b"),
    ("Wings V", r"\bwings\s*v\b"),
    ("Happy VPN", r"\bhappy\s*vpn\b|vpn_happy|vpn_happybot"),
    ("AstrVPN", r"\bastr\s*vpn\b|astrvpn|@astrvpn"),
    ("TunnelX", r"\btunnel\s*x\b|tunnelx"),
    ("Chudo VPN", r"\bchudo\s*vpn\b|vpnchudo"),
    ("Luminox", r"\bluminox\b"),
    ("Hikari VPN", r"\bhikari\s*vpn\b|hikari_vpn"),
    ("Mori VPN", r"\bmori\s*vpn\b|morivpn"),
    ("Viza VPN", r"\bviza\s*vpn\b|viza_vpn"),
    ("Pride VPN", r"\bpride\s*vpn\b|pridevpn"),
    ("Disco VPN", r"\bdisco\s*vpn\b|vpn_disco"),
    ("DarkLine VPN", r"\bdarkline\b"),
    ("Mask VPN", r"\bmask\s*vpn\b|maskvpn"),
    ("Pampa VPN", r"\bpampa\s*vpn\b|pampavpn"),
    ("Kryak VPN", r"\bkryak\s*vpn\b|kryakvpn"),
    ("HOTVPN", r"\bhot\s*vpn\b|\bhotvpn\b"),
    ("H2VPN", r"\bh2\s*vpn\b|@h2vpn\b"),
    ("FlyVPN", r"\bfly\s*vpn\b|@flyvpn\b"),
    ("VPN451", r"vpn451"),
    ("Freepass VPN", r"\bfreepass\b"),
    ("Cicada VPN", r"\bcicada\b|cicxda"),
    ("Cochan VPN", r"\bcochan\b"),
    ("New1984 VPN", r"new_?1984|1984_vpn"),
    ("Probel VPN", r"\bprobel\b"),
    ("VPNG", r"@vpng_bot\b|\bvpng\b"),
    ("CoffeeMania VPN", r"coffemania|coffeemania"),
    ("MSE VPN", r"vpnmse"),
    ("ProxyTG", r"@proxytg\b"),
    # добор 18.09.2026 из Telemetr unknown
    ("Liberty VPN", r"\bliberty\s*vpn\b|liberty-vpn|vpn\s*liberty|vpn_liberty"),
    ("WiseKeys VPN", r"\bwisekeys\b"),
    ("InstVPN", r"\binst\s*vpn\b|\binstvpn\b"),
    ("Legendary VPN", r"\blegendary\s*vpn\b"),
    ("PlusOne VPN", r"\bplus\s*one\s*vpn\b|plusone\s*vpn|\bplusone\b"),
    ("Duck VPN", r"\bduck\s*vpn\b|@duckvpn\b|\bduckvpn\b"),
    ("Polet VPN", r"\bpolet\s*vpn\b|poletvpn"),
    ("Edge VPN", r"\bedge\s*vpn\b|edgevpn"),
    ("FLUX VPN", r"\bflux\s*vpn\b|fluxvpn"),
    ("Shiva VPN", r"\bshiva\s*vpn\b|shivavpn"),
    ("Gamma VPN", r"\bgamma\s*vpn\b"),
    ("LTVPN", r"\blt\s*vpn\b|\bltvpn\b"),
    ("Чик-Чирик VPN", r"чик-?чирик"),
    ("Vibe VPN", r"\bvibe\s*vpn\b|vibevpn"),
    ("Whale VPN", r"\bwhale\s*vpn\b|whalevpn"),
    ("White VPN", r"\bwhite\s*vpn\b|whitevpn"),
    ("Zona VPN", r"\bzona\s*vpn\b|zona_vpn"),
    ("UPS VPN", r"\bups\s*vpn\b|upsvpn"),
    ("Geen VPN", r"\bgeen\s*vpn\b|geenvpn"),  # typo-brand / bot
    ("Liberty Bot", r"vpn_liberty_bot"),
    ("Алтай VPN", r"алтай\s*vpn|altai\s*vpn|@?altayvpn"),
    ("AlloNet VPN", r"allonet|allo\s*net"),
    # добор 21.09.2026 из unknown-пересчёта
    ("Appa VPN", r"\bappa\s*vpn\b|appavpn"),
    ("SAVE VPN", r"\bsave\s*vpn\b|savevpn"),
    ("Endor VPN", r"\bendor\s*vpn\b|endorvpn"),
    ("Click VPN", r"\bclick\s*vpn\b|clickvpn"),
    ("NZT VPN", r"\bnzt\s*vpn\b|nztvpn"),
    ("Gru VPN", r"\bgru\s*vpn\b|gruvpn"),
    ("INS VPN", r"\bins\s*vpn\b|insvpn"),
    ("EjX VPN", r"\bejx\s*vpn\b|ejxvpn|\bejx\b"),
    ("Anarchy VPN", r"\banarchy\s*vpn\b|anarchyvpn"),
    ("WireBuddy VPN", r"\bwirebuddy\b"),
    ("Supra VPN", r"\bsupra\s*vpn\b|supravpn"),
    ("Ledokol VPN", r"\bledokol\s*vpn\b|ледокол\s*vpn"),
    ("ShadowHub VPN", r"\bshadowhub\b"),
    ("Airlines VPN", r"\bairlines\s*vpn\b"),
    ("Taurus VPN", r"\btaurus\s*vpn\b"),
    ("Adaptive VPN", r"\badaptive\s*vpn\b|adaptivevpn"),
    ("EVA VPN", r"\beva\s*vpn\b|evavpn"),
    ("Vasco VPN", r"\bvasco\s*vpn\b|vascovpn"),
    ("Sova VPN", r"\bsova\s*vpn\b|sovavpn|сова\s*vpn"),
    ("Spintria VPN", r"\bspintria\b"),
    ("GPT VPN", r"\bgpt\s*vpn\b|gptvpn"),
    ("Ghost VPN", r"\bghost\s*vpn\b|ghostvpn"),
    ("DARV VPN", r"\bdarv\s*vpn\b|darvvpn"),
    ("Strelka VPN", r"\bstrelka\s*vpn\b|стрелка\s*vpn"),
    ("Burn VPN", r"\bburn\s*vpn\b|burnvpn"),
    ("Sputnik VPN", r"\bsputnik\s*vpn\b|sputnikvpn"),
    ("MSI VPN", r"\bmsi\s*vpn\b|msivpn"),
    ("HFC VPN", r"\bhfc\s*vpn\b|hfcvpn"),
    ("MyVPN24", r"myvpn24"),
    ("HARD VPN", r"\bhard\s*vpn\b|hardvpn"),
    ("Max VPN", r"\bmax\s*vpn\b|maxvpn"),  # не путать с мессенджером MAX без VPN
    ("AVARA VPN", r"\bavara\s*vpn\b|avaravpn"),
    ("Denver VPN", r"\bdenver\s*vpn\b|denvervpn"),
    ("Riot VPN", r"\briot\s*vpn\b|riotvpn"),
    ("Kosmo VPN", r"\bkosmo\s*vpn\b|kosmovpn"),
]

# бот → бренд (если в тексте только @bot)
_BOT_TO_BRAND: dict[str, str] = {
    "astrvpn_bot": "AstrVPN",
    "vipass_robot": "VIPASS",
    "vpn_happybot": "Happy VPN",
    "tunnelx_vpn": "TunnelX",
    "vpnchudobot": "Chudo VPN",
    "luminox_vpn_bot": "Luminox",
    "hikari_vpn_bot": "Hikari VPN",
    "morivpnrobot": "Mori VPN",
    "viza_vpnbot": "Viza VPN",
    "pridevpnbuy_bot": "Pride VPN",
    "vpn_disco_bot": "Disco VPN",
    "darklinevpn_bot": "DarkLine VPN",
    "maskvpn_bot": "Mask VPN",
    "pampavpn_bot": "Pampa VPN",
    "kryakvpnbot": "Kryak VPN",
    "hotvpn_bot": "HOTVPN",
    "h2vpn": "H2VPN",
    "flyvpn": "FlyVPN",
    "vpn451_on": "VPN451",
    "freepass_vpn_bot": "Freepass VPN",
    "cicxdavpn_bot": "Cicada VPN",
    "cochanvpnbot": "Cochan VPN",
    "new_1984_vpn_bot": "New1984 VPN",
    "probelvpnbot": "Probel VPN",
    "vpng_bot": "VPNG",
    "coffemaniavpnbot": "CoffeeMania VPN",
    "vpnmse_bot": "MSE VPN",
    "bluxorvpn_bot": "Bluxor VPN",
    "vpnvolnabot": "VolnaLink",
    "luchshiyvpnxbot": "Лучший VPN",
    "impvpnbot": "Imp VPN",
    "turbognomvpn": "TurboGnom",
    "neovpn": "NeoVPN",
    "vpn_perec": "PEREC",
    "perec": "PEREC",
    "vpn_liberty_bot": "Liberty VPN",
    "fck_rkn_bot": "BlancVPN",
    "hidemyname_bot": "HideMyName",
    "duckvpn": "Duck VPN",
    "poletvpn": "Polet VPN",
    "wisekeys": "WiseKeys VPN",
    "wisekeysvpn": "WiseKeys VPN",
    "instvpn": "InstVPN",
    "vibevpn_xbot": "Vibe VPN",
    "whalevpnofficial_bot": "Whale VPN",
    "whitevpn_probot": "White VPN",
    "zona_vpn_bot": "Zona VPN",
    "upsvpnbot": "UPS VPN",
    "ural_vpnbot": "Ural VPN",
    "magnumvpnbot": "Magnum",
    "magnumvpn": "Magnum",
    "unlockedvpnbot": "Unlock VPN",
    "geenvpn": "Geen VPN",
    "gptvpnrbot": "GPT VPN",
    "gruvpnbot": "Gru VPN",
    "allonetvpn_bot": "AlloNet VPN",
    "upsvpnbot": "UPS VPN",
    "cicxdavpn_bot": "Cicada VPN",
    "adaptivevpn_bot": "Adaptive VPN",
    "sputnikvpn_robot": "Sputnik VPN",
    "spintriavpnbot": "Spintria VPN",
    "msivpnbot": "MSI VPN",
    "vpnmse_bot": "MSE VPN",
    "luchshiyvpnxbot": "Лучший VPN",
    "hfcvpn_bot": "HFC VPN",
    "myvpn24_bot": "MyVPN24",
    "endorvpn": "Endor VPN",
    "appavpn": "Appa VPN",
    "savevpn": "SAVE VPN",
    "clickvpn": "Click VPN",
    "nztvpn": "NZT VPN",
}

BRAND_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (name, re.compile(pat, re.I)) for name, pat in _BRAND_SPECS
]

# креатив без имени → бренд по отпечатку (осторожно)
_CREATIVE_FPS: list[tuple[str, re.Pattern[str]]] = [
    (
        "OneGo",
        re.compile(
            r"белые списки\s*[–—-]\s*вс[её].*появился vpn.*оператор связи",
            re.I | re.S,
        ),
    ),
    (
        "DoDo",
        re.compile(r"вы выиграли бесплатный впн|цензура проиграла.*хватит платить за vpn", re.I),
    ),
]


def extract_brands(text: str) -> list[str]:
    """Уникальные бренды в порядке появления в тексте."""
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        if name and name not in seen and name.lower() != "unknown":
            seen.add(name)
            found.append(name)

    for name, rx in BRAND_PATTERNS:
        if rx.search(text):
            add(name)

    for m in re.finditer(r"(?:@|t\.me/)([A-Za-z0-9_]{3,})", text, re.I):
        bot = m.group(1).lower()
        if bot in _BOT_TO_BRAND:
            add(_BOT_TO_BRAND[bot])
        elif bot in {"perec"}:
            add("PEREC")
        elif "vpn" in bot and bot not in {"vpn", "vpns"}:
            # не плодить @VPN_xxx если уже есть канонический бренд
            mapped = False
            for name, rx in BRAND_PATTERNS:
                if rx.search(bot) or rx.search(m.group(1)):
                    add(name)
                    mapped = True
                    break
            if not mapped:
                add("@" + m.group(1))

    for name, rx in _CREATIVE_FPS:
        if rx.search(text):
            add(name)

    # «X VPN» / «VPN X» общего вида, если ещё не поймали
    for m in re.finditer(
        r"(?:из|попробуй|установи|рекоменду\w*|сервис|проект)\s+([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_-]{1,24})\s*VPN",
        text,
        re.I,
    ):
        raw = m.group(1).strip()
        if raw.lower() in {"свой", "ваш", "этот", "наш", "новый", "лучший", "бесплатный", "нормальный"}:
            continue
        canon = f"{raw} VPN"
        # не дублировать уже найденное тем же корнем
        if not any(raw.lower() in b.lower() for b in found):
            add(canon)

    for m in re.finditer(
        r"\b([A-Za-z][A-Za-z0-9]{1,20})\s*VPN\b",
        text,
        re.I,
    ):
        raw = m.group(1)
        if raw.lower() in {"a", "the", "for", "and", "with", "free", "best", "your"}:
            continue
        if not any(raw.lower() in b.lower().replace(" ", "") for b in found):
            # только если рядом sell-сигнал
            if re.search(r"промокод|бот|t\.me/|скидк|тариф|подписк|попробуй|установи", text, re.I):
                add(f"{raw} VPN")

    return found


def format_brands(counts: dict[str, int]) -> str:
    items = sorted(counts.items(), key=lambda x: (-x[1], x[0].lower()))
    parts = []
    for name, n in items:
        if n <= 0:
            continue
        parts.append(f"{name}×{n}" if n > 1 else name)
    return "; ".join(parts)
