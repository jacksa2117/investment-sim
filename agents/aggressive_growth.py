from .base_agent import BaseAgent
from datetime import datetime

UNIVERSE  = ["NVDA", "META", "GOOGL", "AMD", "TSLA", "PLTR", "CRWD", "SHOP", "SNOW", "COIN"]
TOP_N     = 5
TARGET_PCT = 1.0 / TOP_N


def _ticker_sentiment_signal(ticker: str, sentiment: dict) -> tuple[float, str]:
    """
    Score a ticker using yfinance news + Reddit mentions.
    Returns (score, summary_string).
    """
    score = 0.0
    parts = []

    # yfinance news sentiment
    news = sentiment.get("ticker_news", {}).get(ticker, [])
    if news:
        avg_sent = sum(n["sentiment"] for n in news) / len(news)
        score += avg_sent * 2
        best = news[0]["title"][:60]
        parts.append(f"news={avg_sent:+.2f}('{best}')")

    # WSB mentions
    wsb_count = sentiment.get("wsb_tickers", {}).get(ticker, 0)
    if wsb_count:
        score += wsb_count * 0.3
        parts.append(f"WSB×{wsb_count}")

    # r/investing mentions
    inv_count = sentiment.get("inv_tickers", {}).get(ticker, 0)
    if inv_count:
        score += inv_count * 0.15
        parts.append(f"inv×{inv_count}")

    return score, " ".join(parts) if parts else "no signal"


class AggressiveGrowthAgent(BaseAgent):
    def __init__(self):
        super().__init__("Aggressive Growth")

    def _score_tickers(self, market_data: dict) -> list:
        fundamentals = market_data.get("fundamentals", {})
        returns_1w   = market_data.get("returns_1w", {})
        sentiment    = market_data.get("sentiment", {})
        scores = []
        for ticker in UNIVERSE:
            f          = fundamentals.get(ticker, {})
            rev_growth = f.get("revenue_growth") or 0
            margin     = f.get("gross_margins") or 0
            momentum   = returns_1w.get(ticker, 0)
            sent_score, _ = _ticker_sentiment_signal(ticker, sentiment)
            total = rev_growth * 50 + margin * 20 + momentum * 0.5 + sent_score * 5
            scores.append((ticker, total))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _should_rebalance(self) -> bool:
        return self.portfolio.get("last_rebalance_month") != datetime.now().strftime("%Y-%m")

    def run(self, market_data: dict, fear_greed: dict) -> list:
        prices    = market_data["prices"]
        sentiment = market_data.get("sentiment", {})
        total     = self.portfolio["total_value"]
        decisions = []

        scored    = self._score_tickers(market_data)
        top_picks = [t for t, _ in scored[:TOP_N] if t in prices]

        # ── Monthly rebalance or initial buy ─────────────────────────────
        if not self.portfolio["holdings"] or self._should_rebalance():
            for ticker in list(self.portfolio["holdings"].keys()):
                if ticker not in top_picks:
                    price = prices.get(ticker)
                    if price:
                        sent_score, sent_note = _ticker_sentiment_signal(ticker, sentiment)
                        d = self.sell(
                            ticker, 100, price,
                            f"{ticker} rotated out of top {TOP_N}. Sentiment: {sent_note}. "
                            f"Reallocating to higher-conviction names."
                        )
                        if d:
                            decisions.append(d)

            for ticker in top_picks:
                price = prices.get(ticker)
                if not price:
                    continue
                target_val   = total * TARGET_PCT * 0.95
                current_val  = 0.0
                if ticker in self.portfolio["holdings"]:
                    current_val = self.portfolio["holdings"][ticker]["shares"] * price
                if target_val - current_val > total * 0.02:
                    buy_amount = min(target_val - current_val, self.portfolio["cash"] * 0.95)
                    f          = market_data["fundamentals"].get(ticker, {})
                    rev_g      = f.get("revenue_growth")
                    rev_str    = f"{rev_g*100:.0f}% YoY revenue growth" if rev_g else "strong momentum"
                    sent_score, sent_note = _ticker_sentiment_signal(ticker, sentiment)
                    d = self.buy(
                        ticker, buy_amount, price,
                        f"Top-{TOP_N} growth pick: {ticker}. {rev_str}. "
                        f"Sentiment: {sent_note}. "
                        f"Tolerates 30%+ drawdowns for asymmetric upside."
                    )
                    if d:
                        decisions.append(d)

            self.portfolio["last_rebalance_month"] = datetime.now().strftime("%Y-%m")

        else:
            # ── Intra-month: news-driven position sizing tweaks ───────────
            for ticker in list(self.portfolio["holdings"].keys()):
                price = prices.get(ticker)
                if not price:
                    continue
                h          = self.portfolio["holdings"][ticker]
                loss_pct   = (price / h["avg_cost"] - 1) * 100
                sent_score, sent_note = _ticker_sentiment_signal(ticker, sentiment)

                if loss_pct < -30:
                    d = self.sell(
                        ticker, 50, price,
                        f"Stop-loss: {ticker} down {abs(loss_pct):.1f}%. News: {sent_note}. "
                        f"Cutting half to preserve capital."
                    )
                    if d:
                        decisions.append(d)
                elif sent_score > 1.5 and self.portfolio["cash"] > total * 0.03:
                    # Strong positive sentiment — add to winner
                    add_amount = min(self.portfolio["cash"] * 0.30, total * 0.05)
                    d = self.buy(
                        ticker, add_amount, price,
                        f"Adding to {ticker} on strong sentiment: {sent_note}. "
                        f"Momentum + news alignment."
                    )
                    if d:
                        decisions.append(d)
                elif sent_score < -1.5:
                    d = self.sell(
                        ticker, 20, price,
                        f"Trimming {ticker} on negative sentiment: {sent_note}. "
                        f"Reducing exposure ahead of potential catalyst."
                    )
                    if d:
                        decisions.append(d)

        if not decisions:
            positions_str = ", ".join(top_picks)
            decisions.append({
                "action": "HOLD",
                "justification": (
                    f"Holding top-{TOP_N}: {positions_str}. "
                    f"Overall sentiment: {sentiment.get('overall_sentiment', 0):+.2f}. "
                    f"Next rebalance: end of {datetime.now().strftime('%B')}. "
                    f"Portfolio: ${total:,.2f}."
                ),
            })

        return decisions
