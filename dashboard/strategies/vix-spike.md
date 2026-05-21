# Strategy: VIX Spike Buyer (template id: `vix-spike`)

Buy SPY into panic. Single-asset, event-driven, dormant most of the
year. Source: Whaley (2009); broadly used as "fear-greed" regime tilt.

## Universe
`SPY` (single asset).

## Activation gate
Strategy is permanently "active" but only **fires entries** when both:
- **VIX > 25** (panic regime), AND
- SPY dropped **≥3% over the last 2 trading days** (confirming the
  panic is in spot, not just expected forward vol).

## Entry
Single 20% slug into SPY at next open (`--type market`).
Max 1 concurrent position from this strategy.

## Exit
- VIX **< 20** (panic over) → sell, OR
- **+5% gain** from entry → sell (take profit; mean reversion captured).
- Hard stop **-4%** (rare — would mean panic kept extending).

## Position sizing
Single 20% slug. No averaging in.

## Daily activity ritual

This strategy spends most days waiting. The Morning Brief and Hourly
Pulse should still broadcast VIX state — that's the visible "I'm
watching for the regime":

```bash
# Morning Brief — VIX state classification
python3 /home/storyclaw/.openclaw/workspace-alpaca-us-stock-trader/skills/alpaca-us-stock/dashboard/broadcast.py \
  AGENT "VIX 17.4 (低波动区,< 25 触发阈值) · SPY 5d 区间 +0.8% · 等待" \
  --actor "[VIXSpike]"
# Hourly Pulse — only when VIX shifts state class
python3 /home/storyclaw/.openclaw/workspace-alpaca-us-stock-trader/skills/alpaca-us-stock/dashboard/broadcast.py \
  WARN "VIX 跳到 22.8 (+18% within 30min),逼近 25 触发线" \
  --actor "[VIXSpike]" --level warn
# Trigger
python3 /home/storyclaw/.openclaw/workspace-alpaca-us-stock-trader/skills/alpaca-us-stock/dashboard/broadcast.py \
  DECIDE "触发条件全满足:VIX 28.4 + SPY 2d -3.6%。买入 SPY 20% 仓位" \
  --actor "[VIXSpike]"
```

## Risk caveats
- **NEVER use VIX short instruments** (XIV/SVXY/VXX short) — 2018-02-05
  "Volmageddon" wiped XIV out overnight (-96% in a single session).
  This strategy is **only on the equity side** (long SPY).
- Confirm "panic in spot" with the 2-day drop check — otherwise can
  trigger on isolated VIX vol-of-vol without a real equity dip.
- The +5% take-profit is conservative; in 2020/03 a held position
  would have +30% if held longer. Optionally widen on user request.
