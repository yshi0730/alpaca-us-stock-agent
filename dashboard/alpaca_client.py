"""Alpaca REST client for the trading-desk dashboard + the agent.

Originally read-only for dashboard renders (account / clock / positions /
portfolio history / activities / bars). It now also provides the
**write methods the agent uses to place and cancel orders** —
`place_order`, `cancel_order`, `get_order` — so the agent never has to
hand-roll an `httpx.post` to `/v2/orders`. Use these; do NOT bypass.

Read paths memoize for `cache_ttl` seconds. Write paths never cache.
The dashboard renderer still only calls reads — `render.py` is a
separate process and must remain side-effect-free.

Free / paper Alpaca accounts only get the IEX market-data feed (15-min
delayed); bar requests therefore set `feed=iex`. **Paper-account
caveat for `get_bars`:** without an explicit `start`, the IEX feed
returns at most ~1 bar. Always pass a `start` (e.g. `start="2025-01-01"`)
when you actually want a series.

Order-flow pairs with the write contract in `dashboard/SCHEMA.md`:
  1. generate `client_order_id` (e.g. `f"alpaca-{strategy_id}-{uuid8}"`)
  2. INSERT `trade_reasoning` row with the WHY (before the order)
  3. `place_order(..., client_order_id=that_id)`
  4. UPDATE `trade_reasoning SET broker_order_id=?, executed_at=?,
     price=<fill> WHERE client_order_id=?` once the fill confirms.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx

TRADING_PAPER = "https://paper-api.alpaca.markets"
TRADING_LIVE = "https://api.alpaca.markets"
DATA_BASE = "https://data.alpaca.markets"


class AlpacaError(RuntimeError):
    def __init__(self, status: int, body: str, endpoint: str):
        super().__init__(f"Alpaca {endpoint} -> HTTP {status}: {body[:300]}")
        self.status = status
        self.body = body
        self.endpoint = endpoint


class AlpacaClient:
    def __init__(
        self,
        key: str,
        secret: str,
        paper: bool = True,
        cache_ttl: float = 5.0,
        timeout: float = 12.0,
    ):
        if not key or not secret:
            raise ValueError("Alpaca key/secret required")
        self.paper = paper
        self.trading_base = TRADING_PAPER if paper else TRADING_LIVE
        self.data_base = DATA_BASE
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "APCA-API-KEY-ID": key,
                "APCA-API-SECRET-KEY": secret,
                "accept": "application/json",
            },
        )

    # ── internals ──────────────────────────────────────────────────
    def _get(
        self,
        base: str,
        path: str,
        params: Optional[dict] = None,
        *,
        cache: bool = True,
    ) -> Any:
        ckey = f"{base}{path}?{sorted((params or {}).items())}"
        if cache and ckey in self._cache:
            ts, val = self._cache[ckey]
            if time.time() - ts < self._cache_ttl:
                return val
        resp = self._client.get(base + path, params=params)
        if resp.status_code != 200:
            raise AlpacaError(resp.status_code, resp.text, path)
        data = resp.json()
        if cache:
            self._cache[ckey] = (time.time(), data)
        return data

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AlpacaClient":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # ── trading API ────────────────────────────────────────────────
    def get_clock(self) -> dict:
        """{timestamp, is_open, next_open, next_close}"""
        return self._get(self.trading_base, "/v2/clock")

    def get_account(self) -> dict:
        return self._get(self.trading_base, "/v2/account")

    def get_positions(self) -> list[dict]:
        return self._get(self.trading_base, "/v2/positions")

    def get_portfolio_history(
        self,
        period: str = "1A",
        timeframe: str = "1D",
        extended_hours: bool = False,
    ) -> dict:
        """{timestamp[], equity[], profit_loss[], profit_loss_pct[],
        base_value, timeframe}"""
        return self._get(
            self.trading_base,
            "/v2/account/portfolio/history",
            {
                "period": period,
                "timeframe": timeframe,
                "extended_hours": str(extended_hours).lower(),
            },
        )

    def get_activities(
        self,
        activity_types: Optional[str] = None,
        page_size: int = 100,
    ) -> list[dict]:
        """Account activities (FILL, DIV, ...). Not cached — feed needs
        freshest data. activity_types is a comma list, e.g. 'FILL'."""
        params: dict = {"page_size": page_size}
        if activity_types:
            params["activity_types"] = activity_types
        return self._get(
            self.trading_base, "/v2/account/activities", params, cache=False
        )

    # ── market data API ────────────────────────────────────────────
    def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Daily bars for one symbol. Used for the SPY benchmark line
        and for any strategy that needs price history.

        `start` / `end` are RFC-3339 or `YYYY-MM-DD` strings.

        ⚠ **Paper-account quirk:** on paper / free Alpaca the IEX feed
        returns at most ~1 bar when `start` is omitted — silently. If
        you actually want a series, **always pass `start`** (e.g.
        `start="2025-01-01"` for YTD). The dashboard renderer always
        supplies one. New ad-hoc strategy scripts often hit this trap
        first time; checking `len(bars) <= 1` is the fastest diagnosis."""
        params: dict = {
            "symbols": symbol,
            "timeframe": timeframe,
            "limit": limit,
            "adjustment": "all",
            "feed": "iex",
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        data = self._get(self.data_base, "/v2/stocks/bars", params)
        return data.get("bars", {}).get(symbol, [])

    # ── order writes (place / cancel / status) ────────────────────
    def place_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        type_: str = "market",
        time_in_force: str = "day",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
        extended_hours: bool = False,
    ) -> dict:
        """Submit a single-leg equity order. Returns the broker's order
        record (`id`, `client_order_id`, `status`, `submitted_at`, …).

        The **canonical write path** — use this, not raw `httpx.post`.
        Pairs with `dashboard/SCHEMA.md` write-contract rule 2:

            cid = f"alpaca-{strategy_id}-{uuid.uuid4().hex[:8]}"
            db.execute("INSERT INTO trade_reasoning(...) VALUES(...)",
                       (cid, ..., reasoning, ...))     # WHY first
            r = ac.place_order("NVDA", 5, "buy", client_order_id=cid)
            db.execute("UPDATE trade_reasoning SET broker_order_id=? "
                       "WHERE client_order_id=?", (r["id"], cid))

        Args:
          symbol: e.g. "NVDA"
          qty: positive number; direction comes from `side`.
          side: "buy" | "sell"
          type_: "market" | "limit" | "stop" | "stop_limit"
          time_in_force: "day" | "gtc" | "ioc" | "fok" | "opg" | "cls"
          limit_price: required when type_ ∈ {"limit","stop_limit"}
          stop_price:  required when type_ ∈ {"stop","stop_limit"}
          client_order_id: ALWAYS pass one — that's how the dashboard
              JOINs the broker order back to your reasoning row. Alpaca
              enforces uniqueness, so include a uuid fragment.
          extended_hours: pre/post-market (limit orders only).

        Does NOT enforce risk guardrails — set them upstream
        (single-position cap, daily-loss limit, paper-first, etc.) per
        SOUL.md. Raises `AlpacaError` on non-2xx.
        """
        side = side.lower().strip()
        if side not in {"buy", "sell"}:
            raise ValueError(f"side must be buy/sell, got {side!r}")
        type_ = type_.lower().strip()
        if type_ not in {"market", "limit", "stop", "stop_limit"}:
            raise ValueError(
                f"type_ must be market/limit/stop/stop_limit, got {type_!r}"
            )
        if type_ in {"limit", "stop_limit"} and limit_price is None:
            raise ValueError(f"limit_price required for type_={type_!r}")
        if type_ in {"stop", "stop_limit"} and stop_price is None:
            raise ValueError(f"stop_price required for type_={type_!r}")
        body: dict = {
            "symbol": symbol.upper().strip(),
            "qty": str(qty),
            "side": side,
            "type": type_,
            "time_in_force": time_in_force.lower().strip(),
        }
        if limit_price is not None:
            body["limit_price"] = str(limit_price)
        if stop_price is not None:
            body["stop_price"] = str(stop_price)
        if client_order_id:
            body["client_order_id"] = client_order_id
        if extended_hours:
            body["extended_hours"] = True
        resp = self._client.post(self.trading_base + "/v2/orders", json=body)
        if resp.status_code not in {200, 201}:
            raise AlpacaError(resp.status_code, resp.text, "/v2/orders")
        return resp.json()

    def cancel_order(self, order_id: str) -> None:
        """Cancel a working order by broker `id` (NOT `client_order_id`).
        Returns None on success (Alpaca returns 204). Already-filled
        or unknown orders raise `AlpacaError`(422). For "cancel all"
        scenarios place separate cancel_order calls — there is no
        bulk-cancel here on purpose (see SOUL.md "Never execute
        'cancel all' without strong confirmation")."""
        resp = self._client.delete(f"{self.trading_base}/v2/orders/{order_id}")
        if resp.status_code not in {200, 204}:
            raise AlpacaError(resp.status_code, resp.text, f"/v2/orders/{order_id}")

    def get_order(
        self,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> dict:
        """Look up an order by broker `id` OR `client_order_id`. Useful
        for status polling after `place_order` (e.g. wait for fill).
        Pass exactly one identifier."""
        if (order_id and client_order_id) or (not order_id and not client_order_id):
            raise ValueError("pass exactly one of order_id / client_order_id")
        if order_id:
            return self._get(
                self.trading_base, f"/v2/orders/{order_id}", cache=False
            )
        return self._get(
            self.trading_base,
            "/v2/orders:by_client_order_id",
            {"client_order_id": client_order_id},
            cache=False,
        )

    # ── normalized convenience views ───────────────────────────────
    def account_snapshot(self) -> dict:
        """Flat, typed view the dashboard hero KPIs consume directly."""
        a = self.get_account()
        equity = float(a.get("equity", 0) or 0)
        last_equity = float(a.get("last_equity", 0) or 0)
        day_pl = equity - last_equity
        day_pl_pct = (day_pl / last_equity * 100) if last_equity else 0.0
        return {
            "account_number": a.get("account_number"),
            "status": a.get("status"),
            "currency": a.get("currency", "USD"),
            "equity": equity,
            "last_equity": last_equity,
            "cash": float(a.get("cash", 0) or 0),
            "buying_power": float(a.get("buying_power", 0) or 0),
            "portfolio_value": float(a.get("portfolio_value", equity) or equity),
            "day_pl": day_pl,
            "day_pl_pct": day_pl_pct,
            "pattern_day_trader": bool(a.get("pattern_day_trader", False)),
            "daytrade_count": int(a.get("daytrade_count", 0) or 0),
            "is_paper": self.paper,
        }

    def positions_normalized(self) -> list[dict]:
        """Positions with numeric fields parsed (Alpaca returns strings)."""
        out = []
        for p in self.get_positions():
            qty = float(p.get("qty", 0) or 0)
            avg = float(p.get("avg_entry_price", 0) or 0)
            mv = float(p.get("market_value", 0) or 0)
            upl = float(p.get("unrealized_pl", 0) or 0)
            uplpc = float(p.get("unrealized_plpc", 0) or 0) * 100
            cur = float(p.get("current_price", 0) or 0)
            out.append(
                {
                    "symbol": p.get("symbol"),
                    "qty": qty,
                    "avg_entry_price": avg,
                    "current_price": cur,
                    "market_value": mv,
                    "unrealized_pl": upl,
                    "unrealized_pl_pct": uplpc,
                    "side": p.get("side", "long"),
                    "asset_class": p.get("asset_class", "us_equity"),
                }
            )
        return out
