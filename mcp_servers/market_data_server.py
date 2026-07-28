import json
import logging
import time
import socket
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP
from datetime import datetime, timedelta

socket.setdefaulttimeout(5.0)

logger = logging.getLogger(__name__)

yf_session = requests.Session()
yf_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})


mcp = FastMCP("market-data")

class RateLimiter:
    """Simple rate limiter for Yahoo Finance to prevent throttling."""
    last_call = 0.0
    
    @classmethod
    def wait(cls):
        now = time.time()
        elapsed = now - cls.last_call
        if elapsed < 1.0:  # 1 second pacing
            time.sleep(1.0 - elapsed)
        cls.last_call = time.time()

@mcp.tool()
def get_historical_close_price(ticker: str, date: str) -> str:
    """Fetch the closing price for a ticker on or near a specific date."""
    try:
        RateLimiter.wait()
        t = yf.Ticker(ticker, session=yf_session)
        target_date = datetime.strptime(date, "%Y-%m-%d")
        start_date = target_date - timedelta(days=7)
        end_date = target_date + timedelta(days=1)
        
        hist = t.history(start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"))
        if hist.empty:
            return json.dumps({"price": None, "actual_trading_date": None})
            
        hist = hist[hist.index.tz_localize(None) <= target_date]
        if hist.empty:
            return json.dumps({"price": None, "actual_trading_date": None})
            
        latest_row = hist.iloc[-1]
        actual_date = hist.index[-1].strftime("%Y-%m-%d")
        
        return json.dumps({
            "price": float(latest_row["Close"]),
            "actual_trading_date": actual_date
        })
    except Exception as e:
        logger.warning(f"Failed to fetch price for {ticker} on {date}: {e}")
        return json.dumps({"price": None, "actual_trading_date": None})

@mcp.tool()
def get_company_market_profile(ticker: str) -> str:
    """Fetch company market profile including Beta."""
    try:
        RateLimiter.wait()
        t = yf.Ticker(ticker, session=yf_session)
        info = t.info
        beta = info.get("beta")
        return json.dumps({
            "beta": float(beta) if beta is not None else None,
            "data_source": "yfinance",
            "as_of": datetime.now().strftime("%Y-%m-%d")
        })
    except Exception as e:
        logger.warning(f"Failed to fetch market profile for {ticker}: {e}")
        return json.dumps({"beta": None, "data_source": "yfinance", "as_of": None})

@mcp.tool()
def get_market_snapshot(ticker: str) -> str:
    """Fetch current market snapshot, including YTD and 1-yr returns."""
    try:
        RateLimiter.wait()
        t = yf.Ticker(ticker, session=yf_session)
        info = t.info
        
        today = datetime.now()
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        market_cap = info.get("marketCap")
        fifty_two_high = info.get("fiftyTwoWeekHigh")
        fifty_two_low = info.get("fiftyTwoWeekLow")
        beta = info.get("beta")
        shares = info.get("sharesOutstanding")
        
        # Calculate YTD
        ytd_start = datetime(today.year, 1, 1).strftime("%Y-%m-%d")
        ytd_price_data = json.loads(get_historical_close_price(ticker, ytd_start))
        ytd_price = ytd_price_data.get("price")
        ytd_return = ((current_price / ytd_price) - 1) * 100 if current_price and ytd_price else None
        
        # Calculate 1-yr
        one_yr_start = (today - timedelta(days=365)).strftime("%Y-%m-%d")
        one_yr_price_data = json.loads(get_historical_close_price(ticker, one_yr_start))
        one_yr_price = one_yr_price_data.get("price")
        one_yr_return = ((current_price / one_yr_price) - 1) * 100 if current_price and one_yr_price else None
        
        return json.dumps({
            "current_price": float(current_price) if current_price is not None else None,
            "market_cap": int(market_cap) if market_cap is not None else None,
            "fifty_two_week_high": float(fifty_two_high) if fifty_two_high is not None else None,
            "fifty_two_week_low": float(fifty_two_low) if fifty_two_low is not None else None,
            "beta": float(beta) if beta is not None else None,
            "shares_outstanding": int(shares) if shares is not None else None,
            "ytd_return_pct": float(ytd_return) if ytd_return is not None else None,
            "one_year_return_pct": float(one_yr_return) if one_yr_return is not None else None,
            "data_date": today.strftime("%Y-%m-%d")
        })
    except Exception as e:
        logger.warning(f"Failed to fetch market snapshot for {ticker}: {e}")
        return json.dumps({
            "current_price": None, "market_cap": None, "fifty_two_week_high": None,
            "fifty_two_week_low": None, "beta": None, "shares_outstanding": None,
            "ytd_return_pct": None, "one_year_return_pct": None,
            "data_date": datetime.now().strftime("%Y-%m-%d")
        })

@mcp.tool()
def get_analyst_data(ticker: str) -> str:
    """Fetch analyst consensus, short interest, and institutional ownership."""
    try:
        RateLimiter.wait()
        t = yf.Ticker(ticker, session=yf_session)
        info = t.info
        
        return json.dumps({
            "analyst_consensus_rating": float(info.get("recommendationMean")) if info.get("recommendationMean") is not None else None,
            "analyst_price_target": float(info.get("targetMeanPrice")) if info.get("targetMeanPrice") is not None else None,
            "num_analysts_covering": int(info.get("numberOfAnalystOpinions")) if info.get("numberOfAnalystOpinions") is not None else None,
            "short_interest_pct": (float(info.get("shortPercentOfFloat")) * 100) if info.get("shortPercentOfFloat") is not None else None,
            "institutional_ownership": (float(info.get("heldPercentInstitutions")) * 100) if info.get("heldPercentInstitutions") is not None else None,
            "data_date": datetime.now().strftime("%Y-%m-%d")
        })
    except Exception as e:
        logger.warning(f"Failed to fetch analyst data for {ticker}: {e}")
        return json.dumps({
            "analyst_consensus_rating": None, "analyst_price_target": None, "num_analysts_covering": None,
            "short_interest_pct": None, "institutional_ownership": None,
            "data_date": datetime.now().strftime("%Y-%m-%d")
        })

@mcp.tool()
def get_earnings_surprise_history(ticker: str) -> str:
    """Fetch the last 4 quarters of earnings surprise history."""
    try:
        RateLimiter.wait()
        t = yf.Ticker(ticker, session=yf_session)
        
        # yfinance earnings_dates contains surprise data
        earnings = t.earnings_dates
        quarters = []
        if earnings is not None and not earnings.empty:
            # Drop rows with NaN in Reported EPS or Estimate
            earnings = earnings.dropna(subset=['Reported EPS', 'EPS Estimate'])
            # Sort by date descending
            earnings = earnings.sort_index(ascending=False).head(4)
            
            for date_idx, row in earnings.iterrows():
                rep = row.get("Reported EPS")
                est = row.get("EPS Estimate")
                surp = row.get("Surprise(%)")
                
                # Format quarter_label nicely (e.g. Q2_2026). Approx based on date.
                q = (date_idx.month - 1) // 3 + 1
                q_label = f"Q{q}_{date_idx.year}"
                
                # Sometimes yfinance surprise is 0.04 meaning 4%, sometimes 4.0 meaning 400%.
                # Usually it's in ratio. We calculate it manually to be safe.
                if rep is not None and est is not None and est != 0:
                    surprise_pct = ((rep - est) / abs(est)) * 100
                else:
                    surprise_pct = None
                    
                quarters.append({
                    "quarter_label": q_label,
                    "reported_eps": float(rep) if rep is not None else None,
                    "estimated_eps": float(est) if est is not None else None,
                    "surprise_pct": float(surprise_pct) if surprise_pct is not None else None
                })
                
        return json.dumps({
            "quarters": quarters,
            "data_date": datetime.now().strftime("%Y-%m-%d")
        })
    except Exception as e:
        logger.warning(f"Failed to fetch earnings surprise for {ticker}: {e}")
        return json.dumps({"quarters": [], "data_date": datetime.now().strftime("%Y-%m-%d")})

if __name__ == "__main__":
    mcp.run()
