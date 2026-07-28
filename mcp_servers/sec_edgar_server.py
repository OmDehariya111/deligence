import asyncio
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

import httpx
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastmcp import FastMCP

from schemas.pydantic_models import (
    CompanyIdentity,
    CompanySubmissionsResult,
    FilingRecord,
    TickerResolutionResult,
)

logger = logging.getLogger(__name__)

# Initialize the FastMCP server
mcp = FastMCP("sec-edgar-server")

# SEC API limits us to 10 requests per second.
# We enforce a 100ms minimum gap between requests across this server.
_sec_request_lock = threading.Lock()
_last_request_time = 0.0

# User-Agent required by SEC
SEC_USER_AGENT = "DeligenX iitisoc2026@iiti.ac.in"


def _enforce_rate_limit() -> None:
    """Ensure at least 100ms has passed since the last SEC API request."""
    global _last_request_time
    with _sec_request_lock:
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < 0.100:
            time.sleep(0.100 - elapsed)
        _last_request_time = time.time()


def _make_sec_request(url: str, max_retries: int = 3) -> httpx.Response:
    """Make an HTTP GET request to the SEC API with rate limiting and retries.
    
    Raises:
        httpx.HTTPError if the request fails after max_retries.
    """
    headers = {"User-Agent": SEC_USER_AGENT}
    
    # We use a synchronous client since FastMCP tools are synchronous.
    with httpx.Client(headers=headers, timeout=10.0, follow_redirects=True) as client:
        for attempt in range(max_retries + 1):
            _enforce_rate_limit()
            try:
                response = client.get(url)
                response.raise_for_status()
                return response
            except httpx.HTTPError as e:
                if attempt == max_retries:
                    logger.error(f"Failed to fetch {url} after {max_retries} retries: {e}")
                    raise
                
                # Exponential backoff: 0.5s, 1s, 2s
                backoff_time = 0.5 * (2 ** attempt)
                logger.warning(f"Transient error fetching {url}: {e}. Retrying in {backoff_time}s...")
                time.sleep(backoff_time)
                
    raise RuntimeError("Unreachable")


@mcp.tool()
def resolve_ticker_to_cik(ticker: str) -> str:
    """Resolve a stock ticker to a CIK, returning a JSON-serialized TickerResolutionResult."""
    ticker_upper = ticker.upper().strip()
    url = "https://www.sec.gov/files/company_tickers.json"
    
    try:
        response = _make_sec_request(url)
        data = response.json()
    except Exception as e:
        # On final failure, return found=false gracefully per spec (G-6 pattern)
        logger.error(f"Error fetching ticker mapping: {e}")
        return TickerResolutionResult(found=False).model_dump_json()

    # The SEC JSON has the structure:
    # {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, "1": ...}
    for _, company_info in data.items():
        if company_info["ticker"].upper() == ticker_upper:
            # SEC strips leading zeros from CIKs in this file, we must pad to 10 digits
            cik_str = str(company_info["cik_str"]).zfill(10)
            result = TickerResolutionResult(
                found=True,
                cik=cik_str,
                company_name=company_info["title"],
                ticker_matched=company_info["ticker"]
            )
            return result.model_dump_json()

    return TickerResolutionResult(found=False).model_dump_json()


def _parse_fiscal_year_end(fye: str) -> tuple[str, int]:
    """Parse '0930' into ('0930', 9). Return ('1231', 12) on failure."""
    if not fye or len(fye) != 4:
        return ("1231", 12)
    try:
        month = int(fye[:2])
        return (fye, month)
    except ValueError:
        return ("1231", 12)

@mcp.tool()
def get_company_tickers() -> str:
    """Fetch and return the SEC company_tickers.json mapping.
    
    Returns a JSON string of the raw SEC tickers mapping which maps CIK to Ticker and Company Title.
    """
    url = "https://www.sec.gov/files/company_tickers.json"
    try:
        response = _make_sec_request(url)
        return json.dumps(response.json())
    except Exception as e:
        logger.error(f"Error fetching ticker mapping: {e}")
        return json.dumps({})


@mcp.tool()
def get_company_submissions(cik: str) -> str:
    """Fetch company identity and submission history, returning a JSON-serialized CompanySubmissionsResult.
    
    Returns a string containing {"success": false, "error_reason": "..."} on outright failure.
    """
    cik = cik.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    
    try:
        response = _make_sec_request(url)
        data = response.json()
    except Exception as e:
        return json.dumps({"success": False, "error_reason": str(e)})

    fye_str, fye_month = _parse_fiscal_year_end(data.get("fiscalYearEnd", "1231"))

    identity = CompanyIdentity(
        company_name=data.get("name", "Unknown"),
        cik=cik,
        sic_code=data.get("sic", "Unknown"),
        industry_name=data.get("sicDescription", "Unknown"),
        exchange=data.get("exchanges", [None])[0] if data.get("exchanges") else None,
        state_of_incorp=data.get("stateOfIncorporation", None),
        fiscal_year_end=fye_str,
        fiscal_year_end_month=fye_month
    )

    filings_list: List[FilingRecord] = []
    recent_filings = data.get("filings", {}).get("recent", {})
    
    if recent_filings:
        # SEC provides column-based arrays: "form", "filingDate", "accessionNumber"
        forms = recent_filings.get("form", [])
        dates = recent_filings.get("filingDate", [])
        accessions = recent_filings.get("accessionNumber", [])
        
        # Zip them together safely
        count = min(len(forms), len(dates), len(accessions))
        for i in range(count):
            filings_list.append(FilingRecord(
                form=forms[i],
                filing_date=dates[i],
                accession_number=accessions[i]
            ))

    # Stitch paginated older filings if present
    # The 'files' array looks like: [{"name": "CIK0000320193-submissions-001.json", "filingCount": 2000}]
    paginated_files = data.get("filings", {}).get("files", [])
    for file_info in paginated_files:
        filename = file_info.get("name")
        if filename:
            page_url = f"https://data.sec.gov/submissions/{filename}"
            try:
                page_resp = _make_sec_request(page_url)
                page_data = page_resp.json()
                
                p_forms = page_data.get("form", [])
                p_dates = page_data.get("filingDate", [])
                p_accessions = page_data.get("accessionNumber", [])
                p_count = min(len(p_forms), len(p_dates), len(p_accessions))
                
                for i in range(p_count):
                    filings_list.append(FilingRecord(
                        form=p_forms[i],
                        filing_date=p_dates[i],
                        accession_number=p_accessions[i]
                    ))
            except Exception as e:
                logger.warning(f"Failed to fetch paginated submissions {filename}: {e}")
                # Continue with what we have

    result = CompanySubmissionsResult(
        company_identity=identity,
        filings=filings_list
    )
    return result.model_dump_json()


@mcp.tool()
def get_filing_document(cik: str, accession_number: str) -> str:
    """Fetch the main document HTML for a given filing, returning JSON.
    
    Returns JSON:
    {"success": true, "accession_number": "...", "main_document_filename": "...", "html_content": "..."}
    or {"success": false, "error_reason": "..."}
    """
    cik = cik.zfill(10)
    accession_no_dash = accession_number.replace("-", "")
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dash}/index.json"
    
    try:
        index_resp = _make_sec_request(index_url)
        index_data = index_resp.json()
    except Exception as e:
        return json.dumps({"success": False, "error_reason": f"Failed to fetch index: {e}"})

    # Find the main document
    try:
        files = index_data.get("directory", {}).get("item", [])
        main_file = None
        
        # Filter candidate HTM/HTML files
        candidates_htm = []
        for item in files:
            name = item.get("name", "")
            lower_n = name.lower()
            if "index" in lower_n or lower_n.startswith("r"): continue
            if "ex-" in lower_n or "ex10" in lower_n or "ex23" in lower_n or "ex97" in lower_n: continue
            if lower_n.endswith(".htm") or lower_n.endswith(".html"):
                size = item.get("size")
                try:
                    size_val = int(size) if size is not None else 0
                except (ValueError, TypeError):
                    size_val = 0
                candidates_htm.append((name, size_val))
                
        if candidates_htm:
            candidates_htm.sort(key=lambda x: x[1], reverse=True)
            main_file = candidates_htm[0][0]
            logger.info(f"Selected main document by size: {main_file} ({candidates_htm[0][1]} bytes)")
            
        if not main_file:
            # Fallback to TXT files
            candidates_txt = []
            for item in files:
                name = item.get("name", "")
                lower_n = name.lower()
                if "index" in lower_n or lower_n.startswith("r"): continue
                if "ex-" in lower_n or "ex10" in lower_n or "ex23" in lower_n or "ex97" in lower_n: continue
                if lower_n.endswith(".txt"):
                    size = item.get("size")
                    try:
                        size_val = int(size) if size is not None else 0
                    except (ValueError, TypeError):
                        size_val = 0
                    candidates_txt.append((name, size_val))
            if candidates_txt:
                candidates_txt.sort(key=lambda x: x[1], reverse=True)
                main_file = candidates_txt[0][0]
                logger.info(f"Selected main document fallback by size: {main_file} ({candidates_txt[0][1]} bytes)")
        
        if not main_file:
            return json.dumps({"success": False, "error_reason": "No HTM or TXT document found in filing index"})
            
        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dash}/{main_file}"
        doc_resp = _make_sec_request(doc_url)
        html_content = doc_resp.text
        
        return json.dumps({
            "success": True,
            "accession_number": accession_number,
            "main_document_filename": main_file,
            "html_content": html_content,
            "retrieved_from_cache": False
        })
    except Exception as e:
        return json.dumps({"success": False, "error_reason": str(e)})


@mcp.tool()
def get_proxy_statement(cik: str) -> str:
    """Fetch the most recent DEF 14A proxy statement for a company, returning JSON.
    
    Returns JSON:
    {"found": true, "accession_number": "...", "main_document_filename": "...", "html_content": "..."}
    or {"found": false, "error_reason": "..."}
    """
    submissions_json = get_company_submissions(cik)
    submissions_data = json.loads(submissions_json)
    
    if "company_identity" not in submissions_data:
        return json.dumps({"found": False, "error_reason": "Failed to fetch company submissions"})
        
    filings = submissions_data.get("filings", [])
    def_14a_acc = None
    for f in filings:
        if f["form"] == "DEF 14A":
            def_14a_acc = f["accession_number"]
            break
            
    if not def_14a_acc:
        return json.dumps({"found": False, "error_reason": "No DEF 14A found in filing history"})
        
    doc_json = get_filing_document(cik, def_14a_acc)
    doc_data = json.loads(doc_json)
    
    if doc_data.get("success"):
        return json.dumps({
            "found": True,
            "accession_number": def_14a_acc,
            "main_document_filename": doc_data["main_document_filename"],
            "html_content": doc_data["html_content"]
        })
    else:
        return json.dumps({
            "found": False,
            "error_reason": doc_data.get("error_reason", "Failed to fetch proxy document")
        })

@mcp.tool()
def get_company_facts(cik: str) -> str:
    """
    Fetch the complete XBRL CompanyFacts for a given CIK.
    """
    if not cik or cik == "0000000000":
        return json.dumps({"success": False, "error_reason": "Invalid CIK"})
        
    cik_str = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_str}.json"
    
    try:
        response = _make_sec_request(url)
        data = response.json()
        return json.dumps({
            "success": True,
            "facts": data.get("facts", {})
        })
    except Exception as e:
        logger.error(f"Error fetching CompanyFacts for CIK {cik}: {e}")
        return json.dumps({"success": False, "error_reason": str(e)})

_frames_cache = {}
_cache_time = {}

@mcp.tool()
def get_frames_data(tag: str, unit: str, period: str) -> str:
    """Fetch frames data for a specific tag, unit, and period. Cached for 24h."""
    cache_key = f"{tag}_{unit}_{period}"
    now = time.time()
    if cache_key in _frames_cache and (now - _cache_time.get(cache_key, 0)) < 86400:
        return _frames_cache[cache_key]
        
    url = f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/{unit}/{period}.json"
    
    try:
        response = _make_sec_request(url)
        data = response.json()
        
        parsed_data = []
        for item in data.get("data", []):
            parsed_data.append({
                "cik": item.get("cik"),
                "entity_name": item.get("entityName"),
                "ticker": None,
                "value": item.get("val")
            })
            
        result = json.dumps({
            "tag": tag,
            "unit": unit,
            "period": period,
            "status": "OK",
            "data": parsed_data,
            "error_message": None
        })
        _frames_cache[cache_key] = result
        _cache_time[cache_key] = now
        return result
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            result = json.dumps({
                "tag": tag,
                "unit": unit,
                "period": period,
                "status": "NO_DATA",
                "data": [],
                "error_message": None
            })
            _frames_cache[cache_key] = result
            _cache_time[cache_key] = now
            return result
        
        return json.dumps({
            "tag": tag,
            "unit": unit,
            "period": period,
            "status": "ERROR",
            "data": [],
            "error_message": str(e)
        })
    except Exception as e:
        return json.dumps({
            "tag": tag,
            "unit": unit,
            "period": period,
            "status": "ERROR",
            "data": [],
            "error_message": str(e)
        })

@mcp.tool()
def get_sic_mapping() -> str:
    """Returns the CIK to SIC mapping from a pre-built offline file."""
    import os
    mapping_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sic_mapping.json")
    if os.path.exists(mapping_path):
        with open(mapping_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)
            return json.dumps({"mapping": mapping})
    return json.dumps({"mapping": {}})

if __name__ == "__main__":
    mcp.run()
