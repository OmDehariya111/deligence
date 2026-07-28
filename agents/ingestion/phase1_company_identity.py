import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from utils.mcp_client import call_mcp_tool_sync
from schemas.pydantic_models import (
    CompanyIdentity,
    CompanySubmissionsResult,
    FilingRecord,
    IngestionSummaryError,
    SelectedFilings,
    TickerResolutionResult,
)
from utils.audit_logger import log_audit_event


class Phase1Error(Exception):
    """Raised when Phase 1 encounters a fatal error (e.g., invalid ticker)."""
    pass


def _now_iso() -> str:
    # Ye function current time ko UTC mein leta hai aur standard ISO 8601 format (Z ending) mein return karta hai.
    # Iska use timestamps generate karne ke liye hota hai taaki logs aur cache files me exact time record ho sake.
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _check_cache(ticker: str, cache_dir: Path) -> tuple[Optional[CompanyIdentity], Optional[SelectedFilings]]:
    """Check TICKER_CACHE_DIR for a recent Phase 1 result."""
    # Ye function dekhta hai ki kya hamne is ticker (jaise AAPL, MSFT) ka data pehle fetch karke save kiya hua hai.
    # Agar cache file milti hai, toh ye baar-baar SEC EDGAR API ko hit karne se bachata hai (time aur rate limits bachata hai).
    cache_file = cache_dir / f"{ticker.upper()}_phase1.json"
    if not cache_file.exists():
        return None, None

    try:
        data = json.loads(cache_file.read_text())
        cached_time_str = data.get("timestamp")
        if not cached_time_str:
            return None, None
            
        cached_time = datetime.fromisoformat(cached_time_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        
        # 7-day TTL (Time-To-Live): Agar cache file 7 din se zyada purani hai, toh hum use discard kar denge (fresh data layenge).
        if now - cached_time > timedelta(days=7):
            return None, None
            
        # Pydantic models (CompanyIdentity aur SelectedFilings) ka use karke json data ko validate aur convert kar rahe hain.
        identity = CompanyIdentity.model_validate(data["company_identity"])
        selected = SelectedFilings.model_validate(data["selected_filings"])
        return identity, selected
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Agar cache file kharab (corrupt) ya invalid ho, toh None return kar do taaki system automatically fresh fetch kar le.
        return None, None


def _write_cache(ticker: str, cache_dir: Path, identity: CompanyIdentity, selected: SelectedFilings) -> None:
    # Jab hum fresh SEC data fetch kar lete hain, toh is function ke through hum use save (cache) kar lete hain.
    # Isse aage ke test runs ya dusre agents ko data turant mil jata hai.
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{ticker.upper()}_phase1.json"
    data = {
        "timestamp": _now_iso(),
        "company_identity": identity.model_dump(),
        "selected_filings": selected.model_dump()
    }
    cache_file.write_text(json.dumps(data, indent=2))


def _filter_filings(filings: list[FilingRecord]) -> SelectedFilings:
    """Filter to 3 most recent 10-K, all 8-K from last 2 years, most recent DEF 14A, and recent 10-Q."""
    # Ye bohot important function hai! SEC SEC EDGAR par kisi company ke hazaro documents hote hain.
    # Ye function filter karke sirf kaam ke documents (10-K, 10-Q, 8-K, DEF 14A) ko select karta hai
    # Taki humara vector database faltu data se na bhar jaye.
    ten_k_list = []
    eight_k_list = []
    def_14a_list = []
    ten_q_list = []
    
    now = datetime.now(timezone.utc)
    two_years_ago = now - timedelta(days=2 * 365) # Last 2 saal ki date nikal rahe hain
    
    # Har ek record par check lag raha hai
    for record in filings:
        if record.form == "10-K":
            ten_k_list.append(record)
        elif record.form == "8-K":
            # 8-K (Current Reports) bohot aate hain, isliye hum sirf pichle 2 saal ke 8-K hi lete hain
            try:
                filing_date = datetime.strptime(record.filing_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if filing_date >= two_years_ago:
                    eight_k_list.append(record)
            except ValueError:
                pass
        elif record.form == "DEF 14A": # Proxy Statement (Board of directors etc ki details)
            def_14a_list.append(record)
        elif record.form == "10-Q": # Quarterly reports
            ten_q_list.append(record)
            
    # Sabko nayi dates se purani dates ke order (descending) mein sort kar rahe hain
    ten_k_list.sort(key=lambda x: x.filing_date, reverse=True)
    eight_k_list.sort(key=lambda x: x.filing_date, reverse=True)
    def_14a_list.sort(key=lambda x: x.filing_date, reverse=True)
    ten_q_list.sort(key=lambda x: x.filing_date, reverse=True)
    
    # Hum sirf wahi 10-Q reports lenge jo sabse recent 10-K aane ke BAAD file hui ho (yani current uncompleted year ki).
    selected_ten_q = []
    if ten_k_list:
        most_recent_10k_date_str = ten_k_list[0].filing_date
        try:
            most_recent_10k_date = datetime.strptime(most_recent_10k_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            for q_rec in ten_q_list:
                q_date = datetime.strptime(q_rec.filing_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if q_date > most_recent_10k_date:
                    selected_ten_q.append(q_rec)
        except ValueError:
            pass
            
    # Selected data ko SelectedFilings schema object mein pack karke return kar rahe hain.
    # 10-K sirf top 3 lenge (pichle 3 saal), DEF 14A sirf 1 (latest).
    return SelectedFilings(
        ten_k=ten_k_list[:3],
        eight_k=eight_k_list,
        def_14a=def_14a_list[0] if def_14a_list else None,
        ten_q=selected_ten_q
    )


class Phase1Result:
    # Ye ek chota wrapper class hai jo phase 1 ke results hold karta hai aur next phase (Phase 2, 4) ko pass karta hai.
    def __init__(self, company_identity: CompanyIdentity, selected_filings: SelectedFilings, cik: str):
        self.company_identity = company_identity
        self.selected_filings = selected_filings
        self.cik = cik


def run_phase1(ticker: str, run_id: str, paths: dict[str, Path], force_refresh: bool = False) -> Phase1Result:
    """
    Run Phase 1: Company Identity Resolution.
    Resolves the ticker, fetches submissions, selects filings, and caches the result.
    """
    # Ye Phase 1 ka sabse main (entry) function hai. Jab ingestion start hota hai toh sabse pehle yahi call hota hai.
    # Iska kaam hai user dwara diye gaye Ticker (eg. AAPL) ko SEC EDGAR par dhundna aur verify karna.
    
    ticker_upper = ticker.upper().strip()
    audit_log_path = paths["AUDIT_LOG_PATH"]
    ticker_cache_dir = paths["TICKER_CACHE_DIR"]
    ingestion_summary_path = paths["INGESTION_SUMMARY_PATH"]
    
    # Process start hone par audit log file mein entry kar rahe hain.
    log_audit_event(
        audit_log_path=audit_log_path,
        agent="IngestionAgent",
        module="PHASE_1_COMPANY_IDENTITY",
        status="STARTED",
        summary=f"Resolving ticker {ticker_upper} for run {run_id}."
    )
    
    # 1. Sabse pehle cache check karte hain, agar valid aur recent file mili to time bach jayega!
    if not force_refresh:
        cached_identity, cached_selected = _check_cache(ticker_upper, ticker_cache_dir)
        if cached_identity and cached_selected:
            log_audit_event(
                audit_log_path=audit_log_path,
                agent="IngestionAgent",
                module="PHASE_1_COMPANY_IDENTITY",
                status="COMPLETED",
                summary=f"Loaded identity for {cached_identity.company_name} from cache."
            )
            return Phase1Result(cached_identity, cached_selected, cached_identity.cik)

    # 2. Agar cache mein nahi mila, toh MCP Server (sec_edgar_server) ke through Ticker se CIK (Central Index Key) nikalenge.
    # CIK ek 10-digit unique ID hoti hai jo har public US company ko SEC dwara di jati hai.
    resolve_json = call_mcp_tool_sync("mcp_servers/sec_edgar_server.py", "resolve_ticker_to_cik", {"ticker": ticker_upper})
    
    if isinstance(resolve_json, str):
        resolve_result = TickerResolutionResult.model_validate_json(resolve_json)
    else:
        resolve_result = TickerResolutionResult.model_validate(resolve_json)
    
    # Agar company SEC EDGAR (US database) par mili hi nahi...
    if not resolve_result.found or not resolve_result.cik:
        # Fatal Error Path (G-6 pattern): Humne ek proper format mein error gracefully raise ki hai.
        reason = f"Company not found in SEC EDGAR for ticker {ticker_upper}. DeligenX currently supports US public companies only."
        
        # System ko samjhane ke liye output folder mein ek error JSON file bana di jati hai.
        error_summary = IngestionSummaryError(
            run_id=run_id,
            status="ERROR",
            reason=reason,
            ticker_provided=ticker_upper,
            module_status={
                "phase_1_company_identity": "FAILED",
                "phase_2_text_processing": "NOT_STARTED",
                "phase_3_user_file": "NOT_STARTED",
                "phase_4_financial_data": "NOT_STARTED",
                "phase_5_validation": "NOT_STARTED",
                "phase_6_normalization": "NOT_STARTED"
            },
            ingestion_timestamp=_now_iso()
        )
        ingestion_summary_path.write_text(error_summary.model_dump_json(indent=2))
        
        log_audit_event(
            audit_log_path=audit_log_path,
            agent="IngestionAgent",
            module="PHASE_1_COMPANY_IDENTITY",
            status="FAILED",
            summary=reason
        )
        
        raise Phase1Error(reason)
        
    cik = resolve_result.cik
    company_name = resolve_result.company_name
    
    # 3. Ticker sahi hai aur CIK mil gaya! Ab SEC EDGAR se us CIK ki poori "submission history" nikalenge.
    # Isme is company dwara aaj tak file kiye gaye saare documents ki ek lambi list hoti hai.
    submissions_json = call_mcp_tool_sync("mcp_servers/sec_edgar_server.py", "get_company_submissions", {"cik": cik})
    
    # BUGS FIX: Yahan pehle unwanted string conversion aur re-parsing ho rahi thi, maine isse clean karke direct dict validaton daal diya hai.
    if isinstance(submissions_json, str):
        submissions_dict = json.loads(submissions_json)
    else:
        submissions_dict = submissions_json
        
    # Agar SEC API fail hui (e.g. rate limit, ya server down)
    if "success" in submissions_dict and not submissions_dict["success"]:
        reason = f"Failed to fetch submissions for CIK {cik}: {submissions_dict.get('error_reason')}"
        log_audit_event(
            audit_log_path=audit_log_path,
            agent="IngestionAgent",
            module="PHASE_1_COMPANY_IDENTITY",
            status="FAILED",
            summary=reason
        )
        raise Phase1Error(reason)
        
    # Dictionary object ko validate karke CompanySubmissionsResult model banayenge
    submissions_result = CompanySubmissionsResult.model_validate(submissions_dict)
    
    identity = submissions_result.company_identity
    
    # 4. Ab us hazaro documents ki lambi list me se sirf important documents ko chhat (filter) kar nikalenge
    selected_filings = _filter_filings(submissions_result.filings)
    
    # 5. Future runs ke liye in saari useful filtered cheezo ko cache mein store karenge
    _write_cache(ticker_upper, ticker_cache_dir, identity, selected_filings)
    
    # Phase 1 effectively Pura (Completed) ho chuka hai! Audit log likh denge.
    log_audit_event(
        audit_log_path=audit_log_path,
        agent="IngestionAgent",
        module="PHASE_1_COMPANY_IDENTITY",
        status="COMPLETED",
        summary=f"Resolved {ticker_upper} to CIK {cik} ({identity.company_name}). Selected {len(selected_filings.ten_k)} 10-K, {len(selected_filings.ten_q)} 10-Q, {len(selected_filings.eight_k)} 8-K, {1 if selected_filings.def_14a else 0} DEF-14A."
    )
    
    # Is result object ko wapas return karenge taaki baaki pipeline (Phase 2 wagera) apna kaam shuru kar sakein!
    return Phase1Result(identity, selected_filings, cik)
