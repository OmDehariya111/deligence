import json
import logging
import os
from datetime import datetime, timedelta
import httpx
from fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("newsapi-server")

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "b3bf6b3890de4c2683bd146951311f5a")


@mcp.tool()
def get_company_news(query: str, from_date: str, to_date: str) -> str:
    """Fetch company news using NewsAPI. No caching — always fetches fresh data."""
    try:
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

        if response.status_code == 426:  # Free tier limit (>30 days history)
            return json.dumps({
                "articles": [],
                "quota_exhausted": True,
                "error": "Plan upgrade required (likely requested >30 days history)"
            })

        if response.status_code == 429:  # Rate limit hit
            return json.dumps({
                "articles": [],
                "quota_exhausted": True,
                "error": "NewsAPI rate limit reached"
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

        return json.dumps({
            "articles": articles,
            "quota_exhausted": False
        })

    except Exception as e:
        logger.warning(f"Failed to fetch news for query '{query}': {e}")

        if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429:
            return json.dumps({
                "articles": [],
                "quota_exhausted": True,
                "error": "NewsAPI rate limit reached"
            })

        return json.dumps({
            "articles": [],
            "quota_exhausted": False,
            "error": str(e)
        })


if __name__ == '__main__':
    mcp.run()
