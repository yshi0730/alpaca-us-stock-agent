# Strategy: Earnings Drift Rider (template id: `earnings-drift`)

Ride the post-earnings drift on held names that beat expectations.
Source: Bernard & Thomas (1989) PEAD — one of the most-replicated
anomalies in academic finance. Long-only, event-driven, low frequency
but very narrative-rich(每天 earnings 日历都有事可看).

## Universe
**Held names + active watchlist** (don't blind-trade arbitrary
earnings — only ones the agent already knows the fundamentals on).

## Activation gate
Always "active" in the background — it doesn't take a market regime,
it takes individual earnings events. The agent should check the
earnings calendar **every Morning Brief** regardless.

## Entry
For each held / watchlist name with a recent earnings event:
- EPS surprise **> 0** (beat consensus), AND
- Next-day price reaction **> +2%** at close, AND
- No more than 3 concurrent positions from this strategy.

→ Buy **10% of equity** at the day-after-reaction open.

## Exit
- **5 trading day hold**, then market-close exit, OR
- Trailing stop **-3%** from intra-hold high, whichever fires first.

## Position sizing
10% per event × max 3 concurrent = up to 30% deployed.

## Daily activity ritual — this is the broadcast-rich one

The earnings calendar generates **a lot of natural daily content** even
when no entry triggers:

```bash
# Morning Brief — today's earnings calendar (relevant names)
python3 /home/storyclaw/.openclaw/workspace-alpaca-us-stock-trader/skills/alpaca-us-stock/dashboard/broadcast.py \
  AGENT "今日 earnings: NVDA (持仓) AMC · CRM AMC · ORCL BMO · 5 个 watchlist 中无" \
  --actor "[EarningsDrift]"

# After NVDA's release (post-market) — note + assess
python3 /home/storyclaw/.openclaw/workspace-alpaca-us-stock-trader/skills/alpaca-us-stock/dashboard/broadcast.py \
  AGENT "NVDA Q1: 营收 \$26.0B (+87% YoY,beat \$24.6B est) · EPS \$0.61 (beat \$0.57) · 指引上修。AH +6.4%" \
  --actor "[EarningsDrift]" --level done

# Next morning — entry decision
python3 /home/storyclaw/.openclaw/workspace-alpaca-us-stock-trader/skills/alpaca-us-stock/dashboard/broadcast.py \
  DECIDE "NVDA 触发 PEAD 入场:EPS surprise +7%,昨日 AH +6.4% > 2% 阈值。买入 10%" \
  --actor "[EarningsDrift]"

# Days where no held names have earnings — still broadcast the scan
python3 /home/storyclaw/.openclaw/workspace-alpaca-us-stock-trader/skills/alpaca-us-stock/dashboard/broadcast.py \
  AGENT "今日 earnings 日历无相关持仓 / watchlist 公司。下次相关 earnings:NVDA Q2 (8/22)" \
  --actor "[EarningsDrift]"
```

## Risk caveats
- PEAD has degraded since publication — works best on **positive**
  surprises (left-tail / misses no longer show clean drift). Long-only.
- Limiting to held names + watchlist means we miss the bulk of the
  PEAD universe, but it stays interpretable and doesn't chase noise.
  If you want to expand, do it deliberately (whitelist of 30+ names).
- Don't enter on **giant** beats (>15%) — those tend to gap and then
  retrace within a week. Strategy works best on moderate beats (2-8%).
