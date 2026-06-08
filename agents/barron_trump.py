from .base_agent import BaseAgent

# Barron Trump: heavy crypto, meme coins, Trump-related assets, AI/tech
# Based on reported interests: crypto (especially meme coins), AI, tech
UNIVERSE = [
    "BTC-USD",   # Bitcoin — the blue chip of crypto
    "ETH-USD",   # Ethereum
    "DOGE-USD",  # Doge — Elon/Trump connection
    "SOL-USD",   # Solana — fast meme coin platform
    "DJT",       # Trump Media & Technology
    "TSLA",      # Elon Musk ally
    "NVDA",      # AI dominance
    "PLTR",      # Palantir — data/AI
    "MSTR",      # Michael Saylor Bitcoin proxy
    "COIN",      # Coinbase
]

MAX_POS    = 0.25   # can go up to 25% in one position (young, concentrated)
RSI_OB     = 75
RSI_OS     = 30
TRUMP_TICKERS = {"DJT", "DOGE-USD"}  # politically connected, always on radar


def _crypto_momentum(market_data: dict) -> list:
    """Return crypto tickers sorted by 1-week return descending."""
    returns_1w = market_data.get("returns_1w", {})
    crypto = ["BTC-USD", "ETH-USD", "DOGE-USD", "SOL-USD"]
    return sorted([t for t in crypto if t in returns_1w],
                  key=lambda t: returns_1w[t], reverse=True)


def _trump_news_sentiment(sentiment: dict) -> float:
    """Check if Trump-related news is positive (boosts DJT/DOGE)."""
    scores = []
    for art in sentiment.get("market_headlines", []):
        title = art.get("title", "").lower()
        if any(kw in title for kw in ["trump", "djt", "maga", "doge", "elon"]):
            scores.append(art.get("sentiment", 0))
    return sum(scores) / len(scores) if scores else 0.0


class BarronTrumpAgent(BaseAgent):
    def __init__(self):
        super().__init__("Barron Trump")

    def run(self, market_data: dict, fear_greed: dict) -> list:
        prices     = market_data["prices"]
        rsi        = market_data.get("rsi", {})
        returns_1d = market_data.get("returns_1d", {})
        returns_1w = market_data.get("returns_1w", {})
        sentiment  = market_data.get("sentiment", {})
        fg         = fear_greed.get("value", 50)
        total      = self.portfolio["total_value"]
        decisions  = []

        trump_sent = _trump_news_sentiment(sentiment)
        wsb        = sentiment.get("wsb_tickers", {})

        # ── Day-1 initial deployment ──────────────────────────────────────
        if not self.portfolio["holdings"] and not decisions:
            # Start with a classic Barron portfolio: heavy crypto + DJT
            initial = [
                ("BTC-USD",  0.30),   # Bitcoin 30%
                ("ETH-USD",  0.20),   # Ethereum 20%
                ("DOGE-USD", 0.15),   # Doge 15% (Elon/Trump play)
                ("DJT",      0.15),   # Dad's company
                ("NVDA",     0.10),   # AI
                ("SOL-USD",  0.10),   # Solana 10%
            ]
            for ticker, alloc in initial:
                price = prices.get(ticker)
                if price:
                    buy_amt = self.portfolio["cash"] * alloc
                    d = self.buy(ticker, buy_amt, price,
                        f"Initial portfolio. Barron classic: {int(alloc*100)}% in {ticker}. "
                        f"Crypto heavy, AI exposure, and keeping it in the family (DJT).")
                    if d:
                        decisions.append(d)
            return decisions

        # ── Exit: overbought or stop-loss ─────────────────────────────────
        for ticker in list(self.portfolio["holdings"].keys()):
            price = prices.get(ticker)
            if not price:
                continue
            h        = self.portfolio["holdings"][ticker]
            gain_pct = (price / h["avg_cost"] - 1) * 100
            r        = rsi.get(ticker, 50)

            if r > RSI_OB and gain_pct > 15:
                pct_sell = 40
                d = self.sell(ticker, pct_sell, price,
                    f"RSI={r:.0f} overbought + {gain_pct:.1f}% gain on {ticker}. "
                    f"Trimming {pct_sell}%. F&G={fg:.0f}. Taking some off the table.")
                if d:
                    decisions.append(d)
            elif gain_pct < -25 and ticker not in TRUMP_TICKERS:
                # Never fully sells DJT or DOGE — political loyalty
                d = self.sell(ticker, 50, price,
                    f"Stop-loss: {ticker} down {abs(gain_pct):.1f}%. "
                    f"Cutting half. Not a Trump asset so no emotional attachment.")
                if d:
                    decisions.append(d)

        # ── Trump news boost → buy DJT / DOGE ────────────────────────────
        if trump_sent > 0.2:
            for ticker in ["DJT", "DOGE-USD"]:
                price = prices.get(ticker)
                if not price or self.portfolio["cash"] < 200:
                    continue
                current_val = self.portfolio["holdings"].get(ticker, {}).get("current_value", 0)
                if current_val / total < MAX_POS:
                    buy_amt = min(self.portfolio["cash"] * 0.20, total * 0.10)
                    d = self.buy(ticker, buy_amt, price,
                        f"Trump news is POSITIVE (sent={trump_sent:+.2f}). "
                        f"Adding {ticker}. Family loyalty + political momentum. F&G={fg:.0f}.")
                    if d:
                        decisions.append(d)

        # ── Extreme Fear → buy BTC + DOGE dip ────────────────────────────
        elif fg < 25:
            for ticker in ["BTC-USD", "DOGE-USD"]:
                price = prices.get(ticker)
                if not price or self.portfolio["cash"] < 150:
                    continue
                r = rsi.get(ticker, 50)
                current_val = self.portfolio["holdings"].get(ticker, {}).get("current_value", 0)
                if current_val / total < MAX_POS:
                    buy_amt = min(self.portfolio["cash"] * 0.25, total * 0.12)
                    d = self.buy(ticker, buy_amt, price,
                        f"EXTREME FEAR ({fg:.0f}) = buying opportunity. "
                        f"Loading {ticker} — dad says buy the dip. RSI={r:.0f}.")
                    if d:
                        decisions.append(d)

        # ── Momentum: chase best performing crypto this week ──────────────
        elif fg > 65:
            top_crypto = _crypto_momentum(market_data)
            for ticker in top_crypto[:2]:
                price = prices.get(ticker)
                if not price or self.portfolio["cash"] < 200:
                    continue
                r      = rsi.get(ticker, 50)
                w_ret  = returns_1w.get(ticker, 0)
                current_val = self.portfolio["holdings"].get(ticker, {}).get("current_value", 0)
                if r < RSI_OB and current_val / total < MAX_POS and w_ret > 5:
                    buy_amt = min(self.portfolio["cash"] * 0.20, total * 0.10)
                    d = self.buy(ticker, buy_amt, price,
                        f"Greed mode ({fg:.0f}). {ticker} up {w_ret:.1f}% this week. "
                        f"RSI={r:.0f}. Riding momentum. Gen Z doesn't fear FOMO.")
                    if d:
                        decisions.append(d)

        # ── RSI oversold bounce on any universe ticker ────────────────────
        if not decisions:
            oversold = [(t, rsi.get(t, 50)) for t in UNIVERSE
                        if t in prices and rsi.get(t, 50) < RSI_OS]
            oversold.sort(key=lambda x: x[1])
            for ticker, r in oversold[:1]:
                price = prices.get(ticker)
                if not price or self.portfolio["cash"] < 150:
                    continue
                current_val = self.portfolio["holdings"].get(ticker, {}).get("current_value", 0)
                if current_val / total < MAX_POS:
                    buy_amt = min(self.portfolio["cash"] * 0.18, total * 0.10)
                    d = self.buy(ticker, buy_amt, price,
                        f"RSI={r:.0f} oversold on {ticker}. Classic dip buy. "
                        f"Trump sentiment: {trump_sent:+.2f}. F&G={fg:.0f}.")
                    if d:
                        decisions.append(d)

        # ── Hold ──────────────────────────────────────────────────────────
        if not decisions:
            top_pos = sorted(self.portfolio["holdings"].items(),
                             key=lambda x: x[1].get("current_value", 0), reverse=True)
            pos_str = ", ".join(f"{t}({v['unrealized_pnl_pct']:+.1f}%)" for t, v in top_pos[:4])
            decisions.append({
                "action": "HOLD",
                "justification": (
                    f"Chilling. F&G={fg:.0f}. Trump news: {trump_sent:+.2f}. "
                    f"Top positions: {pos_str}. Cash: ${self.portfolio['cash']:,.0f}. "
                    f"Waiting for the next meme catalyst."
                ),
            })

        return decisions
