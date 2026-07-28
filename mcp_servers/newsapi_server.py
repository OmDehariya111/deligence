import json
import logging
import os
import hashlib
import time
from datetime import datetime, timedelta
import httpx
from fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("newsapi-server")

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "b3bf6b3890de4c2683bd146951311f5a")
CACHE_DIR = r"c:\Deligence\.cache\newsapi"
QUOTA_FILE = os.path.join(CACHE_DIR, "quota.json")

# Ensure cache dir exists
os.makedirs(CACHE_DIR, exist_ok=True)

def _get_cache_key(query: str, from_date: str, to_date: str) -> str:
    raw = f"{query}_{from_date}_{to_date}"
    return hashlib.md5(raw.encode()).hexdigest()

def _check_quota() -> bool:
    if not os.path.exists(QUOTA_FILE):
        return False
    try:
        with open(QUOTA_FILE, "r") as f:
            data = json.load(f)
        today_str = datetime.now().strftime("%Y-%m-%d")
        if data.get("date") == today_str and data.get("count", 0) >= 95:
            return True
    except Exception:
        pass
    return False

def _increment_quota():
    today_str = datetime.now().strftime("%Y-%m-%d")
    data = {"date": today_str, "count": 0}
    if os.path.exists(QUOTA_FILE):
        try:
            with open(QUOTA_FILE, "r") as f:
                old_data = json.load(f)
            if old_data.get("date") == today_str:
                data["count"] = old_data.get("count", 0)
        except Exception:
            pass
    data["count"] += 1
    with open(QUOTA_FILE, "w") as f:
        json.dump(data, f)

@mcp.tool()
def get_company_news(query: str, from_date: str, to_date: str) -> str:
    """Fetch company news using NewsAPI with 24-hour caching."""
    cache_key = _get_cache_key(query, from_date, to_date)
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    # Check cache (24 hours)
    if os.path.exists(cache_path):
        mtime = os.path.getmtime(cache_path)
        age_hours = (time.time() - mtime) / 3600
        if age_hours < 24:
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                cached_data["served_from_cache"] = True
                cached_data["cache_age_hours"] = age_hours
                cached_data["quota_exhausted"] = False
                return json.dumps(cached_data)
            except Exception:
                pass
                
    if _check_quota():
        return json.dumps({
            "articles": [],
            "quota_exhausted": True,
            "served_from_cache": False,
            "cache_age_hours": None
        })

    try:
        # We use everything endpoint
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "from": from_date,
            "to": to_date,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 100,
            "apiKey": NEWSAPI_KEY
        }
        
        response = httpx.get(url, params=params, timeout=10.0)
        _increment_quota()
        
        if response.status_code == 426: # API limits / Upgrade Required (free tier limit reached, e.g. >30 days)
            return json.dumps({
                "articles": [],
                "quota_exhausted": True, # treat as exhausted so it falls back to web search
                "served_from_cache": False,
                "cache_age_hours": None,
                "error": "Plan upgrade required (likely requested >30 days history)"
            })
            
        response.raise_for_status()
        data = response.json()
        
        articles = []
        for a in data.get("articles", []):
            articles.append({
                "headline": a.get("title", ""),
                "description": a.get("description", ""),
                "source_name": a.get("source", {}).get("name", ""),
                "published_date": a.get("publishedAt", ""),
                "url": a.get("url", "")
            })
            
        result = {
            "articles": articles,
            "quota_exhausted": False,
            "served_from_cache": False,
            "cache_age_hours": None
        }
        
        # Save cache
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f)
            
        return json.dumps(result)
        
    except Exception as e:
        logger.warning(f"Failed to fetch news for query '{query}': {e}")
        # If failure is 429 quota, pretend quota exhausted
        if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429:
            return json.dumps({
                "articles": [],
                "quota_exhausted": True,
                "served_from_cache": False,
                "cache_age_hours": None
            })
            
        return json.dumps({
            "articles": [],
            "quota_exhausted": False,
            "served_from_cache": False,
            "cache_age_hours": None,
            "error": str(e)
        })

if __name__ == '__main__':
    mcp.run()

