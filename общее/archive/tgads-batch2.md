# Batch 2 — 50 связок TG Ads (Blanc Actions)

Дата подготовки: 2026-09-17. Структура: **25 площадок × t01+t04**, `cr=x`, `scope=s`, `_eur`.

Коды для Marketing Panel (уже в буфере обмена и в файле): [`tgads-batch2-codes.txt`](tgads-batch2-codes.txt)

```bash
python общее/scripts/export_tgads_admin_campaigns.py
# статус «к заливке» / On Hold / Active где промокод ≠ добавлен
```

**До Create Ad:** вставить 50 строк в админку (промокоды / кампании). Потом — Create Ad On Hold, проставить `ad_id` в **Связки**, `промокод в админке=добавлен`.

## 25 площадок

| # | Логин | pl | slug | Blanc Actions≈ |
|---|---|---|---|---:|
| 1 | @technoinsider | c | technoinside | 1347 |
| 2 | @v2raytun_bot | b | v2raytunbot | 167 |
| 3 | @amnezia_vpn_news_ru | c | amneziavpnne | 57 |
| 4 | @proton_vpn_news | c | protonvpnnew | 52 |
| 5 | @fastvpnkeybot | b | fastvpnkeybo | 32 |
| 6 | @vpnural | c | vpnural | 32 |
| 7 | @clubvpnru_bot | b | clubvpnrubot | 52 |
| 8 | @phonkvpnbot | b | phonkvpnbot | 45 |
| 9 | @atelecomprovpn | c | atelecomprov | 28 |
| 10 | @adguardru | c | adguardru | 22 |
| 11 | @gruvpnbot | b | gruvpnbot | 162 |
| 12 | @phantom_vpn_robot | b | phantomvpnro | 143 |
| 13 | @x_rocket_vpn_bot | b | xrocketvpnbo | 114 |
| 14 | @velvet_vpn_bot | b | velvetvpnbot | 106 |
| 15 | @vpn1_news | c | vpn1news | 76 |
| 16 | @siriusvpn | c | siriusvpn | 70 |
| 17 | @planetavpna | c | planetavpna | 22 |
| 18 | @green_vpn | c | greenvpn | 19 |
| 19 | @vezarys | c | vezarys | 14 |
| 20 | @dedvpn | c | dedvpn | 10 |
| 21 | @vpnducksbot | b | vpnducksbot | 13 |
| 22 | @bloggervpnbot | b | bloggervpnbo | 10 |
| 23 | @vpn_raketa_bot | b | vpnraketabot | 10 |
| 24 | @vpnui_bot | b | vpnuibot | 17 |
| 25 | @toshibuvpn_bot | b | toshibuvpnbo | 17 |

Тексты из **Креативы**: `t01`, `t04`. Кнопка OPEN. Budget/Daily €8, CPM €3, views/user 1, status On Hold. URL: `https://t.me/getSurfVpnBot?start={code}`.

Вне партии (CTR-риск): `@mybatyaonline_bot`, `@ejxbot`.

## Сделано в таблице

- **VPN-сервисы:** +10 недостающих логинов
- **Слаги:** +25
- **Связки:** 50 строк, статус `к заливке`, `промокод в админке=нет`, cpm/budget заполнены

## Create Ad

**Статус 2026-09-17 ~18:55:**
- Marketing Panel: пользователь вставил → в **Связках** у 50 кодов **`промокод в админке=добавлен`**
- Объявления: **ещё 0/50** — browser MCP (`cursor-ide-browser`) отвечает `Server not found`

После починки Simple Browser / Browser Tab в Cursor: команда «создавай объявления».
