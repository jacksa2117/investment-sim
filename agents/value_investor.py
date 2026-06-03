from .base_agent import BaseAgent
from datetime import datetime

UNIVERSE       = ["BRK-B", "JNJ", "KO", "PG", "JPM", "BAC", "CVX", "WMT", "MCD", "ABBV"]
MAX_POS        = 0.20
MIN_POS        = 0.08
PE_BUY         = 18
PE_SELL        = 28
NOISE_SOURCES  = {"wsb_tickers", "reddit_wsb"}   # Value investor ignores Reddit


def _fundamental_news_signal(ticker: str, sentiment: dict) -> tuple[float, str]:
    """
    Value investor only cares about fundamental news (earnings, P/E, dividends).
    Returns (sentiment_score, headline).
    Ignores Reddit / momentum noise.
    """
    news = sentiment.get("ticker_news", {}).get(ticker, [])
    fundamental_keywords = [
        "earnings", "revenue", "profit", "dividend", "eps", "guidance",
        "quarterly", "annual", "financial", "results", "beat", "miss",
        "cashflow", "balance sheet", "debt", "upgraded", "downgraded",
    ]
    relevant = []
    for art in news:
        t = art["title"].lower()
        if any(kw in t for kw in fundamental_keywords):
            relevant.append(art)
    if relevant:
        avg = sum(a["sentiment"] for a in relevant) / len(relevant)
        return avg, relevant[0]["title"][:70]
    return 0.0, "no fundamental news"


class ValueInvestorAgent(BaseAgent):
    def __init__(self):
        super().__init__("Value Investor")

    def _should_check(self) -> bool:
        return self.portfolio.get("last_check_week") != datetime.now().strftime("%Y-%W")

    def run(self, market_data: dict, fear_greed: dict) -> list:
        prices       = market_data["prices"]
        fundamentals = market_data.get("fundamentals", {})
        sentiment    = market_data.get("sentiment", {})
        decisions    = []
        total        = self.portfolio["total_value"]
        fg           = fear_greed.get("value", 50)

        # Value investor checks weekly — ignores daily noise
        if not self._should_check() and self.portfolio["holdings"]:
            # Still log what's being ignored
            wsb_hot = sorted(sentiment.get("wsb_tickers", {}).items(),
                             key=lambda x: x[1], reverse=True)[:3]
            wsb_str = ", ".join(f"${t}×{c}" for t, c in wsb_hot) if wsb_hot else "nothing"
            decisions.append({
                "action": "HOLD",
                "justification": (
                    f"Already analyzed fundamentals this week — checking again next week. "
                    f"Low turnover is a feature. "
                    f"Reddit buzzing about: {wsb_str} — IGNORED. "
                    f"Portfolio: ${total:,.2f}."
                ),
            })
            return decisions

        # ── Sell overvalued positions ─────────────────────────────────────
        for ticker in list(self.portfolio["holdings"].keys()):
            price = prices.get(ticker)
            if not price:
                continue
            f    = fundamentals.get(ticker, {})
            pe   = f.get("pe")
            h    = self.portfolio["holdings"][ticker]
            gain = (price / h["avg_cost"] - 1) * 100
            sent_score, sent_headline = _fundamental_news_signal(ticker, sentiment)

            if pe and pe > PE_SELL:
                d = self.sell(
                    ticker, 100, price,
                    f"SELL: {ticker} P/E={pe:.1f} > sell threshold {PE_SELL}. "
                    f"Mr. Market is being generous. Realized gain: {gain:.1f}%. "
                    f"Fundamental news: '{sent_headline}'."
                )
                if d:
                    decisions.append(d)

        # ── Buy undervalued positions ─────────────────────────────────────
        for ticker in UNIVERSE:
            price = prices.get(ticker)
            if not price:
                continue
            f        = fundamentals.get(ticker, {})
            pe       = f.get("pe")
            pb       = f.get("pb")
            fcf      = f.get("free_cashflow")
            dte      = f.get("debt_to_equity")
            sent_score, sent_headline = _fundamental_news_signal(ticker, sentiment)

            is_cheap      = pe and pe < PE_BUY
            good_pb       = pb is None or pb < 5
            positive_fcf  = fcf is None or fcf > 0
            ok_debt       = dte is None or dte < 150

            # Negative fundamental news = extra buying opportunity
            is_opportunity = is_cheap or (sent_score < -0.3 and pe and pe < PE_BUY + 5)

            if is_opportunity and good_pb and positive_fcf and ok_debt:
                current_val = 0
                if ticker in self.portfolio["holdings"]:
                    current_val = self.portfolio["holdings"][ticker]["shares"] * price
                if current_val / total < MIN_POS and self.portfolio["cash"] > 200:
                    buy_amt = min(self.portfolio["cash"] * 0.25, total * MAX_POS - current_val)
                    pe_str  = f"P/E={pe:.1f}" if pe else "compelling value"
                    pb_str  = f", P/B={pb:.1f}" if pb else ""
                    opp_str = " (market overreacting to negative news — buying opportunity)" if sent_score < -0.3 else ""
                    d = self.buy(
                        ticker, buy_amt, price,
                        f"Value opportunity: {ticker}. {pe_str}{pb_str}{opp_str}. "
                        f"FCF positive, debt manageable. News: '{sent_headline}'. "
                        f"F&G={fg:.0f} — irrelevant to intrinsic value. "
                        f"Reddit mentions: IGNORED."
                    )
                    if d:
                        decisions.append(d)

        # Day-1 fallback: buy top 5 value names equally
        if not self.portfolio["holdings"] and not decisions:
            for ticker in UNIVERSE[:5]:
                price = prices.get(ticker)
                if price:
                    f       = fundamentals.get(ticker, {})
                    pe_str  = f"P/E={f['pe']:.1f}" if f.get("pe") else ""
                    d = self.buy(
                        ticker, self.portfolio["cash"] * 0.18, price,
                        f"Initial value portfolio: {ticker}. {pe_str}. "
                        f"Durable competitive advantage. Buying and waiting."
                    )
                    if d:
                        decisions.append(d)

        self.portfolio["last_check_week"] = datetime.now().strftime("%Y-%W")

        if not decisions:
            holdings_str = ", ".join(self.portfolio["holdings"].keys())
            decisions.append({
                "action": "HOLD",
                "justification": (
                    f"No buy criteria met (P/E<{PE_BUY}) and no sell criteria met (P/E>{PE_SELL}). "
                    f"Holdings: {holdings_str}. "
                    f"Patience is the most important virtue. "
                    f"Portfolio: ${total:,.2f}."
                ),
            })

        return decisions
