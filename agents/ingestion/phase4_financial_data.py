"""Phase 4: Financial Data Collection."""
# Ye phase Ingestion Agent ka sabse mathematical aur data-heavy part hai.
# Iska main object SEC ki XBRL API (CompanyFacts) se company ke pichle 5 saal ke 
# saare financial numbers (Revenue, Net Income, Debt etc) nikalna hai, aur Market Data 
# (yfinance) se stock price lakar unhe ek solid pydantic model me pack karna hai.

import json
import logging
from pathlib import Path

from utils.mcp_client import call_mcp_tool_sync
from utils.audit_logger import log_audit_event
from utils.financial_extractor import FinancialExtractor
from agents.ingestion.phase1_company_identity import Phase1Result
from schemas.pydantic_models import CompanyFinancialHistory, AnnualFinancials

logger = logging.getLogger(__name__)

def run_phase4(phase1_result: Phase1Result, ticker: str, run_id: str, paths: dict[str, Path]) -> CompanyFinancialHistory:
    """Run Phase 4 financial data collection."""
    ticker = ticker.upper().strip()
    
    log_audit_event(
        paths["AUDIT_LOG_PATH"],
        agent="IngestionAgent",
        module="PHASE_4_FINANCIAL_DATA",
        status="STARTED",
        summary=f"Beginning financial data collection for {ticker}"
    )

    cik = phase1_result.company_identity.cik
    company_name = phase1_result.company_identity.company_name
    
    try:
        # Step 1: SEC XBRL API Call
        # sec_edgar_server se company ki saari raw numeric history mangwate hain
        facts_json = call_mcp_tool_sync("mcp_servers/sec_edgar_server.py", "get_company_facts", {"cik": cik})
        if isinstance(facts_json, str):
            facts_data = json.loads(facts_json)
        else:
            facts_data = facts_json
        
        if not facts_data.get("success", True) or "facts" not in facts_data:
            raise ValueError(f"CompanyFacts data unavailable for this company. Error: {facts_data.get('error_reason')}")
            
        # Step 2: FinancialExtractor Initialization
        # Ye extractor us huge JSON (facts_data) ko parse karne ka magic karta hai
        extractor = FinancialExtractor(facts_data, phase1_result.company_identity.fiscal_year_end)
        
        # Check karta hai ki kaun se saalon (years) ka data maujood hai (Top 5 recent years)
        available_years = extractor.get_available_years()
        
        if not available_years:
            raise ValueError("No annual financial data found for this company.")
            
        # Step 3: Har saal ka data ek-ek karke extract karna
        annual_financials = []
        for year in available_years:
            fin_data = extractor.extract_year(year) # Ye Pydantic model (AnnualFinancials) return karta hai
            annual_financials.append(fin_data)
            
        # Step 4: Market Data (Beta)
        # market_data_server (yfinance) se company ka market risk indicator (Beta) nikalte hain
        profile_json = call_mcp_tool_sync("mcp_servers/market_data_server.py", "get_company_market_profile", {"ticker": ticker})
        if isinstance(profile_json, str):
            profile_data = json.loads(profile_json)
        else:
            profile_data = profile_json
        beta = profile_data.get("beta")
        
        # Step 5: Market Data (Historical Stock Price & Market Cap)
        # Har extracted saal ke liye us saal ke aakhri din (Fiscal Year End) ka stock price nikalna
        for fin in annual_financials:
            fy_end_str = phase1_result.company_identity.fiscal_year_end
            
            if fy_end_str and len(fy_end_str) == 4:
                # String "1231" ko "2024-12-31" me convert karte hain
                date_str = f"{fin.fiscal_year}-{fy_end_str[:2]}-{fy_end_str[2:]}"
                
                # MCP call to get historical price on that exact date (or closest trading day)
                price_json = call_mcp_tool_sync("mcp_servers/market_data_server.py", "get_historical_close_price", {"ticker": ticker, "date": date_str})
                if isinstance(price_json, str):
                    price_data = json.loads(price_json)
                else:
                    price_data = price_json
                
                price = price_data.get("price")
                if price is not None:
                    # Price mil gaya toh model me save karke uska Metadata source "yfinance" mark karte hain
                    fin.stock_price_fy_end = price
                    extractor.field_metadata["stock_price_fy_end"][fin.fiscal_year] = {"source": "yfinance"}
                    
                    # Agar SEC se shares_outstanding mil gaya tha, toh Market Cap mathematically calculate kar lete hain
                    if fin.shares_outstanding is not None:
                        fin.market_cap = price * fin.shares_outstanding
                        extractor.field_metadata["market_cap"][fin.fiscal_year] = {
                            "source": "computed", 
                            "computation_method": "stock_price_fy_end * shares_outstanding"
                        }
            else:
                logger.warning(f"Invalid fiscal_year_end format '{fy_end_str}' for {ticker}")

        # Step 6: Final Packaging
        # Saare saalon ka data aur unka metadata ek single bade object me pack karke return karna
        history = CompanyFinancialHistory(
            ticker=ticker,
            cik=cik,
            company_name=company_name,
            beta=beta,
            annual_data=annual_financials,
            field_metadata=extractor.field_metadata
        )
        
        log_audit_event(
            paths["AUDIT_LOG_PATH"],
            agent="IngestionAgent",
            module="PHASE_4_FINANCIAL_DATA",
            status="COMPLETED",
            summary=f"Extracted {len(available_years)} years of financial data."
        )
        
        return history
        
    except Exception as e:
        log_audit_event(
            paths["AUDIT_LOG_PATH"],
            agent="IngestionAgent",
            module="PHASE_4_FINANCIAL_DATA",
            status="FAILED",
            summary=f"Error extracting financial data: {e}"
        )
        raise e
