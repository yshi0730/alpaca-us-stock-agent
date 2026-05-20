"""Strategy lifecycle helper — pairs `strategy_state` writes with broadcast.

Use these subcommands, NOT direct SQL. They guarantee write-contract
Rule 1 (`strategy_state` row) AND the matching `ai_broadcast` narration
in a single call. The dashboard's Active Strategies panel and AI
Broadcast panel will both update on the next render.

    python3 dashboard/strategy.py activate <id> --name "..." --template "..." \\
        --reason "..." [--params '<json>'] [--authorization-level 1]
    python3 dashboard/strategy.py pause   <id> --reason "..."
    python3 dashboard/strategy.py resume  <id> --reason "..."
    python3 dashboard/strategy.py stop    <id> --reason "..."

Examples:
    python3 dashboard/strategy.py activate mag7-momentum \\
        --name "Mag7 Momentum Rotation" --template mag7-momentum \\
        --params '{"k":3,"hold_days":5}' \\
        --reason "SPY > 50DMA · VIX 17 · 适合做趋势"
    python3 dashboard/strategy.py pause mag7-momentum \\
        --reason "日内 DD -2.8% · 接近熔断阈值,先停"
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from broadcast import write_row as broadcast_row  # noqa: E402

AGENT_ID = "alpaca-us-stock-trader"
DB_PATH = Path(os.environ.get(
    "CLAW_SHARED_DB",
    str(Path.home() / ".claw" / "shared" / "shared.db"),
))

INIT_SQL = """
CREATE TABLE IF NOT EXISTS strategy_state (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  name TEXT,
  template TEXT,
  status TEXT NOT NULL DEFAULT 'running',
  authorization_level INTEGER DEFAULT 1,
  params TEXT,
  pnl_cumulative REAL DEFAULT 0,
  pnl_today REAL DEFAULT 0,
  positions_count INTEGER DEFAULT 0,
  last_action TEXT,
  last_action_at TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
"""


def _broadcast(tag: str, msg: str, actor: str, level: str = "info") -> None:
    broadcast_row(tag, msg, actor=actor, level=level)


def _db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.executescript(INIT_SQL)
    return db


def cmd_activate(args: argparse.Namespace) -> int:
    db = _db()
    db.execute(
        "INSERT OR REPLACE INTO strategy_state "
        "(id, agent_id, name, template, status, authorization_level, "
        " params, last_action, last_action_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'running', ?, ?, ?, datetime('now'), datetime('now'))",
        (
            args.id, AGENT_ID, args.name, args.template,
            args.authorization_level, args.params,
            f"activated · {args.reason}",
        ),
    )
    db.commit(); db.close()
    _broadcast(
        "AGENT",
        f"激活策略 {args.name} ({args.template}): {args.reason}",
        actor="[StrategyManager]",
        level="done",
    )
    print(f"✓ activated {args.id} ({args.name})")
    return 0


def cmd_pause(args: argparse.Namespace) -> int:
    db = _db()
    row = db.execute(
        "SELECT name FROM strategy_state WHERE id=? AND agent_id=?",
        (args.id, AGENT_ID),
    ).fetchone()
    if not row:
        print(f"error: strategy {args.id!r} not found", file=sys.stderr)
        db.close(); return 2
    name = row[0] or args.id
    db.execute(
        "UPDATE strategy_state SET status='paused', "
        "last_action=?, last_action_at=datetime('now'), updated_at=datetime('now') "
        "WHERE id=? AND agent_id=?",
        (f"paused · {args.reason}", args.id, AGENT_ID),
    )
    db.commit(); db.close()
    _broadcast(
        "WARN",
        f"暂停策略 {name}: {args.reason}",
        actor="[StrategyManager]",
        level="warn",
    )
    print(f"⏸ paused {args.id}")
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    db = _db()
    row = db.execute(
        "SELECT name FROM strategy_state WHERE id=? AND agent_id=?",
        (args.id, AGENT_ID),
    ).fetchone()
    if not row:
        print(f"error: strategy {args.id!r} not found", file=sys.stderr)
        db.close(); return 2
    name = row[0] or args.id
    db.execute(
        "UPDATE strategy_state SET status='running', "
        "last_action=?, last_action_at=datetime('now'), updated_at=datetime('now') "
        "WHERE id=? AND agent_id=?",
        (f"resumed · {args.reason}", args.id, AGENT_ID),
    )
    db.commit(); db.close()
    _broadcast(
        "AGENT",
        f"恢复策略 {name}: {args.reason}",
        actor="[StrategyManager]",
        level="done",
    )
    print(f"▶ resumed {args.id}")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    db = _db()
    row = db.execute(
        "SELECT name FROM strategy_state WHERE id=? AND agent_id=?",
        (args.id, AGENT_ID),
    ).fetchone()
    if not row:
        print(f"error: strategy {args.id!r} not found", file=sys.stderr)
        db.close(); return 2
    name = row[0] or args.id
    db.execute(
        "UPDATE strategy_state SET status='stopped', "
        "last_action=?, last_action_at=datetime('now'), updated_at=datetime('now') "
        "WHERE id=? AND agent_id=?",
        (f"stopped · {args.reason}", args.id, AGENT_ID),
    )
    db.commit(); db.close()
    _broadcast(
        "AGENT",
        f"停止策略 {name}: {args.reason}",
        actor="[StrategyManager]",
    )
    print(f"⏹ stopped {args.id}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Strategy lifecycle helper — writes strategy_state + broadcasts in one call.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("activate", help="create or re-activate a strategy")
    a.add_argument("id", help="strategy slug, e.g. mag7-momentum")
    a.add_argument("--name", required=True, help="display name")
    a.add_argument("--template", required=True,
                   help="template slug: mag7-momentum / quality-mr / vix-spike / sector-rotation / earnings-drift / custom")
    a.add_argument("--reason", required=True, help="WHY now (one short sentence)")
    a.add_argument("--params", default="{}", help='strategy params JSON (default "{}")')
    a.add_argument("--authorization-level", type=int, default=1,
                   help="0 advisory / 1 semi-auto (default) / 2 full-auto")
    a.set_defaults(fn=cmd_activate)

    for name, fn, help_ in (
        ("pause",  cmd_pause,  "pause a running strategy"),
        ("resume", cmd_resume, "resume a paused strategy"),
        ("stop",   cmd_stop,   "stop a strategy permanently (state=stopped)"),
    ):
        s = sub.add_parser(name, help=help_)
        s.add_argument("id", help="strategy slug")
        s.add_argument("--reason", required=True, help="WHY (one short sentence)")
        s.set_defaults(fn=fn)

    args = p.parse_args()
    # validate params is JSON for activate
    if args.cmd == "activate":
        try:
            json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"error: --params must be valid JSON: {e}", file=sys.stderr)
            return 2
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
