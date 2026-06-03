"""
News and sentiment data from 4 sources:
  1. yfinance  — per-ticker news feed
  2. NewsAPI   — top business headlines (requires free key in config.json)
  3. Reddit    — r/wallstreetbets + r/investing public JSON
  4. CNN F&G   — already in market_data.py; reused here for convenience
"""

import os
import json
import requests
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# ── Sentiment word lists ──────────────────────────────────────────────────
POSITIVE = {
    "beat", "beats", "surge", "surged", "rally", "rallied", "gain", "gains",
    "growth", "upgrade", "upgraded", "bullish", "record", "breakout", "profit",
    "profits", "strong", "outperform", "rise", "rises", "jumped", "soar",
    "soared", "boom", "buy", "upside", "higher", "above", "exceeds", "exceeded",
    "opportunity", "recovery", "recovered", "positive", "optimistic",
}
NEGATIVE = {
    "miss", "misses", "missed", "drop", "drops", "crash", "crashed", "loss",
    "losses", "decline", "declined", "downgrade", "downgraded", "bearish",
    "warning", "recession", "sell", "underperform", "cut", "cuts", "fell",
    "fall", "slump", "slumped", "risk", "concern", "weak", "weaker",
    "disappointing", "below", "layoff", "layoffs", "sued", "lawsuit",
    "investigation", "fraud", "bankrupt", "collapse", "panic",
}
MACRO_KEYWORDS = [
    "inflation", "federal reserve", "fed ", "interest rate", "recession",
    "gdp", "unemployment", "cpi", "treasury", "yield", "rate hike",
    "rate cut", "soft landing", "economy", "economic", "tariff", "tariffs",
]

# Ticker symbols to fetch news for (union of all agents' universes)
NEWS_TICKERS = [
    "SPY", "QQQ",
    "NVDA", "TSLA", "META", "GOOGL", "AMD", "PLTR", "CRWD", "COIN", "SNOW",
    "BTC-USD", "ETH-USD", "MSTR", "GME",
    "BRK-B", "JNJ", "KO", "JPM", "CVX", "WMT",
    "BND", "GLD", "SCHD",
]

# Common ticker patterns used on Reddit
TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b|\b([A-Z]{2,5})\b')
COMMON_NON_TICKERS = {
    "I", "A", "THE", "AND", "OR", "FOR", "AT", "BY", "TO", "IN", "OF", "UP",
    "IS", "IT", "BE", "AS", "ON", "WE", "US", "MY", "DO", "GO", "SO", "NO",
    "IF", "ALL", "BUT", "NOW", "GET", "CAN", "NEW", "DID", "HAS", "HIM", "HIS",
    "HOW", "ITS", "NOT", "OUT", "TOO", "TWO", "WAY", "WHO", "YET", "YOU",
    "JUST", "BEEN", "FROM", "HAVE", "INTO", "MORE", "ONLY", "OVER", "THAN",
    "THAT", "THEM", "THEY", "THIS", "WHAT", "WHEN", "WILL", "WITH", "YOUR",
    "MUCH", "SOME", "VERY", "ALSO", "BACK", "BEEN", "COME", "GOOD", "KNOW",
    "LIKE", "LONG", "MAKE", "MANY", "MOST", "MUCH", "NEXT", "SAME", "SUCH",
    "TAKE", "THEN", "WELL", "WERE", "YEAR",
    "ATH", "DD", "ETF", "IPO", "YOY", "WSB", "CEO", "CFO", "SEC", "IRS",
    "GDP", "CPI", "FED", "IMO", "TBH", "TLDR", "YOLO", "FOMO", "OTM", "ITM",
}


def load_config() -> dict:
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def score_text(text: str) -> float:
    """Return sentiment score in [-1, 1]. Positive = bullish, negative = bearish."""
    words = [w.strip(".,!?;:\"'()[]#@") for w in text.lower().split()]
    pos = sum(1 for w in words if w in POSITIVE)
    neg = sum(1 for w in words if w in NEGATIVE)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)


def extract_tickers(text: str) -> list[str]:
    """Extract stock tickers mentioned in text."""
    found = set()
    for m in TICKER_PATTERN.finditer(text):
        t = (m.group(1) or m.group(2)).upper()
        if t not in COMMON_NON_TICKERS and len(t) >= 2:
            found.add(t)
    return list(found)


# ── Source 1: yfinance news per ticker ───────────────────────────────────
def fetch_yfinance_news(tickers: list) -> dict:
    import yfinance as yf
    result = {}
    for ticker in tickers:
        try:
            articles = yf.Ticker(ticker).news or []
            parsed = []
            for a in articles[:6]:
                title = a.get("title", "")
                parsed.append({
                    "title": title,
                    "source": a.get("publisher", ""),
                    "url": a.get("link", ""),
                    "published": a.get("providerPublishTime", 0),
                    "sentiment": score_text(title),
                })
            result[ticker] = parsed
        except Exception:
            result[ticker] = []
    return result


# ── Source 2: NewsAPI.org ─────────────────────────────────────────────────
def fetch_newsapi(api_key: str) -> list:
    if not api_key or api_key in ("your_newsapi_key_here", ""):
        return []
    try:
        resp = requests.get(
            "https://newsapi.org/v2/top-headlines",
            params={"category": "business", "language": "en", "pageSize": 20, "apiKey": api_key},
            timeout=10,
        )
        articles = resp.json().get("articles", [])
        result = []
        for a in articles:
            title = a.get("title") or ""
            desc = a.get("description") or ""
            text = f"{title} {desc}"
            result.append({
                "title": title,
                "source": (a.get("source") or {}).get("name", ""),
                "url": a.get("url", ""),
                "sentiment": score_text(text),
                "is_macro": any(kw in text.lower() for kw in MACRO_KEYWORDS),
                "tickers": extract_tickers(title),
            })
        return result
    except Exception as e:
        print(f"    NewsAPI error: {e}")
        return []


# ── Source 3: Reddit public JSON ─────────────────────────────────────────
def fetch_reddit(subreddit: str, limit: int = 30, user_agent: str = "InvestmentSim/1.0") -> tuple:
    """Returns (posts_list, ticker_mention_counts)."""
    try:
        resp = requests.get(
            f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}",
            headers={"User-Agent": user_agent},
            timeout=12,
        )
        if resp.status_code != 200:
            return [], {}
        children = resp.json().get("data", {}).get("children", [])
        posts = []
        ticker_counts: dict[str, int] = {}
        for child in children:
            p = child.get("data", {})
            title = p.get("title", "")
            tickers = extract_tickers(title)
            for t in tickers:
                ticker_counts[t] = ticker_counts.get(t, 0) + 1
            posts.append({
                "title": title,
                "score": p.get("score", 0),
                "comments": p.get("num_comments", 0),
                "url": "https://reddit.com" + p.get("permalink", ""),
                "tickers": tickers,
                "sentiment": score_text(title),
                "flair": p.get("link_flair_text", ""),
            })
        posts.sort(key=lambda x: x["score"], reverse=True)
        return posts, ticker_counts
    except Exception as e:
        print(f"    Reddit r/{subreddit} error: {e}")
        return [], {}


# ── Master fetch ──────────────────────────────────────────────────────────
def fetch_all_sentiment() -> dict:
    cfg = load_config()
    user_agent = cfg.get("reddit_user_agent", "InvestmentSim/1.0")

    print("  [sentiment] yfinance news...")
    ticker_news = fetch_yfinance_news(NEWS_TICKERS)

    newsapi_key = cfg.get("newsapi_key", "")
    if newsapi_key and newsapi_key != "your_newsapi_key_here":
        print("  [sentiment] NewsAPI headlines...")
        headlines = fetch_newsapi(newsapi_key)
    else:
        headlines = []
        print("  [sentiment] NewsAPI skipped — add key to config.json")

    print("  [sentiment] Reddit r/wallstreetbets...")
    wsb_posts, wsb_tickers = fetch_reddit("wallstreetbets", 30, user_agent)

    print("  [sentiment] Reddit r/investing...")
    inv_posts, inv_tickers = fetch_reddit("investing", 20, user_agent)

    # Overall market sentiment: blend of newsapi + WSB top posts
    sentiments = [h["sentiment"] for h in headlines if h["sentiment"] != 0]
    sentiments += [p["sentiment"] for p in wsb_posts[:10] if p["sentiment"] != 0]
    overall = round(sum(sentiments) / len(sentiments), 3) if sentiments else 0.0

    return {
        "ticker_news": ticker_news,
        "market_headlines": headlines,
        "macro_headlines": [h for h in headlines if h.get("is_macro")],
        "reddit_wsb": wsb_posts[:15],
        "reddit_investing": inv_posts[:10],
        "wsb_tickers": wsb_tickers,
        "inv_tickers": inv_tickers,
        "overall_sentiment": overall,
    }
