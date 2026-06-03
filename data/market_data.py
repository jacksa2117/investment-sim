import yfinance as yf
import requests
import pandas as pd
import numpy as np
from datetime import datetime

ALL_TICKERS = [
    "BND", "GLD", "SCHD", "VIG",          # Conservative
    "SPY", "VT", "QQQ",                    # Passive + reference
    "NVDA", "META", "GOOGL", "AMD", "TSLA",
    "PLTR", "CRWD", "SHOP", "SNOW", "COIN",  # Aggressive Growth
    "GME", "AMC", "MSTR",                  # Speculator stocks
    "BTC-USD", "ETH-USD", "DOGE-USD", "SOL-USD",  # Crypto
    "BRK-B", "JNJ", "KO", "PG", "JPM",
    "BAC", "CVX", "WMT", "MCD", "ABBV",   # Value
]

VALUE_TICKERS = ["BRK-B", "JNJ", "KO", "PG", "JPM", "BAC", "CVX", "WMT", "MCD", "ABBV"]
GROWTH_TICKERS = ["NVDA", "META", "GOOGL", "AMD", "TSLA", "PLTR", "CRWD", "SHOP", "SNOW", "COIN"]


def calculate_rsi(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 1:
        return 50.0
    delta = series.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    val = float(rsi.iloc[-1])
    return val if not np.isnan(val) else 50.0


def fetch_fear_greed() -> dict:
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = resp.json()
        score = float(data["fear_and_greed"]["score"])
        rating = str(data["fear_and_greed"]["rating"])
        return {"value": score, "classification": rating}
    except Exception:
        pass
    # Fallback: alternate endpoint
    try:
        url2 = "https://fear-and-greed-index.p.rapidapi.com/v1/fgi"
        resp = requests.get(url2, timeout=8)
        val = resp.json()["fgi"]["now"]["value"]
        return {"value": float(val), "classification": _classify_fg(float(val))}
    except Exception:
        return {"value": 50.0, "classification": "Neutral"}


def _classify_fg(v: float) -> str:
    if v <= 25:
        return "Extreme Fear"
    if v <= 45:
        return "Fear"
    if v <= 55:
        return "Neutral"
    if v <= 75:
        return "Greed"
    return "Extreme Greed"


CRYPTO_TICKERS = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"]


def fetch_crypto_data() -> dict:
    """Lightweight fetch for the 4-hour crypto-only Speculator cycle."""
    raw = yf.download(CRYPTO_TICKERS, period="3d", auto_adjust=True, progress=False)

    if isinstance(raw.columns, pd.MultiIndex):
        close_df = raw["Close"]
    else:
        close_df = pd.DataFrame({CRYPTO_TICKERS[0]: raw["Close"]})

    prices, rsi_values, returns_1d, returns_1w = {}, {}, {}, {}
    for ticker in CRYPTO_TICKERS:
        if ticker not in close_df.columns:
            continue
        series = close_df[ticker].dropna()
        if len(series) < 2:
            continue
        prices[ticker]      = round(float(series.iloc[-1]), 4)
        rsi_values[ticker]  = round(calculate_rsi(series), 2)
        returns_1d[ticker]  = round(float(series.iloc[-1] / series.iloc[-2] - 1) * 100, 3)
        lookback = min(5, len(series) - 1)
        returns_1w[ticker]  = round(float(series.iloc[-1] / series.iloc[-1 - lookback] - 1) * 100, 3)

    print(f"  Crypto prices fetched: {', '.join(f'{t}=${prices.get(t,0):,.0f}' for t in CRYPTO_TICKERS if t in prices)}")
    return {
        "prices": prices, "rsi": rsi_values,
        "returns_1d": returns_1d, "returns_1w": returns_1w,
        "fundamentals": {}, "date": datetime.now().strftime("%Y-%m-%d"),
    }


def fetch_market_data(include_fundamentals: bool = True) -> dict:
    print("  Downloading price history (30d)...")
    raw = yf.download(ALL_TICKERS, period="35d", auto_adjust=True, progress=False)

    # Handle MultiIndex columns from multi-ticker download
    if isinstance(raw.columns, pd.MultiIndex):
        close_df = raw["Close"]
    else:
        close_df = pd.DataFrame({"_single": raw["Close"]})

    prices, rsi_values, returns_1d, returns_1w = {}, {}, {}, {}

    for ticker in ALL_TICKERS:
        col = ticker if ticker in close_df.columns else None
        if col is None:
            continue
        series = close_df[col].dropna()
        if len(series) < 2:
            continue
        prices[ticker] = round(float(series.iloc[-1]), 4)
        rsi_values[ticker] = round(calculate_rsi(series), 2)
        returns_1d[ticker] = round(float(series.iloc[-1] / series.iloc[-2] - 1) * 100, 3)
        lookback = min(5, len(series) - 1)
        returns_1w[ticker] = round(float(series.iloc[-1] / series.iloc[-1 - lookback] - 1) * 100, 3)

    print(f"  Fetched prices for {len(prices)}/{len(ALL_TICKERS)} tickers")

    if not include_fundamentals:
        print("  Skipping fundamentals (afternoon mode)")
        return {
            "prices": prices, "rsi": rsi_values,
            "returns_1d": returns_1d, "returns_1w": returns_1w,
            "fundamentals": {}, "date": datetime.now().strftime("%Y-%m-%d"),
        }

    # Fundamentals (best-effort, non-blocking)
    fundamentals = {}
    for ticker in VALUE_TICKERS + GROWTH_TICKERS:
        try:
            info = yf.Ticker(ticker).fast_info
            full = yf.Ticker(ticker).info
            fundamentals[ticker] = {
                "pe": full.get("trailingPE"),
                "pb": full.get("priceToBook"),
                "dividend_yield": (full.get("dividendYield") or 0) * 100,
                "revenue_growth": full.get("revenueGrowth"),
                "profit_margins": full.get("profitMargins"),
                "free_cashflow": full.get("freeCashflow"),
                "debt_to_equity": full.get("debtToEquity"),
                "market_cap": full.get("marketCap"),
                "gross_margins": full.get("grossMargins"),
            }
        except Exception:
            fundamentals[ticker] = {}

    return {
        "prices": prices,
        "rsi": rsi_values,
        "returns_1d": returns_1d,
        "returns_1w": returns_1w,
        "fundamentals": fundamentals,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
