from .base_agent import BaseAgent

# Target allocation (cash reserve ≈ 10%)
TARGETS = {
    "BND":  0.35,   # Total bond market
    "GLD":  0.20,   # Gold
    "SCHD": 0.25,   # Dividend ETF
    "VIG":  0.10,   # Dividend growth ETF
}
REBALANCE_THRESHOLD = 0.04

# Macro keywords that concern a conservative investor
DANGER_MACRO = ["rate hike", "inflation", "recession", "default", "crisis", "stagflation"]
SAFE_MACRO   = ["rate cut", "soft landing", "disinflation", "employment strong", "gdp growth"]


def _macro_signal(sentiment: dict) -> tuple[str, str]:
    """Returns ('danger'|'safe'|'neutral', description)."""
    headlines = sentiment.get("macro_headlines", [])
    if not headlines:
        return "neutral", "No macro headlines today."

    danger_count = 0
    safe_count = 0
    titles = []
    for h in headlines[:6]:
        t = h.get("title", "").lower()
        titles.append(h.get("title", ""))
        for kw in DANGER_MACRO:
            if kw in t:
                danger_count += 1
                break
        for kw in SAFE_MACRO:
            if kw in t:
                safe_count += 1
                break

    if danger_count >= 2:
        return "danger", f"Macro risk detected in {danger_count} headlines: '{titles[0][:60]}...'"
    if safe_count >= 2:
        return "safe", f"Positive macro backdrop: '{titles[0][:60]}'"
    return "neutral", f"{len(headlines)} macro headline(s) — mixed signals."


class ConservativeAgent(BaseAgent):
    def __init__(self):
        super().__init__("Conservative")

    def run(self, market_data: dict, fear_greed: dict) -> list:
        prices     = market_data["prices"]
        sentiment  = market_data.get("sentiment", {})
        fg         = fear_greed.get("value", 50)
        total      = self.portfolio["total_value"]
        decisions  = []

        macro_sig, macro_desc = _macro_signal(sentiment)

        # ── Rebalance toward targets ──────────────────────────────────────
        for ticker, target_pct in TARGETS.items():
            price = prices.get(ticker)
            if not price:
                continue
            current_val = 0.0
            if ticker in self.portfolio["holdings"]:
                current_val = self.portfolio["holdings"][ticker]["shares"] * price
            target_val  = total * target_pct
            deviation   = (target_val - current_val) / total

            if deviation > REBALANCE_THRESHOLD:
                buy_amount = min(target_val - current_val, self.portfolio["cash"] * 0.95)
                d = self.buy(
                    ticker, buy_amount, price,
                    f"Rebalancing: {ticker} is {deviation*100:.1f}% below {target_pct*100:.0f}% target. "
                    f"Macro: {macro_desc}"
                )
                if d:
                    decisions.append(d)

            elif deviation < -REBALANCE_THRESHOLD:
                sell_frac = min(abs(deviation) / (current_val / total) * 0.5, 0.40) * 100
                d = self.sell(
                    ticker, sell_frac, price,
                    f"Rebalancing: {ticker} overweight by {abs(deviation)*100:.1f}%. Trimming to target."
                )
                if d:
                    decisions.append(d)

        # ── Macro danger → raise cash buffer ─────────────────────────────
        if macro_sig == "danger" and self.portfolio["cash"] / total < 0.12:
            for ticker in ["SCHD", "VIG"]:
                if ticker in self.portfolio["holdings"]:
                    d = self.sell(
                        ticker, 8, prices.get(ticker, 1),
                        f"MACRO RISK: {macro_desc} — raising cash buffer as defensive move. "
                        f"Fear & Greed: {fg:.0f}."
                    )
                    if d:
                        decisions.append(d)
                    break

        # ── Extreme greed in market → reduce equity exposure ──────────────
        if fg > 82 and not any(d["action"] == "SELL" for d in decisions):
            for ticker in ["SCHD", "VIG"]:
                if ticker in self.portfolio["holdings"]:
                    d = self.sell(
                        ticker, 6, prices.get(ticker, 1),
                        f"F&G at {fg:.0f} (Extreme Greed) — trimming equity, increasing safety margin. "
                        f"{macro_desc}"
                    )
                    if d:
                        decisions.append(d)
                    break

        if not decisions:
            yfnews = sentiment.get("ticker_news", {})
            spy_latest = (yfnews.get("SPY") or [{}])[0].get("title", "no recent news")
            decisions.append({
                "action": "HOLD",
                "justification": (
                    f"All positions within {REBALANCE_THRESHOLD*100:.0f}% of targets. "
                    f"Macro: {macro_desc} "
                    f"F&G={fg:.0f}. Latest SPY headline: '{spy_latest[:80]}'. "
                    f"Conservative strategy: ignore noise, stay the course."
                ),
            })

        return decisions
