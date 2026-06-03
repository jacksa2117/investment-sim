import json
import os
from datetime import datetime
from abc import ABC, abstractmethod

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BaseAgent(ABC):
    def __init__(self, name: str, starting_capital: float = 10000):
        self.name = name
        self.starting_capital = starting_capital
        self.slug = name.lower().replace(" ", "_")
        self.portfolio_file = os.path.join(BASE_DIR, "data", "portfolios", f"{self.slug}.json")
        self.log_file = os.path.join(BASE_DIR, "data", "logs", f"{self.slug}_log.json")
        self.portfolio = self._load_portfolio()

    def _load_portfolio(self):
        if os.path.exists(self.portfolio_file):
            with open(self.portfolio_file) as f:
                return json.load(f)
        return {
            "agent_name": self.name,
            "starting_capital": self.starting_capital,
            "cash": self.starting_capital,
            "holdings": {},
            "total_value": self.starting_capital,
            "return_pct": 0.0,
            "peak_value": self.starting_capital,
            "max_drawdown": 0.0,
            "last_updated": None,
            "trade_count": 0,
        }

    def save_portfolio(self):
        os.makedirs(os.path.dirname(self.portfolio_file), exist_ok=True)
        with open(self.portfolio_file, "w") as f:
            json.dump(self.portfolio, f, indent=2)

    def log_decision(self, decisions: list):
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        logs = []
        if os.path.exists(self.log_file):
            with open(self.log_file) as f:
                logs = json.load(f)
        logs.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "decisions": decisions,
            "portfolio_value": self.portfolio["total_value"],
            "return_pct": self.portfolio["return_pct"],
        })
        with open(self.log_file, "w") as f:
            json.dump(logs, f, indent=2)

    def update_portfolio_value(self, prices: dict):
        total = self.portfolio["cash"]
        for ticker, holding in self.portfolio["holdings"].items():
            price = prices.get(ticker, holding.get("current_price", holding["avg_cost"]))
            val = holding["shares"] * price
            total += val
            holding["current_price"] = round(price, 4)
            holding["current_value"] = round(val, 2)
            holding["unrealized_pnl_pct"] = round((price / holding["avg_cost"] - 1) * 100, 2)

        self.portfolio["total_value"] = round(total, 2)
        self.portfolio["return_pct"] = round((total / self.starting_capital - 1) * 100, 2)
        self.portfolio["last_updated"] = datetime.now().strftime("%Y-%m-%d")

        if total > self.portfolio["peak_value"]:
            self.portfolio["peak_value"] = round(total, 2)
        dd = (self.portfolio["peak_value"] - total) / self.portfolio["peak_value"] * 100
        if dd > self.portfolio.get("max_drawdown", 0):
            self.portfolio["max_drawdown"] = round(dd, 2)

    def buy(self, ticker: str, amount_usd: float, price: float, justification: str):
        if price <= 0:
            return None
        amount_usd = min(amount_usd, self.portfolio["cash"])
        if amount_usd < 1:
            return None
        shares = amount_usd / price
        cost = shares * price
        self.portfolio["cash"] = round(self.portfolio["cash"] - cost, 4)
        h = self.portfolio["holdings"]
        if ticker in h:
            total_shares = h[ticker]["shares"] + shares
            h[ticker]["avg_cost"] = round(
                (h[ticker]["avg_cost"] * h[ticker]["shares"] + cost) / total_shares, 4
            )
            h[ticker]["shares"] = round(total_shares, 6)
        else:
            h[ticker] = {
                "shares": round(shares, 6),
                "avg_cost": round(price, 4),
                "current_price": round(price, 4),
                "current_value": round(cost, 2),
                "unrealized_pnl_pct": 0.0,
            }
        self.portfolio["trade_count"] = self.portfolio.get("trade_count", 0) + 1
        return {
            "action": "BUY",
            "ticker": ticker,
            "shares": round(shares, 4),
            "price": round(price, 2),
            "value": round(cost, 2),
            "justification": justification,
        }

    def sell(self, ticker: str, pct: float, price: float, justification: str):
        if ticker not in self.portfolio["holdings"] or price <= 0:
            return None
        h = self.portfolio["holdings"][ticker]
        shares_to_sell = h["shares"] * (pct / 100)
        proceeds = round(shares_to_sell * price, 2)
        self.portfolio["cash"] = round(self.portfolio["cash"] + proceeds, 4)
        h["shares"] = round(h["shares"] - shares_to_sell, 6)
        if h["shares"] < 0.0001:
            del self.portfolio["holdings"][ticker]
        self.portfolio["trade_count"] = self.portfolio.get("trade_count", 0) + 1
        return {
            "action": "SELL",
            "ticker": ticker,
            "shares": round(shares_to_sell, 4),
            "price": round(price, 2),
            "value": proceeds,
            "pct_sold": round(pct, 1),
            "justification": justification,
        }

    def sell_all(self, ticker: str, price: float, justification: str):
        return self.sell(ticker, 100, price, justification)

    @abstractmethod
    def run(self, market_data: dict, fear_greed: dict) -> list:
        pass
