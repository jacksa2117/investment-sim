import yfinance as yf
import requests
import pandas as pd
import numpy as np
from datetime import datetime

ALL_TICKERS = [
    "BND", "GLD", "SCHD", "VIG",
    "SPY", "VT", "QQQ",
    "NVDA", "META", "GOOGL", "AMD", "TSLA",
    "PLTR", "CRWD", "SHOP", "SNOW", "COIN",
    "GME", "AMC", "MSTR",
    "BTC-USD", "ETH-USD", "DOGE-USD", "SOL-USD",
    "BRK-B", "JNJ", "KO", "PG", "JPM",
    "BAC", "CVX", "WMT", "MCD", "ABBV",
]
CRYPTO_TICKERS  = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"]
VALUE_TICKERS   = ["BRK-B", "JNJ", "KO", "PG", "JPM", "BAC", "CVX", "WMT", "MCD", "ABBV"]
GROWTH_TICKERS  = ["NVDA", "META", "GOOGL", "AMD", "TSLA", "PLTR", "CRWD", "SHOP", "SNOW", "COIN"]

# Hardcoded names — no extra API call needed
TICKER_NAMES = {
    "SPY":      "SPDR S&P 500 ETF Trust",
    "QQQ":      "Invesco QQQ Trust (Nasdaq-100)",
    "VT":       "Vanguard Total World Stock ETF",
    "BND":      "Vanguard Total Bond Market ETF",
    "GLD":      "SPDR Gold Shares",
    "SCHD":     "Schwab U.S. Dividend Equity ETF",
    "VIG":      "Vanguard Dividend Appreciation ETF",
    "NVDA":     "NVIDIA Corporation",
    "META":     "Meta Platforms Inc",
    "GOOGL":    "Alphabet Inc (Google)",
    "AMD":      "Advanced Micro Devices Inc",
    "TSLA":     "Tesla Inc",
    "PLTR":     "Palantir Technologies Inc",
    "CRWD":     "CrowdStrike Holdings Inc",
    "SHOP":     "Shopify Inc",
    "SNOW":     "Snowflake Inc",
    "COIN":     "Coinbase Global Inc",
    "GME":      "GameStop Corp",
    "AMC":      "AMC Entertainment Holdings",
    "MSTR":     "MicroStrategy Inc",
    "BTC-USD":  "Bitcoin",
    "ETH-USD":  "Ethereum",
    "SOL-USD":  "Solana",
    "DOGE-USD": "Dogecoin",
    "BRK-B":    "Berkshire Hathaway Inc (Class B)",
    "JNJ":      "Johnson & Johnson",
    "KO":       "The Coca-Cola Company",
    "PG":       "Procter & Gamble Co",
    "JPM":      "JPMorgan Chase & Co",
    "BAC":      "Bank of America Corp",
    "CVX":      "Chevron Corporation",
    "WMT":      "Walmart Inc",
    "MCD":      "McDonald's Corporation",
    "ABBV":     "AbbVie Inc",
}


# ── Sparkline SVG ─────────────────────────────────────────────────────────

def _sparkline_svg(prices: list, width: int = 120, height: int = 44) -> str:
    if not prices or len(prices) < 2:
        return ""
    lo, hi = min(prices), max(prices)
    rng = hi - lo or lo * 0.01 or 1
    n   = len(prices)
    pad = 2  # padding so line doesn't touch edges

    def px(i, p):
        x = round(pad + (i / (n - 1)) * (width - pad * 2), 2)
        y = round(pad + (1 - (p - lo) / rng) * (height - pad * 2), 2)
        return f"{x},{y}"

    pts       = [px(i, p) for i, p in enumerate(prices)]
    color     = "#3fb950" if prices[-1] >= prices[0] else "#f85149"
    polyline  = " ".join(pts)
    # Closed polygon for gradient fill (trace line then close at bottom)
    fill_pts  = f"{pad},{height-pad} {polyline} {width-pad},{height-pad}"
    uid       = abs(hash(str(prices[:3]))) % 99999  # unique gradient id per chart

    return (
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="display:block;width:100%;height:{height}px">'
        f'<defs><linearGradient id="sg{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.25"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/>'
        f'</linearGradient></defs>'
        f'<polygon points="{fill_pts}" fill="url(#sg{uid})"/>'
        f'<polyline points="{polyline}" fill="none" stroke="{color}" '
        f'stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>'
        f'</svg>'
    )


# ── Sentiment helpers ─────────────────────────────────────────────────────

def calculate_rsi(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 1:
        return 50.0
    delta    = series.diff().dropna()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs  = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    val = float(rsi.iloc[-1])
    return val if not np.isnan(val) else 50.0


def fetch_fear_greed() -> dict:
    try:
        resp = requests.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10,
        )
        data = resp.json()
        return {
            "value":          float(data["fear_and_greed"]["score"]),
            "classification": str(data["fear_and_greed"]["rating"]),
        }
    except Exception:
        pass
    return {"value": 50.0, "classification": "Neutral"}


def _classify_fg(v: float) -> str:
    if v <= 25: return "Extreme Fear"
    if v <= 45: return "Fear"
    if v <= 55: return "Neutral"
    if v <= 75: return "Greed"
    return "Extreme Greed"


# ── Close-series extractor ────────────────────────────────────────────────

def _close_series(raw, ticker: str) -> pd.Series:
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            return raw["Close"][ticker].dropna()
        return raw["Close"].dropna()
    except Exception:
        return pd.Series(dtype=float)


# ── Crypto fetch (4-hour cycle) ───────────────────────────────────────────

def fetch_crypto_data() -> dict:
    raw = yf.download(CRYPTO_TICKERS, period="60d", auto_adjust=True, progress=False)

    prices, rsi_values, returns_1d, returns_1w, ticker_info = {}, {}, {}, {}, {}
    for ticker in CRYPTO_TICKERS:
        series = _close_series(raw, ticker)
        if len(series) < 2:
            continue
        prices[ticker]     = round(float(series.iloc[-1]), 4)
        rsi_values[ticker] = round(calculate_rsi(series), 2)
        returns_1d[ticker] = round(float(series.iloc[-1] / series.iloc[-2] - 1) * 100, 3)
        lb = min(5, len(series) - 1)
        returns_1w[ticker] = round(float(series.iloc[-1] / series.iloc[-1 - lb] - 1) * 100, 3)

        prices_30d = [round(float(p), 4) for p in series.iloc[-30:].tolist()]
        ticker_info[ticker] = {
            "name":      TICKER_NAMES.get(ticker, ticker),
            "high52":    round(float(series.max()), 4),
            "low52":     round(float(series.min()), 4),
            "sparkline": _sparkline_svg(prices_30d),
        }

    print(f"  Crypto: {', '.join(f'{t}=${prices.get(t,0):,.0f}' for t in CRYPTO_TICKERS if t in prices)}")
    return {
        "prices": prices, "rsi": rsi_values,
        "returns_1d": returns_1d, "returns_1w": returns_1w,
        "fundamentals": {}, "ticker_info": ticker_info,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }


# ── Full market fetch (morning run) ──────────────────────────────────────

def fetch_market_data(include_fundamentals: bool = True) -> dict:
    # Download 1 year — gives us RSI, returns, 52w stats, and sparkline from one call
    print("  Downloading 1-year price history...")
    raw = yf.download(ALL_TICKERS, period="1y", auto_adjust=True, progress=False)

    prices, rsi_values, returns_1d, returns_1w, ticker_info = {}, {}, {}, {}, {}

    for ticker in ALL_TICKERS:
        series = _close_series(raw, ticker)
        if len(series) < 2:
            continue

        prices[ticker]     = round(float(series.iloc[-1]), 4)
        rsi_values[ticker] = round(calculate_rsi(series), 2)
        returns_1d[ticker] = round(float(series.iloc[-1] / series.iloc[-2] - 1) * 100, 3)
        lb = min(5, len(series) - 1)
        returns_1w[ticker] = round(float(series.iloc[-1] / series.iloc[-1 - lb] - 1) * 100, 3)

        prices_30d = [round(float(p), 4) for p in series.iloc[-30:].tolist()]
        ticker_info[ticker] = {
            "name":      TICKER_NAMES.get(ticker, ticker),
            "high52":    round(float(series.max()), 4),
            "low52":     round(float(series.min()), 4),
            "sparkline": _sparkline_svg(prices_30d),
        }

    print(f"  Prices fetched: {len(prices)}/{len(ALL_TICKERS)} tickers")

    if not include_fundamentals:
        print("  Fundamentals skipped (afternoon mode)")
        return {
            "prices": prices, "rsi": rsi_values,
            "returns_1d": returns_1d, "returns_1w": returns_1w,
            "fundamentals": {}, "ticker_info": ticker_info,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }

    # Fundamentals (best-effort)
    print("  Fetching fundamentals...")
    fundamentals = {}
    for ticker in VALUE_TICKERS + GROWTH_TICKERS:
        try:
            full = yf.Ticker(ticker).info
            fundamentals[ticker] = {
                "pe":             full.get("trailingPE"),
                "pb":             full.get("priceToBook"),
                "dividend_yield": (full.get("dividendYield") or 0) * 100,
                "revenue_growth": full.get("revenueGrowth"),
                "profit_margins": full.get("profitMargins"),
                "free_cashflow":  full.get("freeCashflow"),
                "debt_to_equity": full.get("debtToEquity"),
                "market_cap":     full.get("marketCap"),
                "gross_margins":  full.get("grossMargins"),
            }
        except Exception:
            fundamentals[ticker] = {}

    return {
        "prices": prices, "rsi": rsi_values,
        "returns_1d": returns_1d, "returns_1w": returns_1w,
        "fundamentals": fundamentals, "ticker_info": ticker_info,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
