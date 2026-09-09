# PostHog (SUR-2)

Доски про **людей**, не про клики. Выручка, общий LTV, repeat покупок, mix тарифов, сток — остаются в админке. Расход рекламы — в Директе/Метрике. PostHog конверсии в Директ не шлёт.

## Семь отчётов первой очереди

1. **Воронка**  
   Входы разные, дальше общее: бот → триал или касса → оплата → VPN за сутки.  
   Сплит: source, бренд/generic, оффер. Где дыра — лендинг, бот, касса или онбординг.

2. **Четыре оффера**  
   Та же воронка + connect rate + деньги на одного зашедшего за 30 дней. Только новый трафик. Победитель по деньгам.

3. **Триал-когорта**  
   Взяли триал в один день → коннект → оплата за 3 и 7 дней vs expired без оплаты. Список «триал без коннекта».

4. **Качество платного трафика**  
   Activation 24ч Direct vs TG vs organic. «Оплатил, не коннектнулся». Если реклама сильно хуже органики — чинить подключение, не бюджет.

5. **Connect-retention**  
   Снова включил VPN на 1 / 7 / 30 день. Paid idle 7д. Не вкладка «Повторные» (там оплата, здесь использование).

6. **Кампании**  
   Уники: старт бота, доступ, коннект, first_pay по `utm_campaign`. CAC считать рядом в Директе.

7. **Рассылки vs holdout**  
   Получил письмо → renew в окне expiry vs ~10% без письма. Revenue на 1000 sent, block rate если пишем событие.

## Не делать в первую очередь

Дубли панели. Heatmap, replay на всю базу, 20 feature-отчётов. CPU нод. CAC «внутри» PostHog без импорта затрат.

## События, без которых доски не встанут

- `landing_view`, `landing_cta_click` + UTM
- `bot_start` (`start_param`)
- `access_granted` / `trial_started` / `trial_expired`
- `vpn_connect_succeeded` / `failed` (+ location, error)
- `vpn_bytes_used` (день или сессия)
- `payment_succeeded` (plan, amount, first vs repeat)
- `subscription_expired` / `renewed`
- `mailing_sent` / `clicked` + campaign_id + флаг holdout

Человек = один `telegram_id`. На person: `yclid`, `ym_uid`, `first_touch_source`, `experiment_pricing`, `current_plan`, `status`, `last_connect_at`.

Лендинг без id — cookie, merge после `/start` (deep link с токеном). Это главный инженерный кусок.
