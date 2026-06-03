"""
Investment Simulation Runner
Supports three execution modes:

  --mode morning    (default) All 6 agents. Runs Mon-Fri 9:00 AM ET.
  --mode afternoon  Speculator + Emotional only. Runs Mon-Fri 3:45 PM ET.
  --mode crypto     Speculator crypto positions only. Runs every 4 hours, 24/7.
"""

import sys
import os
import json
import argparse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, BASE_DIR)

from agents.conservative import ConservativeAgent
from agents.passive_indexer import PassiveIndexerAgent
from agents.aggressive_growth import AggressiveGrowthAgent
from agents.speculator import SpeculatorAgent
from agents.value_investor import ValueInvestorAgent
from agents.emotional import EmotionalInvestorAgent
from data.market_data import fetch_market_data, fetch_crypto_data, fetch_fear_greed
from data.news_sentiment import fetch_all_sentiment

HISTORY_FILE       = os.path.join(BASE_DIR, "data", "history.json")
DASHBOARD_DATA_FILE = os.path.join(BASE_DIR, "docs", "data.js")

AGENT_META = {
    "Conservative":      {"color": "#1976D2", "emoji": "🛡️", "strategy": "Bonds, gold, dividend ETFs. Capital preservation."},
    "Passive Indexer":   {"color": "#43A047", "emoji": "📊", "strategy": "100% S&P 500 + Global ETF. Buy and hold forever."},
    "Aggressive Growth": {"color": "#F57C00", "emoji": "🚀", "strategy": "High-growth tech & biotech. Concentrated bets."},
    "Speculator":        {"color": "#E53935", "emoji": "🎰", "strategy": "Crypto, meme stocks, momentum chasing."},
    "Value Investor":    {"color": "#7B1FA2", "emoji": "📖", "strategy": "Buffett-style. Undervalued fundamentals. Low turnover."},
    "Emotional":         {"color": "#FDD835", "emoji": "😱", "strategy": "No strategy. FOMO buys, panic sells."},
}

# Which agents run in each mode
MODE_AGENTS = {
    "morning":   ["Conservative", "Passive Indexer", "Aggressive Growth",
                  "Speculator", "Value Investor", "Emotional"],
    "afternoon": ["Speculator", "Emotional"],
    "crypto":    ["Speculator"],
}

MODE_LABELS = {
    "morning":   "🌅 MORNING RUN — All 6 agents",
    "afternoon": "🌆 AFTERNOON RUN — Speculator + Emotional (pre-close)",
    "crypto":    "🌙 CRYPTO CHECK — Speculator 4-hour cycle",
}


# ── Persistence ───────────────────────────────────────────────────────────

def load_history() -> dict:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"start_date": datetime.now().strftime("%Y-%m-%d"), "days": []}


def save_history(history: dict):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


# ── Dashboard ─────────────────────────────────────────────────────────────

def build_dashboard_data(all_agents, active_agents, history,
                         today_decisions, fear_greed, market_data, mode) -> dict:
    agents_out = {}
    for agent in all_agents:
        p    = agent.portfolio
        meta = AGENT_META.get(agent.name, {})
        total_val = p["total_value"]
        holdings_list = []
        for ticker, h in p.get("holdings", {}).items():
            val = h.get("current_value", h["shares"] * h["avg_cost"])
            holdings_list.append({
                "ticker":           ticker,
                "shares":           round(h["shares"], 4),
                "avg_cost":         round(h["avg_cost"], 2),
                "current_price":    round(h.get("current_price", h["avg_cost"]), 2),
                "current_value":    round(val, 2),
                "allocation_pct":   round(val / total_val * 100, 1) if total_val else 0,
                "unrealized_pnl_pct": round(h.get("unrealized_pnl_pct", 0), 2),
            })
        holdings_list.sort(key=lambda x: x["current_value"], reverse=True)

        agents_out[agent.name] = {
            "name":             agent.name,
            "color":            meta.get("color", "#888"),
            "emoji":            meta.get("emoji", ""),
            "strategy":         meta.get("strategy", ""),
            "schedule":         _agent_schedule_label(agent.name),
            "starting_capital": p["starting_capital"],
            "current_value":    p["total_value"],
            "cash":             round(p["cash"], 2),
            "cash_pct":         round(p["cash"] / total_val * 100, 1) if total_val else 100,
            "return_pct":       p["return_pct"],
            "return_usd":       round(p["total_value"] - p["starting_capital"], 2),
            "max_drawdown":     p.get("max_drawdown", 0),
            "peak_value":       p.get("peak_value", p["starting_capital"]),
            "trade_count":      p.get("trade_count", 0),
            "holdings":         holdings_list,
        }

    raw_sent = market_data.get("sentiment", {})
    dash_sentiment = {
        "market_headlines": raw_sent.get("market_headlines", [])[:10],
        "reddit_wsb":       raw_sent.get("reddit_wsb", [])[:10],
        "reddit_investing": raw_sent.get("reddit_investing", [])[:8],
        "wsb_tickers":      raw_sent.get("wsb_tickers", {}),
        "inv_tickers":      raw_sent.get("inv_tickers", {}),
        "overall_sentiment": raw_sent.get("overall_sentiment", 0),
    }

    return {
        "last_updated":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        "last_run_mode":   mode,
        "start_date":      history["start_date"],
        "days_running":    len(history["days"]),
        "fear_greed":      fear_greed,
        "sentiment":       dash_sentiment,
        "agents":          agents_out,
        "history":         history["days"][-180:],
        "today_decisions": today_decisions,
    }


def _agent_schedule_label(name: str) -> str:
    if name in ("Speculator", "Emotional"):
        if name == "Speculator":
            return "9 AM · 3:45 PM · crypto every 4h"
        return "9 AM · 3:45 PM"
    return "9 AM daily"


def generate_dashboard_js(data: dict):
    os.makedirs(os.path.dirname(DASHBOARD_DATA_FILE), exist_ok=True)
    with open(DASHBOARD_DATA_FILE, "w", encoding="utf-8") as f:
        f.write("// Auto-generated by runner.py — do not edit manually\n")
        f.write(f"const SIMULATION_DATA = {json.dumps(data, indent=2)};\n")


# ── Git push ──────────────────────────────────────────────────────────────

def _git_push_data(label: str):
    import subprocess
    try:
        subprocess.run(
            ["git", "add", "docs/data.js", "data/history.json", "data/portfolios", "data/logs"],
            cwd=BASE_DIR, check=True, capture_output=True,
        )
        changed = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=BASE_DIR, capture_output=True
        )
        if changed.returncode != 0:
            subprocess.run(
                ["git", "commit", "-m", f"sim: {label}"],
                cwd=BASE_DIR, check=True, capture_output=True,
            )
            subprocess.run(["git", "push"], cwd=BASE_DIR, check=True, capture_output=True)
            print("📤 Pushed to GitHub Pages")
        else:
            print("📤 Nothing new to push")
    except Exception as e:
        print(f"⚠️  Git push skipped: {e}")


# ── Console summary ───────────────────────────────────────────────────────

def print_summary(agents):
    print(f"\n{'─'*62}")
    print(f"  {'AGENT':<22} {'VALUE':>10} {'RETURN':>9} {'MAX DD':>8}")
    print(f"{'─'*62}")
    for i, agent in enumerate(sorted(agents, key=lambda a: a.portfolio["total_value"], reverse=True)):
        p     = agent.portfolio
        medal = ["🥇", "🥈", "🥉", " 4.", " 5.", " 6."][min(i, 5)]
        print(f"  {medal} {agent.name:<20} ${p['total_value']:>9,.2f}"
              f"  {p['return_pct']:>+7.2f}%  {p.get('max_drawdown',0):>6.1f}%")
    print(f"{'─'*62}\n")


# ── Agent factory ─────────────────────────────────────────────────────────

def make_agents(names: list) -> list:
    registry = {
        "Conservative":      ConservativeAgent,
        "Passive Indexer":   PassiveIndexerAgent,
        "Aggressive Growth": AggressiveGrowthAgent,
        "Speculator":        SpeculatorAgent,
        "Value Investor":    ValueInvestorAgent,
        "Emotional":         EmotionalInvestorAgent,
    }
    return [registry[n]() for n in names if n in registry]


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Investment Simulation Runner")
    parser.add_argument("--mode", choices=["morning", "afternoon", "crypto"],
                        default="morning", help="Execution mode")
    args = parser.parse_args()
    mode = args.mode

    now = datetime.now()
    print(f"\n{'═'*62}")
    print(f"  {MODE_LABELS[mode]}")
    print(f"  {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*62}\n")

    # ── 1. Fetch data (scope depends on mode) ──────────────────────────
    fear_greed = {"value": 50, "classification": "Neutral"}

    if mode == "crypto":
        print("📡 Fetching crypto prices (fast)...")
        try:
            market_data = fetch_crypto_data()
        except Exception as e:
            print(f"  FATAL: {e}"); sys.exit(1)

        print("😨 Fetching Fear & Greed...")
        try:
            fear_greed = fetch_fear_greed()
            print(f"  F&G: {fear_greed['value']:.0f} — {fear_greed['classification']}")
        except Exception as e:
            print(f"  F&G unavailable ({e})")
        market_data["fear_greed"] = fear_greed

        print("📰 Fetching crypto sentiment (Reddit + news)...")
        try:
            sentiment = fetch_all_sentiment()
            market_data["sentiment"] = sentiment
        except Exception as e:
            print(f"  Sentiment error ({e})")
            market_data["sentiment"] = {}

    else:
        # morning or afternoon — full market data
        print("📡 Fetching full market data...")
        try:
            skip_fundamentals = (mode == "afternoon")
            market_data = fetch_market_data(include_fundamentals=not skip_fundamentals)
        except Exception as e:
            print(f"  FATAL: {e}"); sys.exit(1)

        print("😨 Fetching Fear & Greed...")
        try:
            fear_greed = fetch_fear_greed()
            print(f"  F&G: {fear_greed['value']:.0f} — {fear_greed['classification']}")
        except Exception as e:
            print(f"  F&G unavailable ({e}), using Neutral=50")
        market_data["fear_greed"] = fear_greed

        if mode == "morning":
            print("📰 Fetching news & sentiment...")
            try:
                sentiment = fetch_all_sentiment()
                market_data["sentiment"] = sentiment
                wsb_top = sorted(sentiment.get("wsb_tickers", {}).items(),
                                 key=lambda x: x[1], reverse=True)[:5]
                wsb_str = ", ".join(f"{t}×{c}" for t, c in wsb_top) or "none"
                print(f"  Sentiment: {sentiment['overall_sentiment']:+.2f}  |  WSB: {wsb_str}")
            except Exception as e:
                print(f"  Sentiment error ({e})")
                market_data["sentiment"] = {}
        else:
            # afternoon: reuse morning sentiment if it was saved
            market_data["sentiment"] = _load_cached_sentiment()

    # ── 2. Load ALL agents for portfolio value tracking ─────────────────
    all_agent_names  = MODE_AGENTS["morning"]
    active_agent_names = MODE_AGENTS[mode]

    all_agents    = make_agents(all_agent_names)
    active_agents = [a for a in all_agents if a.name in active_agent_names]

    # Update every agent's portfolio value with current prices
    for agent in all_agents:
        try:
            agent.update_portfolio_value(market_data["prices"])
        except Exception:
            pass

    # ── 3. Run active agents ────────────────────────────────────────────
    today_decisions = []
    for agent in active_agents:
        print(f"\n▶  Running {agent.name} [{mode}]...")
        try:
            if mode == "crypto":
                decisions = agent.run_crypto_only(market_data, fear_greed)
            else:
                decisions = agent.run(market_data, fear_greed)

            agent.update_portfolio_value(market_data["prices"])
            agent.log_decision(decisions)
            agent.save_portfolio()

            today_decisions.append({
                "agent":           agent.name,
                "color":           AGENT_META.get(agent.name, {}).get("color", "#888"),
                "mode":            mode,
                "time":            now.strftime("%H:%M"),
                "decisions":       decisions,
                "portfolio_value": agent.portfolio["total_value"],
                "return_pct":      agent.portfolio["return_pct"],
            })

            non_hold = [d for d in decisions if d.get("action") != "HOLD"]
            if non_hold:
                for d in non_hold[:3]:
                    print(f"   {d['action']}: {d.get('ticker','')} — ${d.get('value',0):,.0f}")
            else:
                print(f"   HOLD — ${agent.portfolio['total_value']:,.2f}"
                      f" ({agent.portfolio['return_pct']:+.2f}%)")

        except Exception as e:
            import traceback
            print(f"   ERROR in {agent.name}: {e}")
            traceback.print_exc()

    # ── 4. Update history (morning run owns the daily snapshot) ─────────
    history  = load_history()
    today_str = now.strftime("%Y-%m-%d")

    if mode == "morning":
        history["days"] = [d for d in history["days"] if d["date"] != today_str]
        history["days"].append({
            "date":       today_str,
            "values":     {a.name: a.portfolio["total_value"] for a in all_agents},
            "returns":    {a.name: a.portfolio["return_pct"]  for a in all_agents},
            "fear_greed": fear_greed["value"],
        })
        save_history(history)
    elif mode in ("afternoon", "crypto"):
        # Update intraday values on today's snapshot without adding a new row
        if history["days"] and history["days"][-1]["date"] == today_str:
            snap = history["days"][-1]
            for a in active_agents:
                snap["values"][a.name]  = a.portfolio["total_value"]
                snap["returns"][a.name] = a.portfolio["return_pct"]
            save_history(history)

    # ── 5. Merge today's new decisions into dashboard decisions list ─────
    merged_decisions = _merge_decisions(today_decisions, mode, today_str)

    # ── 6. Generate dashboard ────────────────────────────────────────────
    dash_data = build_dashboard_data(
        all_agents, active_agents, history,
        merged_decisions, fear_greed, market_data, mode,
    )
    generate_dashboard_js(dash_data)

    # ── 7. Print summary + push ──────────────────────────────────────────
    print_summary(all_agents)
    print(f"✅ Dashboard updated  mode={mode}  day={len(history['days'])}")
    label = f"{mode} update {today_str} {now.strftime('%H:%M')}"
    _git_push_data(label)


# ── Helpers ───────────────────────────────────────────────────────────────

def _load_cached_sentiment() -> dict:
    """Load sentiment saved by the morning run (avoids redundant API calls)."""
    path = os.path.join(BASE_DIR, "data", "sentiment_cache.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_sentiment_cache(sentiment: dict):
    path = os.path.join(BASE_DIR, "data", "sentiment_cache.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(sentiment, f)


def _merge_decisions(new_decisions: list, mode: str, today_str: str) -> list:
    """
    Keep a rolling decisions log for today that accumulates across all 3 runs.
    Stored in data/today_decisions.json, reset each morning.
    """
    path = os.path.join(BASE_DIR, "data", "today_decisions.json")

    if mode == "morning":
        # Reset on morning run
        combined = new_decisions
    else:
        try:
            with open(path) as f:
                saved = json.load(f)
            if saved.get("date") == today_str:
                combined = saved.get("decisions", []) + new_decisions
            else:
                combined = new_decisions
        except Exception:
            combined = new_decisions

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"date": today_str, "decisions": combined}, f)

    return combined


if __name__ == "__main__":
    main()
