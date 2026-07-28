import json
import logging
from typing import Any
from pathlib import Path

from schemas.pydantic_models import (
    BenchmarkOutput, BenchmarkMetric, PeerInfo, RatioRecord
)

# Ye script ek external SEC EDGAR aur Market Data MCP server ko call karti hai external data lane ke liye
from utils.mcp_client import call_mcp_tool_sync

logger = logging.getLogger(__name__)

class SectorBenchmarkEngine:
    def __init__(self, ticker: str, sic_code: str, industry: str, benchmark_year: int, target_ratios: list[RatioRecord]):
        # Yahan hum target company (jaise MSFT) ki details aur uske Module 1 se nikle hue apne ratios (target_ratios) store karte hain
        self.ticker = ticker.upper().strip()
        self.sic_code = sic_code.strip()
        self.industry = industry
        self.benchmark_year = benchmark_year
        self.target_ratios = {r.ratio_name: r for r in target_ratios if r.fiscal_year == benchmark_year}
        
    def run(self) -> dict[str, Any]:
        """Run sector benchmarking."""
        # Ye main function hai jo competitor dhoondne se lekar average nikalne tak sab karta hai
        logger.info(f"Running sector benchmarking for {self.ticker} in year {self.benchmark_year} under SIC {self.sic_code}")
        
        # 1. Load SIC mapping using the correct get_sic_mapping tool
        # Pehla step: SEC se saari companies ke SIC code (Industry code) ki dictionary (map) lana taaki hum competitors dhoond sakein
        try:
            tickers_resp = call_mcp_tool_sync("mcp_servers/sec_edgar_server.py", "get_sic_mapping", {})
            if isinstance(tickers_resp, str):
                tickers_resp = json.loads(tickers_resp)
        except Exception as e:
            logger.error(f"Failed to fetch SIC mapping: {e}")
            tickers_resp = {}
            
        sic_mapping = tickers_resp.get("mapping", {})
        
        # 2. Fetch Revenues frame to identify peers
        # Dusra step: Us saal ki sabhi companies ka Total Revenue lana. Hum competitors ko unke revenue size ke hisab se select karenge.
        target_year = self.benchmark_year
        try:
            rev_resp = call_mcp_tool_sync(
                "mcp_servers/sec_edgar_server.py", 
                "get_frames_data", 
                {"tag": "Revenues", "unit": "USD", "period": f"CY{target_year}"}
            )
            if isinstance(rev_resp, str):
                rev_resp = json.loads(rev_resp)
        except Exception as e:
            logger.error(f"Revenues frame query failed: {e}")
            rev_resp = {"status": "FAILED", "error_message": str(e)}
                
        # If CY{target_year} fails (e.g. 404 because year is not complete), try target_year - 1
        if rev_resp.get("status") != "OK":
            logger.info(f"CY{target_year} Revenues frame not found, trying fallback to CY{target_year-1}")
            target_year -= 1
            try:
                rev_resp = call_mcp_tool_sync(
                    "mcp_servers/sec_edgar_server.py", 
                    "get_frames_data", 
                    {"tag": "Revenues", "unit": "USD", "period": f"CY{target_year}"}
                )
                if isinstance(rev_resp, str):
                    rev_resp = json.loads(rev_resp)
            except Exception as e:
                logger.error(f"Fallback Revenues frame query failed: {e}")
                rev_resp = {"status": "FAILED", "error_message": str(e)}

        if rev_resp.get("status") != "OK":
            return {"status": "FAILED", "reason": f"Could not fetch Revenues frame: {rev_resp.get('error_message')}"}
            
        # Update benchmark_year if we had to fallback so subsequent fetches use the same year
        self.benchmark_year = target_year
            
        companies = rev_resp.get("data", [])
        # Sort by revenue descending (Jiska revenue sabse zyada hai wo upar aayega)
        companies.sort(key=lambda x: x.get("value", 0), reverse=True)
        
        peers = []
        fallback_count = 0
        max_fallbacks = 15  # Limit to prevent excessive API calls (Sirf top companies pe hi extra check lagana)
        
        # Har company ko check kar rahe hain ki wo hamari industry (SIC code) ki hai ya nahi
        for comp in companies:
            cik_str = str(comp["cik"]).zfill(10)
            if cik_str == "0000000000": 
                continue
            
            comp_sic = sic_mapping.get(cik_str)
            
            # Fallback for missing SIC in mapping
            if not comp_sic and fallback_count < max_fallbacks:
                try:
                    logger.info(f"CIK {cik_str} not in SIC mapping. Falling back to submissions resolution.")
                    sub_resp = call_mcp_tool_sync(
                        "mcp_servers/sec_edgar_server.py", 
                        "get_company_submissions", 
                        {"cik": cik_str}
                    )
                    if isinstance(sub_resp, str):
                        sub_data = json.loads(sub_resp)
                    else:
                        sub_data = sub_resp
                    
                    if sub_data and "company_identity" in sub_data:
                        comp_sic = sub_data["company_identity"].get("sic_code")
                        if comp_sic:
                            comp_sic = str(comp_sic).strip()
                            sic_mapping[cik_str] = comp_sic
                            fallback_count += 1
                except Exception as e:
                    logger.warning(f"Failed fallback SIC lookup for CIK {cik_str}: {e}")
            
            if comp_sic == self.sic_code and comp.get("entity_name", "").upper() != self.ticker:
                peers.append(comp)
                # Hum sirf top 20 competitors hi lenge warna API calls bahut zyada lag jayengi
                if len(peers) >= 20:
                    break
                    
        peer_ciks = {str(p["cik"]).zfill(10) for p in peers}
        
        if not peers:
            return {"status": "PARTIAL", "peer_count": 0, "reason": "No peers found for this SIC code in the Frames data."}
            
        logger.info(f"Found {len(peers)} peer companies for benchmarking.")
            
        # 3. Define metrics and tags (supporting fallback tags)
        instant_tags = {
            "Assets", "StockholdersEquity", "AssetsCurrent", "LiabilitiesCurrent",
            "LongTermDebtNoncurrent", "LongTermDebt", "DebtCurrent", "ShortTermBorrowings",
            "CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalentsFairValueDisclosure",
            "CashAndCashEquivalents"
        }
        
        # Collect all tags needed for standard queries
        standard_tags = {
            "GrossProfit", "OperatingIncomeLoss", "NetIncomeLoss", "ProfitLoss",
            "Assets", "StockholdersEquity", "AssetsCurrent", "LiabilitiesCurrent",
            "InterestExpense", "InterestExpenseDebt",
            "LongTermDebtNoncurrent", "LongTermDebt", "DebtCurrent", "ShortTermBorrowings",
            "NetCashProvidedByUsedInOperatingActivities", "PaymentsToAcquirePropertyPlantAndEquipment",
            "DepreciationDepletionAndAmortization", "Depreciation",
            "CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalentsFairValueDisclosure", "CashAndCashEquivalents",
            "Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet"
        }
        
        # 4. Fetch frames data for tags
        # Chotha step: Ab jo Top 20 peers mile hain, unke baki sabhi financial items (jaise Profit, Assets, Debt) API se mangwana
        frames_cache = {}
        for tag in standard_tags:
            # Point-in-time instant tags require CY{year}Q4I period format
            period_str = f"CY{self.benchmark_year}Q4I" if tag in instant_tags else f"CY{self.benchmark_year}"
            
            try:
                resp = call_mcp_tool_sync(
                    "mcp_servers/sec_edgar_server.py", 
                    "get_frames_data", 
                    {"tag": tag, "unit": "USD", "period": period_str}
                )
                if isinstance(resp, str):
                    resp = json.loads(resp)
            except Exception as e:
                logger.error(f"Error fetching frame for {tag}: {e}")
                resp = {"status": "ERROR"}
                    
            if resp.get("status") == "OK":
                frames_cache[tag] = {str(d["cik"]).zfill(10): d["value"] for d in resp.get("data", [])}
            else:
                frames_cache[tag] = {}
                
        # Fetch previous year revenues for YoY growth computation
        prev_rev_cache = {}
        for tag in ["Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet"]:
            try:
                resp = call_mcp_tool_sync(
                    "mcp_servers/sec_edgar_server.py", 
                    "get_frames_data", 
                    {"tag": tag, "unit": "USD", "period": f"CY{self.benchmark_year-1}"}
                )
                if isinstance(resp, str):
                    resp = json.loads(resp)
            except Exception as e:
                logger.error(f"Error fetching previous year frame for {tag}: {e}")
                resp = {"status": "ERROR"}
                
            if resp.get("status") == "OK":
                prev_rev_cache[tag] = {str(d["cik"]).zfill(10): d["value"] for d in resp.get("data", [])}
            else:
                prev_rev_cache[tag] = {}
                
        # 5. Fetch CIK-to-ticker mapping and market caps for EV/EBITDA
        # Panchwa step: Valuation ratios (EV/EBITDA) nikalne ke liye Market Cap chahiye, jiske liye yfinance use karenge
        cik_to_ticker = {}
        try:
            tickers_info = call_mcp_tool_sync("mcp_servers/sec_edgar_server.py", "get_company_tickers", {})
            if isinstance(tickers_info, str):
                tickers_info = json.loads(tickers_info)
            if tickers_info:
                for key, val in tickers_info.items():
                    c = str(val["cik_str"]).zfill(10)
                    cik_to_ticker[c] = val["ticker"]
        except Exception as e:
            logger.warning(f"Failed to fetch company tickers mapping: {e}")
            
        peer_market_caps = {}
        # Fetch market caps only for the top 10 peers by revenue to stay within yfinance limits
        yfinance_peers = peers[:10]
        for p in yfinance_peers:
            cik_str = str(p["cik"]).zfill(10)
            ticker = cik_to_ticker.get(cik_str)
            if ticker:
                try:
                    logger.info(f"Fetching market cap for peer {ticker} ({cik_str})")
                    snap_resp = call_mcp_tool_sync(
                        "mcp_servers/market_data_server.py", 
                        "get_market_snapshot", 
                        {"ticker": ticker}
                    )
                    if isinstance(snap_resp, str):
                        snap_data = json.loads(snap_resp)
                    else:
                        snap_data = snap_resp
                    
                    if snap_data and snap_data.get("market_cap"):
                        peer_market_caps[cik_str] = snap_data["market_cap"]
                except Exception as e:
                    logger.warning(f"Failed to fetch market cap for peer {ticker} ({cik_str}): {e}")

        # 6. Define calculation helpers
        def get_value(cik: str, tags: list[str], cache: dict) -> float | None:
            for tag in tags:
                if tag in cache and cik in cache[tag]:
                    return cache[tag][cik]
            return None
            return None

        # 7. Compute the 12 Metrics
        # Satwa step: Sabhi 20 peers ka mathematical calculation karna aur unko rank karna
        metrics_definitions = {
            "Gross Margin": {"ratio_key": "gross_margin", "higher_is_better": True, "percentage": True},
            "Operating Margin": {"ratio_key": "operating_margin", "higher_is_better": True, "percentage": True},
            "Net Margin": {"ratio_key": "net_profit_margin", "higher_is_better": True, "percentage": True},
            "ROA": {"ratio_key": "roa", "higher_is_better": True, "percentage": True},
            "ROE": {"ratio_key": "roe", "higher_is_better": True, "percentage": True},
            "Current Ratio": {"ratio_key": "current_ratio", "higher_is_better": True, "percentage": False},
            "Debt/EBITDA": {"ratio_key": "debt_to_ebitda", "higher_is_better": False, "percentage": False},
            "Interest Coverage": {"ratio_key": "interest_coverage", "higher_is_better": True, "percentage": False},
            "Asset Turnover": {"ratio_key": "asset_turnover", "higher_is_better": True, "percentage": False},
            "FCF Margin": {"ratio_key": "fcf_margin", "higher_is_better": True, "percentage": True},
            "Revenue Growth YoY": {"ratio_key": "revenue_yoy", "higher_is_better": True, "percentage": True},
            "EV/EBITDA": {"ratio_key": "ev_ebitda", "higher_is_better": False, "percentage": False}
        }
        
        benchmark_metrics = {}
        
        for metric_name, details in metrics_definitions.items():
            ratio_key = details["ratio_key"]
            target_record = self.target_ratios.get(ratio_key)
            
            target_val = None
            target_status = "NOT_APPLICABLE"
            target_reason = "Not computed in Module 1"
            
            if target_record:
                target_val = target_record.value
                target_status = target_record.status
                target_reason = target_record.reason
                
            # Calculate values for each peer
            peer_values = []
            for comp in peers:
                cik = str(comp["cik"]).zfill(10)
                
                # Fetch base components
                rev_curr = get_value(cik, ["Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet"], frames_cache)
                rev_prev = get_value(cik, ["Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet"], prev_rev_cache)
                gp = get_value(cik, ["GrossProfit"], frames_cache)
                op_inc = get_value(cik, ["OperatingIncomeLoss"], frames_cache)
                ni = get_value(cik, ["NetIncomeLoss", "ProfitLoss"], frames_cache)
                assets = get_value(cik, ["Assets"], frames_cache)
                equity = get_value(cik, ["StockholdersEquity"], frames_cache)
                ca = get_value(cik, ["AssetsCurrent"], frames_cache)
                cl = get_value(cik, ["LiabilitiesCurrent"], frames_cache)
                int_exp = get_value(cik, ["InterestExpense", "InterestExpenseDebt"], frames_cache)
                da = get_value(cik, ["DepreciationDepletionAndAmortization", "Depreciation"], frames_cache) or 0
                
                lt_debt = get_value(cik, ["LongTermDebtNoncurrent", "LongTermDebt"], frames_cache) or 0
                st_debt = get_value(cik, ["DebtCurrent", "ShortTermBorrowings"], frames_cache) or 0
                cash = get_value(cik, ["CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalentsFairValueDisclosure", "CashAndCashEquivalents"], frames_cache) or 0
                
                ocf = get_value(cik, ["NetCashProvidedByUsedInOperatingActivities"], frames_cache)
                capex = get_value(cik, ["PaymentsToAcquirePropertyPlantAndEquipment"], frames_cache)
                
                # Compute EBITDA
                ebitda = (op_inc + da) if op_inc is not None else None
                
                val = None
                
                # Calculate metrics
                if metric_name == "Gross Margin":
                    if gp is not None and rev_curr:
                        val = gp / rev_curr
                elif metric_name == "Operating Margin":
                    if op_inc is not None and rev_curr:
                        val = op_inc / rev_curr
                elif metric_name == "Net Margin":
                    if ni is not None and rev_curr:
                        val = ni / rev_curr
                elif metric_name == "ROA":
                    if ni is not None and assets:
                        val = ni / assets
                elif metric_name == "ROE":
                    if ni is not None and equity and equity > 0:
                        val = ni / equity
                elif metric_name == "Current Ratio":
                    if ca is not None and cl:
                        val = ca / cl
                elif metric_name == "Debt/EBITDA":
                    if lt_debt is not None and ebitda and ebitda > 0:
                        val = lt_debt / ebitda
                elif metric_name == "Interest Coverage":
                    if op_inc is not None and int_exp and int_exp > 0:
                        val = op_inc / int_exp
                elif metric_name == "Asset Turnover":
                    if rev_curr is not None and assets:
                        val = rev_curr / assets
                elif metric_name == "FCF Margin":
                    if ocf is not None and capex is not None and rev_curr:
                        val = (ocf - abs(capex)) / rev_curr
                elif metric_name == "Revenue Growth YoY":
                    if rev_curr is not None and rev_prev and rev_prev > 0:
                        val = (rev_curr - rev_prev) / rev_prev
                elif metric_name == "EV/EBITDA":
                    mcap = peer_market_caps.get(cik)
                    if mcap is not None and ebitda and ebitda > 0:
                        ev = mcap + (lt_debt + st_debt) - cash
                        val = ev / ebitda
                
                if val is not None:
                    if details["percentage"]:
                        val *= 100
                    peer_values.append(val)
                    
            if not peer_values:
                logger.info(f"Skipping {metric_name} benchmarking: no peer values resolved.")
                continue
                
            peer_values.sort()
            n_peers = len(peer_values)
            
            # Median (Becho-beech ki value, average se zyada accurate hoti hai kyunki ek bahut badi company result kharab nahi kar sakti)
            if n_peers % 2 == 0:
                sector_median = (peer_values[n_peers//2 - 1] + peer_values[n_peers//2]) / 2
            else:
                sector_median = peer_values[n_peers//2]
                
            # Mean (Saari values ka normal average)
            sector_mean = sum(peer_values) / n_peers
            
            percentile = None
            relative_position = None
            vs_median_delta = None
            note = None
            
            if target_status == "COMPUTED" and target_val is not None:
                # Target percentile = percentage of peers with LOWER value (Target se kitne log peeche hain)
                lower_count = sum(1 for v in peer_values if v < target_val)
                percentile = int((lower_count / n_peers) * 100)
                
                # Agar kisi ratio ka kam hona achha hai (e.g. Debt/EBITDA), to hum rank ulta (100 - percentile) se check karenge
                eval_percentile = percentile if details["higher_is_better"] else (100 - percentile)
                
                # Ye company ka final verdict/grade hai market ke hisab se
                if eval_percentile >= 75:
                    relative_position = "ABOVE_AVERAGE"
                elif eval_percentile >= 50:
                    relative_position = "AVERAGE"
                elif eval_percentile >= 25:
                    relative_position = "BELOW_AVERAGE"
                else:
                    relative_position = "SIGNIFICANTLY_BELOW_AVERAGE"
                    
                vs_median_delta = round(target_val - sector_median, 4)
                
                if not details["higher_is_better"]:
                    note = "Lower is better for this ratio."
                    
            benchmark_metrics[metric_name] = BenchmarkMetric(
                company_value=round(target_val, 4) if target_val is not None else None,
                sector_median=round(sector_median, 4),
                sector_mean=round(sector_mean, 4),
                company_percentile=percentile,
                relative_position=relative_position,
                vs_median_delta=vs_median_delta,
                note=note
            )
            
        top_peers_list = [PeerInfo(cik=str(p["cik"]).zfill(10), entity_name=p["entity_name"], revenue=p["value"]) for p in peers]
        
        output = BenchmarkOutput(
            ticker=self.ticker,
            sic_code=self.sic_code,
            industry=self.industry,
            benchmark_year=self.benchmark_year,
            peer_count=len(peers),
            top_peers=top_peers_list,
            metrics=benchmark_metrics
        )
        
        logger.info(f"Benchmarking completed successfully with {len(peers)} peers and {len(benchmark_metrics)} metrics.")
        return json.loads(output.model_dump_json())
