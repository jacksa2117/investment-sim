from .base_agent import BaseAgent

FOMO_WATCHLIST   = ["NVDA", "TSLA", "META", "COIN", "PLTR", "AMD"]
PANIC_PRIORITY   = ["COIN", "PLTR", "TSLA", "GME", "SNOW", "MSTR"]


def _scan_headlines(sentiment: dict) -> tuple[float, str, str]:
    """
    Read ALL available news and Reddit posts.
    Returns (avg_sentiment, most_alarming_headline, most_exciting_headline).
    """
    all_texts = []

    # Market headlines
    for h in sentiment.get("market_headlines", []):
        all_texts.append((h["sentiment"], h["title"]))

    # Reddit WSB (emotional investor loves Reddit)
    for p in sentiment.get("reddit_wsb", [])[:8]:
        all_texts.append((p["sentiment"], p["title"]))

    # Ticker news for FOMO watchlist
    ticker_news = sentiment.get("ticker_news", {})
    for ticker in FOMO_WATCHLIST:
        for art in (ticker_news.get(ticker) or [])[:2]:
            all_texts.append((art["sentiment"], art["title"]))

    if not all_texts:
        return 0.0, "no news", "no news"

    avg_sent       = sum(s for s, _ in all_texts) / len(all_texts)
    alarming       = min(all_texts, key=lambda x: x[0])[1]
    exciting       = max(all_texts, key=lambda x: x[0])[1]
    return avg_sent, alarming, exciting


def _most_wsb_hyped(sentiment: dict, prices: dict) -> tuple[str, int]:
    """Return the most-mentioned WSB ticker that we can actually trade."""
    tradeable = set(FOMO_WATCHLIST)
    wsb = sentiment.get("wsb_tickers", {})
    candidates = [(t, c) for t, c in wsb.items() if t in tradeable and t in prices]
    if not candidates:
        return "", 0
    return max(candidates, key=lambda x: x[1])


class EmotionalInvestorAgent(BaseAgent):
    def __init__(self):
        super().__init__("Emotional")

    def run(self, market_data: dict, fear_greed: dict) -> list:
        prices      = market_data["prices"]
        returns_1d  = market_data.get("returns_1d", {})
        returns_1w  = market_data.get("returns_1w", {})
        sentiment   = market_data.get("sentiment", {})
        fg          = fear_greed.get("value", 50)
        fg_class    = fear_greed.get("classification", "Neutral")
        spy_today   = returns_1d.get("SPY", 0)
        qqq_today   = returns_1d.get("QQQ", 0)
        total       = self.portfolio["total_value"]
        decisions   = []

        news_sent, alarming_hl, exciting_hl = _scan_headlines(sentiment)
        wsb_ticker, wsb_count = _most_wsb_hyped(sentiment, prices)

        # ──────────────────────────────────────────────────────────────────
        # SCENARIO 1: FULL PANIC — sell most of everything
        # ──────────────────────────────────────────────────────────────────
        if fg < 22 or spy_today < -2.5 or news_sent < -0.4:
            if fg < 22:
                trigger = f"Fear & Greed CRASHED to {fg:.0f}!"
            elif spy_today < -2.5:
                trigger = f"Market COLLAPSING ({spy_today:.1f}% today)!"
            else:
                trigger = f"Terrifying headlines: '{alarming_hl[:60]}'"
            for ticker in list(self.portfolio["holdings"].keys()):
                price = prices.get(ticker)
                if price:
                    d = self.sell(
                        ticker, 75, price,
                        f"PANIC! {trigger} "
                        f"I can't watch this anymore. SELLING 75% before it goes to zero! "
                        f"News sentiment: {news_sent:+.2f}."
                    )
                    if d:
                        decisions.append(d)

        # ──────────────────────────────────────────────────────────────────
        # SCENARIO 2: MASSIVE FOMO — market pumping + Reddit hype
        # ──────────────────────────────────────────────────────────────────
        elif fg > 72 or (spy_today > 1.2 and qqq_today > 1.5) or news_sent > 0.4:
            if fg > 72:
                trigger = f"FOMO: F&G={fg:.0f}, everyone's getting rich!"
            elif news_sent > 0.4:
                trigger = f"Incredible news everywhere: '{exciting_hl[:60]}'"
            else:
                trigger = f"Market PUMPING ({spy_today:.1f}% today)!"

            # Go for the most hyped name
            best_ticker = wsb_ticker or (
                max(FOMO_WATCHLIST, key=lambda t: returns_1w.get(t, 0))
            )
            price = prices.get(best_ticker)
            if price:
                buy_amt = min(self.portfolio["cash"] * 0.45, total * 0.30)
                wsb_note = f" {wsb_ticker} is trending on WSB ({wsb_count}× today)!" if wsb_count > 3 else ""
                d = self.buy(
                    best_ticker, buy_amt, price,
                    f"{trigger}{wsb_note} "
                    f"I HAVE to buy {best_ticker} right now before it goes parabolic! "
                    f"1W return: {returns_1w.get(best_ticker,0):.1f}%."
                )
                if d:
                    decisions.append(d)

        # ──────────────────────────────────────────────────────────────────
        # SCENARIO 3: Reddit-driven impulse buy
        # ──────────────────────────────────────────────────────────────────
        elif wsb_count >= 5 and self.portfolio["cash"] > 400:
            price = prices.get(wsb_ticker)
            if price:
                buy_amt = min(self.portfolio["cash"] * 0.25, total * 0.18)
                d = self.buy(
                    wsb_ticker, buy_amt, price,
                    f"${wsb_ticker} is EVERYWHERE on WallStreetBets ({wsb_count}× today)! "
                    f"I can't miss this. Buying before it goes crazy. YOLO! "
                    f"F&G={fg:.0f}."
                )
                if d:
                    decisions.append(d)

        # ──────────────────────────────────────────────────────────────────
        # SCENARIO 4: Mild fear — shaky hands, sells a bit
        # ──────────────────────────────────────────────────────────────────
        elif fg < 40 and spy_today < -0.7 and self.portfolio["holdings"]:
            tickers_held     = list(self.portfolio["holdings"].keys())
            sell_candidates  = [t for t in PANIC_PRIORITY if t in tickers_held] or tickers_held
            ticker           = sell_candidates[0]
            price            = prices.get(ticker)
            if price:
                d = self.sell(
                    ticker, 30, price,
                    f"Feeling nervous... SPY down {abs(spy_today):.1f}% and F&G={fg:.0f}. "
                    f"Selling some {ticker} just in case. Scary headline: '{alarming_hl[:60]}'. "
                    f"Maybe I'll buy back cheaper later (spoiler: I won't)."
                )
                if d:
                    decisions.append(d)

        # ──────────────────────────────────────────────────────────────────
        # SCENARIO 5: Nice green day — mild FOMO top-up
        # ──────────────────────────────────────────────────────────────────
        elif spy_today > 0.6 and self.portfolio["cash"] > 600:
            hot = [(t, returns_1d.get(t, 0)) for t in FOMO_WATCHLIST if t in prices]
            hot.sort(key=lambda x: x[1], reverse=True)
            if hot and hot[0][1] > 1.5:
                ticker, d_ret = hot[0]
                price         = prices.get(ticker)
                buy_amt       = min(self.portfolio["cash"] * 0.18, 1200)
                d = self.buy(
                    ticker, buy_amt, price,
                    f"Market's green today (+{spy_today:.1f}%). {ticker} up {d_ret:.1f}%! "
                    f"'{exciting_hl[:60]}' — this sounds huge. Buying while it's still moving."
                )
                if d:
                    decisions.append(d)

        # ── Day-1 initial buy ─────────────────────────────────────────────
        if not self.portfolio["holdings"] and not decisions:
            ticker = wsb_ticker or max(FOMO_WATCHLIST, key=lambda t: returns_1w.get(t, 0))
            price  = prices.get(ticker)
            if price:
                d = self.buy(
                    ticker, self.portfolio["cash"] * 0.65, price,
                    f"Going big on {ticker} — everyone's talking about it "
                    f"({wsb_count}× on WSB)! "
                    f"'{exciting_hl[:60]}'. This is definitely the one. ALL IN (well, 65%)."
                )
                if d:
                    decisions.append(d)

        if not decisions:
            mood = "anxious 😰" if fg < 45 else "excited 🤩" if fg > 65 else "uncertain 😕"
            decisions.append({
                "action": "HOLD",
                "justification": (
                    f"Feeling {mood}. SPY={spy_today:+.1f}%, F&G={fg:.0f} ({fg_class}). "
                    f"News: {news_sent:+.2f}. Latest: '{alarming_hl[:60]}'. "
                    f"WSB buzz: {wsb_ticker}×{wsb_count} if wsb_count else 'quiet'. "
                    f"Refreshing portfolio every 5 minutes but not sure what to do. "
                    f"Portfolio: ${total:,.2f}."
                ),
            })

        return decisions
