import json
import logging
import os
from typing import Any
from pathlib import Path

from litellm import completion

from schemas.pydantic_models import (
    BenchmarkOutput, BenchmarkMetric, PeerInfo, RatioRecord
)
from utils.mcp_client import call_mcp_tool_sync
from utils.llm_utils import parse_llm_json_response

logger = logging.getLogger(__name__)

class SectorBenchmarkEngine:
    def __init__(self, ticker: str, sic_code: str, industry: str, benchmark_year: int, target_ratios: list[RatioRecord]):
        # Target company ki details aur uske Module 1 se nikle hue ratios store karte hain
        self.ticker = ticker.upper().strip()
        self.sic_code = sic_code.strip()
        self.industry = industry
        self.benchmark_year = benchmark_year
        self.target_ratios = {r.ratio_name: r for r in target_ratios if r.fiscal_year == benchmark_year}
        
    def _identify_peers_via_llm(self, company_name: str) -> list[str]:
        """LLM se real-world sector peers identify karna.
        
        Returns:
            List of company names (e.g. ["Microsoft Corp", "Alphabet Inc"])
        """
        model_name = os.environ.get("LLM_MODEL_NAME_TIER1", "vertex_ai/gemini-2.5-flash")
        
        prompt = (
            f"You are a financial analyst performing sector benchmarking. "
            f"For the company {self.ticker} ({company_name}) which operates in SIC industry code {self.sic_code} ({self.industry}), "
            f"identify the top 10 publicly-traded US peer companies that would appear in an institutional-grade sector benchmark comparison. "
            f"These should be companies that:\n"
            f"1. Are registered with the US SEC (have CIK numbers)\n"
            f"2. Operate in the same or closely related industry segments\n"
            f"3. Are comparable in terms of business model and market positioning\n"
            f"4. File annual reports (10-K) with the SEC\n\n"
            f"Use the EXACT legal names as registered with the SEC (e.g. 'MICROSOFT CORP' not 'Microsoft').\n"
            f"Do NOT include {self.ticker} ({company_name}) itself.\n\n"
            f"Return ONLY a valid JSON array of strings. Example: [\"MICROSOFT CORP\", \"ALPHABET INC\"]\n"
            f"No markdown formatting, no explanations."
        )
        
        try:
            response = completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = response.choices[0].message.content
            names = parse_llm_json_response(raw_text, default=[])
            if isinstance(names, list):
                result = [n.strip() for n in names if isinstance(n, str) and n.strip()]
                logger.info(f"LLM identified {len(result)} peer companies: {result}")
                return result
            return []
        except Exception as e:
            logger.error(f"LLM peer identification failed: {e}")
            return []
    
    def _resolve_names_to_ciks(self, names: list[str]) -> list[dict]:
        """Company names ko SEC tickers/CIKs me resolve karna.
        
        Returns:
            List of dicts with keys: ticker, cik, entity_name
        """
        if not names:
            return []
            
        try:
            tickers_data = call_mcp_tool_sync(
                "mcp_servers/sec_edgar_server.py",
                "get_company_tickers",
                {},
            )
            if isinstance(tickers_data, str):
                tickers_data = json.loads(tickers_data)
        except Exception as e:
            logger.error(f"Failed to fetch company tickers via MCP: {e}")
            return []
        
        # Build lookup list
        entity_lookup: list[tuple[str, str, str]] = []
        if tickers_data:
            for key, item in tickers_data.items():
                if isinstance(item, dict):
                    t = item.get("ticker")
                    title = item.get("title")
                    cik_val = item.get("cik_str")
                    if t and title:
                        cik_str = str(cik_val).zfill(10) if cik_val is not None else ""
                        entity_lookup.append((t, title, cik_str))
        
        resolved = []
        used_tickers = set()
        
        for name in names:
            name_lower = name.lower().strip()
            # Corporate suffixes hatake short form banao
            import re
            short_name = re.sub(r",?\s*\b(Inc\.?|Corp\.?|Corporation|LLC|PLC|Ltd\.?)\s*$", "", name, flags=re.IGNORECASE).strip().lower()
            
            best_match = None
            
            # Pass 1: Exact match
            for ticker_key, entity_name, cik_str in entity_lookup:
                ent_lower = entity_name.lower()
                tk_lower = ticker_key.lower()
                if (ent_lower == name_lower or ent_lower == short_name or 
                    tk_lower == name_lower or tk_lower == short_name):
                    best_match = (ticker_key, entity_name, cik_str)
                    break
            
            # Pass 2: Substring match
            if not best_match:
                for ticker_key, entity_name, cik_str in entity_lookup:
                    ent_lower = entity_name.lower()
                    if (name_lower in ent_lower or short_name in ent_lower or
                        ent_lower in name_lower or ent_lower in short_name):
                        best_match = (ticker_key, entity_name, cik_str)
                        break
            
            if best_match and best_match[0].upper() != self.ticker and best_match[0] not in used_tickers:
                resolved.append({
                    "ticker": best_match[0],
                    "entity_name": best_match[1],
                    "cik": best_match[2],
                })
                used_tickers.add(best_match[0])
        
        logger.info(f"Resolved {len(resolved)}/{len(names)} peer names to SEC tickers.")
        return resolved
        
    def run(self) -> dict[str, Any]:
        """Run sector benchmarking."""
        logger.info(f"Running sector benchmarking for {self.ticker} in year {self.benchmark_year} under SIC {self.sic_code}")
        
        # =====================================================================
        # STEP 1: LLM-based peer identification (NEW - replaces SIC filtering)
        # =====================================================================
        # Pehle ingestion summary se company name lene ki koshish
        company_name = self.industry or self.ticker
        
        llm_peer_names = self._identify_peers_via_llm(company_name)
        resolved_peers = self._resolve_names_to_ciks(llm_peer_names)
        
        if not resolved_peers:
            logger.warning("LLM peer identification yielded no resolved peers. Returning PARTIAL status.")
            return {"status": "PARTIAL", "peer_count": 0, "reason": "LLM peer identification yielded no SEC-resolved companies."}
        
        # =====================================================================
        # STEP 2: Fetch Revenue data to get peer revenue for sorting/PeerInfo
        # =====================================================================
        # IMPORTANT: Different companies use different XBRL revenue tags.
        # Semiconductors like Intel, AMD, Broadcom use RevenueFromContractWithCustomer*
        # while others use Revenues or SalesRevenueNet.
        # We try all common tags and merge the results to get maximum coverage.
        REVENUE_TAGS = [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
            "SalesRevenueServicesNet"
        ]
        
        target_year = self.benchmark_year
        
        # We need to find which year (target_year, target_year - 1, or target_year - 2) 
        # has the most peer revenue data published.
        year_coverage = {}
        year_data = {}
        
        for attempt_year in [target_year, target_year - 1, target_year - 2]:
            rev_by_cik = {}
            for tag in REVENUE_TAGS:
                try:
                    rev_resp = call_mcp_tool_sync(
                        "mcp_servers/sec_edgar_server.py",
                        "get_frames_data",
                        {"tag": tag, "unit": "USD", "period": f"CY{attempt_year}"}
                    )
                    if isinstance(rev_resp, str):
                        rev_resp = json.loads(rev_resp)
                    if rev_resp.get("status") == "OK":
                        for comp in rev_resp.get("data", []):
                            cik_str = str(comp["cik"]).zfill(10)
                            if cik_str not in rev_by_cik:
                                rev_by_cik[cik_str] = comp.get("value", 0)
                except Exception as e:
                    logger.warning(f"Revenue tag '{tag}' CY{attempt_year} failed: {e}")
                    continue
            
            peer_hits = sum(1 for p in resolved_peers if p["cik"] in rev_by_cik)
            year_coverage[attempt_year] = peer_hits
            year_data[attempt_year] = rev_by_cik
            
        # Select the year with the highest peer coverage. If tie, prefer more recent.
        best_year = max(year_coverage.keys(), key=lambda y: (year_coverage[y], y))
        self.benchmark_year = best_year
        revenue_by_cik = year_data[best_year]
        
        logger.info(f"Selected CY{best_year} for benchmarking as it covers {year_coverage[best_year]}/{len(resolved_peers)} peers.")
        
        if not revenue_by_cik:
            logger.warning("Could not fetch any revenue data from SEC EDGAR frames. Peer revenues will be 0.")

        
        # Build peer list with revenue info, sorted by revenue descending
        peers = []
        peer_ciks = set()
        for p in resolved_peers:
            cik = p["cik"]
            revenue = revenue_by_cik.get(cik, 0)
            peers.append({
                "cik": int(cik.lstrip("0")) if cik.lstrip("0") else 0,
                "entity_name": p["entity_name"],
                "value": revenue,  # 'value' key for compatibility with metrics computation
                "ticker": p["ticker"],
            })
            peer_ciks.add(cik)
        
        # Sort by revenue descending
        peers.sort(key=lambda x: x.get("value", 0), reverse=True)
        
        logger.info(f"Found {len(peers)} LLM-identified peer companies for benchmarking.")
            
        # =====================================================================
        # STEP 3: Fetch financial data frames for all metric tags
        # =====================================================================
        instant_tags = {
            "Assets", "StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            "AssetsCurrent", "LiabilitiesCurrent",
            "LongTermDebtNoncurrent", "LongTermDebt", "LongTermNotesPayable",
            "DebtCurrent", "ShortTermBorrowings", "LongTermDebtCurrent", "CommercialPaper", "NotesPayableCurrent",
            "CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalentsFairValueDisclosure", "CashAndCashEquivalents", "Cash", "CashCashEquivalentsAndShortTermInvestments"
        }
        
        standard_tags = {
            "GrossProfit", "OperatingIncomeLoss", "NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss", "NetIncome",
            "Assets", "StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            "AssetsCurrent", "LiabilitiesCurrent",
            "InterestExpense", "InterestAndDebtExpense", "InterestExpenseDebt", "InterestExpenseRelatedParty", "InterestExpenseNonoperating",
            "LongTermDebtNoncurrent", "LongTermDebt", "LongTermNotesPayable",
            "DebtCurrent", "ShortTermBorrowings", "LongTermDebtCurrent", "CommercialPaper", "NotesPayableCurrent",
            "NetCashProvidedByUsedInOperatingActivities", 
            "PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets", "CapitalExpenditureContinuingOperations", "PaymentsForCapitalImprovements",
            "DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation", "AmortizationOfIntangibleAssets",
            "CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalentsFairValueDisclosure", "CashAndCashEquivalents", "Cash", "CashCashEquivalentsAndShortTermInvestments",
            "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet", "SalesRevenueGoodsNet", "SalesRevenueServicesNet"
        }
        
        frames_cache = {}
        for tag in standard_tags:
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
        for tag in ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet", "SalesRevenueGoodsNet", "SalesRevenueServicesNet"]:
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
                
        # =====================================================================
        # STEP 4: Fetch market caps for EV/EBITDA
        # =====================================================================
        peer_market_caps = {}
        yfinance_peers = peers[:10]
        for p in yfinance_peers:
            ticker = p.get("ticker")
            cik_str = str(p["cik"]).zfill(10)
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

        # =====================================================================
        # STEP 5: Compute the 12 Metrics
        # =====================================================================
        def get_value(cik: str, tags: list[str], cache: dict) -> float | None:
            for tag in tags:
                if tag in cache and cik in cache[tag]:
                    return cache[tag][cik]
            return None

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
                rev_curr = get_value(cik, ["Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueGoodsNet", "SalesRevenueServicesNet"], frames_cache)
                rev_prev = get_value(cik, ["Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueGoodsNet", "SalesRevenueServicesNet"], prev_rev_cache)
                gp = get_value(cik, ["GrossProfit"], frames_cache)
                op_inc = get_value(cik, ["OperatingIncomeLoss"], frames_cache)
                ni = get_value(cik, ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss", "NetIncome"], frames_cache)
                assets = get_value(cik, ["Assets"], frames_cache)
                equity = get_value(cik, ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"], frames_cache)
                ca = get_value(cik, ["AssetsCurrent"], frames_cache)
                cl = get_value(cik, ["LiabilitiesCurrent"], frames_cache)
                int_exp = get_value(cik, ["InterestExpense", "InterestAndDebtExpense", "InterestExpenseDebt", "InterestExpenseRelatedParty", "InterestExpenseNonoperating"], frames_cache)
                da = get_value(cik, ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation", "AmortizationOfIntangibleAssets"], frames_cache) or 0
                
                lt_debt = get_value(cik, ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermNotesPayable"], frames_cache) or 0
                st_debt = get_value(cik, ["DebtCurrent", "ShortTermBorrowings", "LongTermDebtCurrent", "CommercialPaper", "NotesPayableCurrent"], frames_cache) or 0
                cash = get_value(cik, ["CashAndCashEquivalentsAtCarryingValue", "Cash", "CashAndCashEquivalents", "CashCashEquivalentsAndShortTermInvestments", "CashAndCashEquivalentsFairValueDisclosure"], frames_cache) or 0
                
                ocf = get_value(cik, ["NetCashProvidedByUsedInOperatingActivities"], frames_cache)
                capex = get_value(cik, ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets", "CapitalExpenditureContinuingOperations", "PaymentsForCapitalImprovements"], frames_cache)
                
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
            
            # Median
            if n_peers % 2 == 0:
                sector_median = (peer_values[n_peers//2 - 1] + peer_values[n_peers//2]) / 2
            else:
                sector_median = peer_values[n_peers//2]
                
            # Mean
            sector_mean = sum(peer_values) / n_peers
            
            percentile = None
            relative_position = None
            vs_median_delta = None
            note = None
            
            if target_status == "COMPUTED" and target_val is not None:
                lower_count = sum(1 for v in peer_values if v < target_val)
                percentile = int((lower_count / n_peers) * 100)
                
                eval_percentile = percentile if details["higher_is_better"] else (100 - percentile)
                
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
