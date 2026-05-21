# Strategy: Sector Momentum Rotation (template id: `sector-rotation`)

Rotate monthly into the strongest 2 of 9 SPDR sector ETFs. Source:
classic sector momentum (Asness, Faber); works best in sideways /
mildly trending markets.

## Universe
9 SPDR sector ETFs:
`XLK` (tech) · `XLF` (financials) · `XLE` (energy) · `XLV` (healthcare) ·
`XLI` (industrials) · `XLP` (cons. staples) · `XLY` (cons. disc.) ·
`XLU` (utilities) · `XLB` (materials).

## Activation gate
Activate only when **SPY is within ±2% of its 50DMA** (sideways
market — sector dispersion is biggest here). In strong trends, single
broad index outperforms rotation.

## Entry / rebalance
**1st trading day of each month at 09:35 ET**, rank the 9 sectors by
**trailing 3-month return** and hold top 2 equal-weight at 30% each
(60% total deployed, 40% cash buffer). Drop any sector that fell out of
top 2; buy any new entrant.

## Exit
- Monthly rebalance.
- Strategy-level: SPY moves > ±5% from 50DMA → pause (regime change).

## Position sizing
30% per sector × 2 = 60% deployed.

## Daily activity ritual

Even though rebalance is monthly, the strategy provides daily research
content — sector relative strength shifts every day:

```bash
P=/home/storyclaw/.openclaw/workspace-alpaca-us-stock-trader/skills/alpaca-us-stock/dashboard
# Daily Morning Brief — sector ranking refresh
python3 $P/broadcast.py AGENT \
  "板块 3 个月动量排了一下:XLK 领先 (+8.4),XLF / XLV / XLI 紧随,XLP / XLU / XLE 在下半区" \
  --actor "[SectorRotation]"

# Weekly (Wed) — preview of upcoming rebalance if still N days away
python3 $P/broadcast.py AGENT \
  "距月末调仓还有 9 天 —— 当前持仓 XLK / XLF,XLV 在候补,差 1.9 个点" \
  --actor "[SectorRotation]"

# Rebalance day
python3 $P/broadcast.py DECIDE \
  "月度调仓:XLF 跌出 top 2,换 XLV 进来 —— 卖出 XLF 30%,买入 XLV 30%" \
  --actor "[SectorRotation]"
```

## Risk caveats
- Sector ETFs in concentrated baskets (XLE = 25+ energy names, XLF =
  ~70 banks) — strategy implicitly takes on sector concentration risk.
- Lags badly in strongly trending markets where breadth is narrow
  (e.g., 2023 tech-only run). Activation gate is the protection.
- 3-month lookback can chase late-cycle sectors. Consider 6-month for
  a smoother variant if backtests show better.
