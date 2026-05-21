# Strategy: Quality Mean-Reversion (template id: `quality-mr`)

Buy high-quality large-caps when they temporarily oversell in a
downtrending market. Quality picks WHO; mean-reversion picks WHEN.

## Universe
10 high-ROE large caps:
`AAPL, MSFT, GOOGL, META, V, MA, JPM, UNH, COST, LLY`.

## Activation gate
Activate only when **SPY is in confirmed drawdown**: SPY is **below
50DMA** AND down **≥5% from its 60-day high**. In normal markets, this
strategy sits dormant.

## Entry
For each name in the universe, **buy 10% of equity** when:
- RSI(14) **< 30** (oversold), AND
- Price **< 50DMA** (confirming the dip is real, not a head-fake), AND
- Less than 4 positions from this strategy currently open.

## Exit
- RSI(14) **> 50** → sell.
- Hard stop **-5%** from entry.
- Strategy-level: SPY reclaims 50DMA → close all and pause.

## Position sizing
10% per name; max 4 concurrent → up to 40% deployed.

## Daily activity ritual

Every weekday Morning Brief, scan all 10 names and broadcast:

```bash
# 1 row per name approaching threshold
python3 /home/storyclaw/.openclaw/workspace-alpaca-us-stock-trader/skills/alpaca-us-stock/dashboard/broadcast.py \
  AGENT "AAPL RSI 34.2 (阈值 30,接近) · 价 $184.20 < 50DMA $189.10" \
  --actor "[QualityMR-Scan]"
# summary row at the end
python3 /home/storyclaw/.openclaw/workspace-alpaca-us-stock-trader/skills/alpaca-us-stock/dashboard/broadcast.py \
  AGENT "QualityMR 扫描完成:0 触发 / 3 接近阈值 / 7 中性" \
  --actor "[QualityMR-Scan]" --level done
```

For HELD positions, also broadcast RSI progress toward exit threshold:

```bash
python3 /home/storyclaw/.openclaw/workspace-alpaca-us-stock-trader/skills/alpaca-us-stock/dashboard/broadcast.py \
  AGENT "已持 MSFT (entry RSI 28),当前 RSI 41.5,接近 exit 50" \
  --actor "[QualityMR]"
```

## Risk caveats
- Catching falling knives if regime changes (bear market → entries pile
  up at lower lows). The -5% hard stop and SPY-50DMA reclaim exit are
  the only protections.
- 10 names × 10% sizing = up to 40% in correlated tech/finance/health
  largecaps in a crisis. Don't let it concentrate.
