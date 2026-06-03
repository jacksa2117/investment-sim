from .base_agent import BaseAgent

TARGETS = {"SPY": 0.70, "VT": 0.30}


class PassiveIndexerAgent(BaseAgent):
    def __init__(self):
        super().__init__("Passive Indexer")

    def run(self, market_data: dict, fear_greed: dict) -> list:
        prices    = market_data["prices"]
        sentiment = market_data.get("sentiment", {})
        decisions = []

        # Summarise what news exists — then explicitly ignore it
        headlines = sentiment.get("market_headlines", [])
        wsb_top = sorted(
            sentiment.get("wsb_tickers", {}).items(),
            key=lambda x: x[1], reverse=True
        )[:3]
        wsb_str = ", ".join(f"${t}" for t, _ in wsb_top) if wsb_top else "nothing notable"
        fg = fear_greed.get("value", 50)

        if not self.portfolio["holdings"]:
            # Day 1: buy and lock in allocation forever
            for ticker, pct in TARGETS.items():
                price = prices.get(ticker)
                if not price:
                    continue
                d = self.buy(
                    ticker, self.portfolio["cash"] * pct, price,
                    f"Initial allocation: {pct*100:.0f}% in {ticker}. "
                    f"Buy-and-hold forever. Market timing is a loser's game. "
                    f"Ignoring {len(headlines)} headlines and WSB noise ({wsb_str})."
                )
                if d:
                    decisions.append(d)
        else:
            total = self.portfolio["total_value"]
            spy_v = 0
            vt_v  = 0
            if "SPY" in self.portfolio["holdings"]:
                spy_v = self.portfolio["holdings"]["SPY"]["shares"] * prices.get("SPY", 1)
            if "VT" in self.portfolio["holdings"]:
                vt_v = self.portfolio["holdings"]["VT"]["shares"] * prices.get("VT", 1)

            # Passive indexer explicitly does NOT react to news or F&G
            headline_titles = " | ".join(h["title"][:40] for h in headlines[:3]) if headlines else "none"
            decisions.append({
                "action": "HOLD",
                "justification": (
                    f"Zero activity. News ignored: '{headline_titles}'. "
                    f"WSB buzz: {wsb_str}. F&G={fg:.0f} — irrelevant. "
                    f"SPY={spy_v/total*100:.1f}%, VT={vt_v/total*100:.1f}%. "
                    f"Academic evidence: 90%+ of active managers underperform over 10 years. "
                    f"Portfolio: ${total:,.2f}."
                ),
            })

        return decisions
