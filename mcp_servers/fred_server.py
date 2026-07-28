import json
import logging
import os
import httpx
from fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("fred-server")

FRED_API_KEY = os.environ.get("FRED_API_KEY", "1a1a852e0ea1271b6ebd569feca37f0a")

@mcp.tool()
def get_fred_series(series_id: str, limit: int = 37) -> str:
    """Fetch macro indicator data from FRED API."""
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit
        }
        
        response = httpx.get(url, params=params, timeout=10.0)
        
        if response.status_code == 404:
            return json.dumps({
                "series_id": series_id,
                "status": "NOT_FOUND",
                "observations": [],
                "error_reason": "Series ID not found on FRED"
            })
            
        response.raise_for_status()
        data = response.json()
        
        observations = []
        for obs in data.get("observations", []):
            observations.append({
                "date": obs.get("date"),
                "value": obs.get("value")
            })
            
        return json.dumps({
            "series_id": series_id,
            "status": "OK",
            "observations": observations,
            "error_reason": None
        })
        
    except Exception as e:
        logger.warning(f"Failed to fetch FRED series '{series_id}': {e}")
        return json.dumps({
            "series_id": series_id,
            "status": "ERROR",
            "observations": [],
            "error_reason": str(e)
        })

if __name__ == '__main__':
    mcp.run()

