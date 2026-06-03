from .base_agent import BaseAgent

CRYPTO     = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"]
HOT_STOCKS = ["GME", "AMC", "MSTR", "TSLA", "COIN", "PLTR"]
UNIVERSE   = CRYPTO + HOT_STOCKS
MAX_POS    = 0.20
RSI_OB     = 72
RSI_OS     = 28
WSB_HYPE_THRESHOLD = 4   # mentions before it becomes a buy signal


def _wsb_hype(ticker: str, sentiment: dict) -> int:
    """Return WSB mention count for ticker (strips $ prefix)."""
    wsb = sentiment.get("wsb_tickers", {})
    clean = ticker.replace("-USD", "").replace("-", "")
    return wsb.get(ticker, 0) + wsb.get(clean, 0)


def _crypto_sentiment(sentiment: dict) -> float:
    """Average sentiment of crypto-related news."""
    scores = []
    for coin in ["BTC-USD", "ETH-USD", "SOL-USD"]:
        for art in sentiment.get("ticker_news", {}).get(coin, []):
            scores.append(art["sentiment"])
    for post in sentiment.get("reddit_wsb", [])[:10]:
        if any(kw in post["title"].lower() for kw in ["btc", "eth", "crypto", "bitcoin", "ethereum"]):
            scores.append(post["sentiment"])
    return sum(scores) / len(scores) if scores else 0.0


class SpeculatorAgent(BaseAgent):
    def __init__(self):
        super().__init__("Speculator")

    def run_crypto_only(self, market_data: dict, fear_greed: dict) -> list:
        """
        4-hour crypto cycle: only analyzes and trades CRYPTO positions.
        Runs 24/7 since crypto markets never close.
        Uses tighter RSI bands and smaller position sizes for intraday moves.
        """
        prices     = market_data["prices"]
        rsi        = market_data.get("rsi", {})
        returns_1d = market_data.get("returns_1d", {})
        sentiment  = market_data.get("sentiment", {})
        fg         = fear_greed.get("value", 50)
        total      = self.portfolio["total_value"]
        decisions  = []
        now_hour   = __import__("datetime").datetime.now().hour

        crypto_sent = _crypto_sentiment(sentiment)
        time_label  = f"{'overnight' if now_hour < 6 else 'morning' if now_hour < 12 else 'afternoon' if now_hour < 18 else 'evening'} ({now_hour:02d}:00)"

        # ── Exit overbought crypto ────────────────────────────────────────
        for ticker in [t for t in list(self.portfolio["holdings"].keys()) if t in CRYPTO]:
            price = prices.get(ticker)
            if not price:
                continue
            r        = rsi.get(ticker, 50)
            h        = self.portfolio["holdings"][ticker]
            gain_pct = (price / h["avg_cost"] - 1) * 100

            if r > 75 and gain_pct > 8:
                d = self.sell(ticker, 40, price,
                    f"[CRYPTO 4h] RSI={r:.0f} overbought. Trimming {ticker} +{gain_pct:.1f}%. "
                    f"Crypto sent: {crypto_sent:+.2f}. Time: {time_label}.")
                if d: decisions.append(d)
            elif gain_pct < -15:
                d = self.sell(ticker, 35, price,
                    f"[CRYPTO 4h] Stop-loss: {ticker} down {abs(gain_pct):.1f}%. "
                    f"F&G={fg:.0f}. Cutting before it gets worse.")
                if d: decisions.append(d)

        # ── Extreme fear → buy dip ────────────────────────────────────────
        if fg < 25:
            for ticker in ["BTC-USD", "ETH-USD"]:
                price = prices.get(ticker)
                if not price:
                    continue
                current_val = (self.portfolio["holdings"].get(ticker, {}).get("shares", 0) * price)
                if current_val / total < MAX_POS * 0.7 and self.portfolio["cash"] > 200:
                    buy_amt = min(self.portfolio["cash"] * 0.20, total * 0.08)
                    d = self.buy(ticker, buy_amt, price,
                        f"[CRYPTO 4h] EXTREME FEAR ({fg:.0f}) at {time_label}. "
                        f"Adding {ticker}. Sent: {crypto_sent:+.2f}. RSI={rsi.get(ticker,50):.0f}.")
                    if d: decisions.append(d)

        # ── RSI oversold bounce ───────────────────────────────────────────
        elif not decisions:
            for ticker in CRYPTO:
                price = prices.get(ticker)
                if not price:
                    continue
                r = rsi.get(ticker, 50)
                if r < 30:
                    current_val = (self.portfolio["holdings"].get(ticker, {}).get("shares", 0) * price)
                    if current_val / total < MAX_POS and self.portfolio["cash"] > 150:
                        buy_amt = min(self.portfolio["cash"] * 0.12, total * 0.06)
                        d = self.buy(ticker, buy_amt, price,
                            f"[CRYPTO 4h] RSI={r:.0f} oversold at {time_label}. "
                            f"Scalp entry on {ticker}. F&G={fg:.0f}.")
                        if d: decisions.append(d); break

        if not decisions:
            crypto_held = {t: v for t, v in self.portfolio["holdings"].items() if t in CRYPTO}
            pos_str = ", ".join(f"{t}(RSI={rsi.get(t,50):.0f})" for t in crypto_held) or "none"
            decisions.append({
                "action": "HOLD",
                "justification": (
                    f"[CRYPTO 4h] {time_label}. No signals. "
                    f"F&G={fg:.0f}, sentiment={crypto_sent:+.2f}. "
                    f"Crypto positions: {pos_str}. Monitoring..."
                ),
            })
        return decisions

    def run(self, market_data: dict, fear_greed: dict) -> list:
        prices      = market_data["prices"]
        rsi         = market_data.get("rsi", {})
        returns_1d  = market_data.get("returns_1d", {})
        returns_1w  = market_data.get("returns_1w", {})
        sentiment   = market_data.get("sentiment", {})
        fg          = fear_greed.get("value", 50)
        fg_class    = fear_greed.get("classification", "Neutral")
        total       = self.portfolio["total_value"]
        decisions   = []

        crypto_sent = _crypto_sentiment(sentiment)

        # ── Exit overbought / stop-loss ───────────────────────────────────
        for ticker in list(self.portfolio["holdings"].keys()):
            price = prices.get(ticker)
            if not price:
                continue
            r        = rsi.get(ticker, 50)
            h        = self.portfolio["holdings"][ticker]
            gain_pct = (price / h["avg_cost"] - 1) * 100
            wsb_buzz = _wsb_hype(ticker, sentiment)

            if r > RSI_OB and gain_pct > 5:
                d = self.sell(
                    ticker, 60, price,
                    f"RSI={r:.0f} (overbought). Locking in {gain_pct:.1f}% gain. "
                    f"WSB mentions: {wsb_buzz}. Momentum traders exit into strength."
                )
                if d:
                    decisions.append(d)
            elif gain_pct > 40:
                d = self.sell(
                    ticker, 33, price,
                    f"Taking 33% profit — {ticker} +{gain_pct:.1f}%. Never wrong to take money off the table. "
                    f"WSB: {wsb_buzz} mentions."
                )
                if d:
                    decisions.append(d)
            elif gain_pct < -20:
                # Check if Reddit still bullish before cutting
                if wsb_buzz < 3:
                    d = self.sell(
                        ticker, 50, price,
                        f"Stop-loss: {ticker} down {abs(gain_pct):.1f}% and WSB buzz dying ({wsb_buzz} mentions). "
                        f"Cutting losers."
                    )
                    if d:
                        decisions.append(d)

        # ── EXTREME FEAR → contrarian crypto buy ─────────────────────────
        if fg < 22:
            for ticker in ["BTC-USD", "ETH-USD"]:
                price = prices.get(ticker)
                if not price:
                    continue
                current_val = 0
                if ticker in self.portfolio["holdings"]:
                    current_val = self.portfolio["holdings"][ticker]["shares"] * price
                if current_val / total < MAX_POS:
                    buy_amt = min(self.portfolio["cash"] * 0.30, total * MAX_POS - current_val)
                    d = self.buy(
                        ticker, buy_amt, price,
                        f"EXTREME FEAR ({fg:.0f}). Crypto sentiment: {crypto_sent:+.2f}. "
                        f"Loading {ticker} while retail panics. "
                        f"Greed when others are fearful."
                    )
                    if d:
                        decisions.append(d)

        # ── EXTREME GREED → chase momentum ───────────────────────────────
        elif fg > 78:
            available = [(t, returns_1w.get(t, 0)) for t in UNIVERSE if t in prices]
            available.sort(key=lambda x: x[1], reverse=True)
            for ticker, w_ret in available[:2]:
                if w_ret < 3:
                    break
                price = prices.get(ticker)
                if not price:
                    continue
                current_val = 0
                if ticker in self.portfolio["holdings"]:
                    current_val = self.portfolio["holdings"][ticker]["shares"] * price
                if current_val / total < MAX_POS:
                    wsb_buzz = _wsb_hype(ticker, sentiment)
                    buy_amt  = min(self.portfolio["cash"] * 0.25, total * MAX_POS - current_val)
                    d = self.buy(
                        ticker, buy_amt, price,
                        f"EXTREME GREED ({fg:.0f}) + MOMENTUM. {ticker} +{w_ret:.1f}% this week. "
                        f"WSB mentions: {wsb_buzz}. Trend is your friend until it bends."
                    )
                    if d:
                        decisions.append(d)

        # ── WSB hype play ─────────────────────────────────────────────────
        else:
            hype_tickers = [
                (t, _wsb_hype(t, sentiment))
                for t in UNIVERSE
                if _wsb_hype(t, sentiment) >= WSB_HYPE_THRESHOLD and t in prices
            ]
            hype_tickers.sort(key=lambda x: x[1], reverse=True)
            for ticker, buzz in hype_tickers[:2]:
                price = prices.get(ticker)
                if not price:
                    continue
                current_val = 0
                if ticker in self.portfolio["holdings"]:
                    current_val = self.portfolio["holdings"][ticker]["shares"] * price
                r = rsi.get(ticker, 50)
                if current_val / total < MAX_POS and r < RSI_OB and self.portfolio["cash"] > 300:
                    buy_amt = min(self.portfolio["cash"] * 0.20, total * 0.12)
                    d = self.buy(
                        ticker, buy_amt, price,
                        f"WSB HYPE: {ticker} mentioned {buzz}x on r/wallstreetbets. "
                        f"RSI={r:.0f}. F&G={fg:.0f}. Retail momentum play."
                    )
                    if d:
                        decisions.append(d)

            # Fallback: RSI oversold
            if not decisions:
                oversold = [(t, rsi.get(t, 50)) for t in UNIVERSE
                            if rsi.get(t, 50) < RSI_OS and t in prices]
                oversold.sort(key=lambda x: x[1])
                for ticker, r in oversold[:1]:
                    price = prices.get(ticker)
                    if not price:
                        continue
                    current_val = 0
                    if ticker in self.portfolio["holdings"]:
                        current_val = self.portfolio["holdings"][ticker]["shares"] * price
                    if current_val / total < MAX_POS and self.portfolio["cash"] > 200:
                        news_sent = 0.0
                        for art in sentiment.get("ticker_news", {}).get(ticker, []):
                            news_sent += art["sentiment"]
                        buy_amt = min(self.portfolio["cash"] * 0.18, total * 0.10)
                        d = self.buy(
                            ticker, buy_amt, price,
                            f"RSI={r:.0f} oversold bounce on {ticker}. News sentiment: {news_sent:+.2f}. "
                            f"F&G={fg:.0f} ({fg_class})."
                        )
                        if d:
                            decisions.append(d)

        # ── Day-1 initial deployment ──────────────────────────────────────
        if not self.portfolio["holdings"] and not decisions:
            for ticker in ["BTC-USD", "ETH-USD", "MSTR", "COIN"]:
                price = prices.get(ticker)
                if price:
                    wsb_buzz = _wsb_hype(ticker, sentiment)
                    d = self.buy(
                        ticker, self.portfolio["cash"] * 0.22, price,
                        f"Initial speculative position: {ticker}. "
                        f"WSB mentions: {wsb_buzz}. Crypto sentiment: {crypto_sent:+.2f}."
                    )
                    if d:
                        decisions.append(d)

        if not decisions:
            top_pos = sorted(
                self.portfolio["holdings"].items(),
                key=lambda x: x[1].get("current_value", 0), reverse=True
            )
            pos_str = ", ".join(
                f"{t}({v['unrealized_pnl_pct']:+.1f}%)" for t, v in top_pos[:3]
            )
            wsb_hot = sorted(sentiment.get("wsb_tickers", {}).items(), key=lambda x: x[1], reverse=True)[:3]
            wsb_str = ", ".join(f"${t}×{c}" for t, c in wsb_hot) if wsb_hot else "quiet"
            decisions.append({
                "action": "HOLD",
                "justification": (
                    f"No clear entry/exit. F&G={fg:.0f} ({fg_class}). "
                    f"Crypto sent: {crypto_sent:+.2f}. WSB buzz: {wsb_str}. "
                    f"Top positions: {pos_str}. Cash: ${self.portfolio['cash']:,.0f}."
                ),
            })

        return decisions
