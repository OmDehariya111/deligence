"""
Module:  module2_ltm_financials.py
Agent:   Market Intelligence Agent
Purpose: Fetch CompanyFacts via MCP and compute LTM metrics (with M-2 Fix).
Inputs:  named_competitors table, Target Company info.
Outputs: Writes to `competitor_ltm_financials` SQLite table.
"""

import json
import logging
from sqlalchemy import Column, Float, MetaData, String, Table, text

from config.paths import get_run_paths
from utils.mcp_client import call_mcp_tool_sync
from schemas.pydantic_models import MarketIntelContext
from tools.sqlite_tools import DatabaseManager
from utils.audit_logger import log_audit_event

logger = logging.getLogger(__name__)

def get_ltm_table(metadata: MetaData) -> Table:
    """
    # SQLite Database me `competitor_ltm_financials` table banane ke liye definition hai.
    # Isme sabhi companies (target + competitors) ka 12 mahine ka financial data save hoga.
    """
    return Table(
        "competitor_ltm_financials",
        metadata,
        Column("ticker", String, primary_key=True),
        Column("cik", String),
        Column("ltm_revenue", Float, nullable=True),
        Column("ltm_gross_profit", Float, nullable=True),
        Column("ltm_operating_inc", Float, nullable=True),
        Column("ltm_da", Float, nullable=True),
        Column("ltm_ebitda", Float, nullable=True),
        Column("ltm_net_income", Float, nullable=True),
        Column("ltm_operating_cf", Float, nullable=True),
        Column("ltm_capex", Float, nullable=True),
        Column("ltm_fcf", Float, nullable=True),
        Column("ltm_gross_margin", Float, nullable=True),
        Column("ltm_ebitda_margin", Float, nullable=True),
        Column("ltm_net_margin", Float, nullable=True),
        Column("ltm_fcf_margin", Float, nullable=True),
        Column("latest_cash", Float, nullable=True),
        Column("latest_st_debt", Float, nullable=True),
        Column("latest_lt_debt", Float, nullable=True),
        Column("latest_net_debt", Float, nullable=True),
        Column("prior_fy_revenue", Float, nullable=True),
        Column("quarters_used", String),
        Column("reporting_style_detected", String),
        extend_existing=True,
    )

class LTMExtractor:
    """
    # Ye class sabhi competitors ka SEC data nikal kar LTM (Last Twelve Months) compute karti hai.
    """
    def __init__(self, context: MarketIntelContext):
        self.context = context
        self.paths = get_run_paths(context.ticker, context.run_id)
        self.db_manager = DatabaseManager(self.paths["SQLITE_DB_PATH"])
        self.db_manager.create_tables([get_ltm_table(self.db_manager.metadata)])

    def _get_metric_data(self, facts: dict, primary_tag: str, fallback_tags: list = None, target_year: int = None) -> list:
        """Extract the 'units' array for a given tag, ensuring it has data for target_year if specified.
        # SEC data me metric ke naam badal sakte hain, toh ye function primary metric check karta hai,
        # agar na mile toh fallback names check karta hai.
        """
        tags_to_try = [primary_tag] + (fallback_tags or [])
        for tag in tags_to_try:
            if tag in facts:
                units = facts[tag].get("units", {})
                # Paison ki values USD ya CNY me ho sakti hain, ya per share bhi ho sakti hai.
                for unit_key in ["USD", "CNY", "shares", "USD/shares"]:
                    if unit_key in units and units[unit_key]:
                        entries = units[unit_key]
                        if target_year is not None:
                            # Verify if there is an entry for target_year (kya is saal ka annual data hai?)
                            has_target = any(e.get("form") in ["10-K", "20-F"] and e.get("fp") == "FY" and e.get("fy") == target_year for e in entries)
                            if not has_target:
                                continue
                        return entries
        return []

    def _determine_reporting_style(self, data: list, target_year: int) -> str:
        """
        Helper to run the M-2 test: cumulative vs individual detection.
        TEST 1: Sum of Q1+Q2+Q3 within 5% of (3/4)*annual_value (INDIVIDUAL)
        TEST 2: Q3 alone within 5% of (3/4)*annual_value (CUMULATIVE)
        
        # Ye detect karta hai ki company ne har quarter ka data alag se diya hai (INDIVIDUAL)
        # ya pichle quarters ka data jod ke diya hai (CUMULATIVE). Isse LTM calculation accurately hoti hai.
        """
        # Find annual value for target_year (Pure saal ki revenue/value)
        annual_val = None
        for item in data:
            if item.get("form") in ["10-K", "20-F"] and item.get("fy") == target_year and item.get("fp") == "FY":
                annual_val = item.get("val")
                break

        if annual_val is None or annual_val == 0:
            return "UNCERTAIN_TREATED_AS_CUMULATIVE"

        # Find quarters for target_year (Q1, Q2, Q3 nikalte hain)
        q1 = q2 = q3 = None
        for item in data:
            if item.get("fy") == target_year and item.get("fp") in ["Q1", "Q2", "Q3"]:
                fp = item.get("fp")
                val = item.get("val")
                if fp == "Q1":
                    q1 = val
                elif fp == "Q2":
                    q2 = val
                elif fp == "Q3":
                    q3 = val

        if q1 is None or q2 is None or q3 is None:
            return "UNCERTAIN_TREATED_AS_CUMULATIVE"

        sum_q1_q3 = q1 + q2 + q3
        target_val = 0.75 * annual_val

        # Logic: Kya teeno ka sum (3/4th) saal ke kareeb hai? (5% margin of error)
        t1_pass = abs(sum_q1_q3 - target_val) <= 0.05 * abs(target_val)
        # Logic: Kya sirf Q3 (YTD) 3/4th saal ke kareeb hai?
        t2_pass = abs(q3 - target_val) <= 0.05 * abs(target_val)

        if t1_pass and not t2_pass:
            return "INDIVIDUAL"
        elif t2_pass and not t1_pass:
            return "CUMULATIVE"
        else:
            # Safe khelne ke liye uncertain hone par cumulative maan lete hain
            return "UNCERTAIN_TREATED_AS_CUMULATIVE"

    def _individualize_quarters(self, quarters_dict: dict, style: str) -> dict:
        """
        Given a dict {1: q1_val, 2: q2_val, 3: q3_val, 4: q4_val},
        return a dict of individualized quarterly values.
        
        # Agar data cumulative hai, toh subtract karke har quarter ki alag individual value nikalta hai.
        """
        res = {}
        if style == "INDIVIDUAL":
            return {k: v for k, v in quarters_dict.items() if v is not None}
        
        # Cumulative / Uncertain Cumulative style
        # Q1 toh already individual hota hai (Jan-March)
        if 1 in quarters_dict and quarters_dict[1] is not None:
            res[1] = quarters_dict[1]
        # Q2 individual = Q2(Total) - Q1(Total)
        if 2 in quarters_dict and quarters_dict[2] is not None:
            q1_val = quarters_dict.get(1, 0) or 0
            res[2] = quarters_dict[2] - q1_val
        # Q3 individual = Q3(Total) - Q2(Total)
        if 3 in quarters_dict and quarters_dict[3] is not None:
            q2_val = quarters_dict.get(2, 0) or 0
            res[3] = quarters_dict[3] - q2_val
            
        return res

    def _get_annual_and_quarters(self, data: list, year: int) -> tuple[float | None, dict]:
        """Get annual value and raw quarterly values dict for a year.
        # Kisi ek particular saal ki annual value aur saaro quarters ki dict deta hai.
        """
        annual = None
        quarters = {1: None, 2: None, 3: None, 4: None}
        
        # Sort by end date descending (latest first) and filed date descending (newest first)
        sorted_data = sorted(data, key=lambda x: (x.get("end", ""), x.get("filed", "")), reverse=True)
        
        for item in sorted_data:
            if item.get("fy") == year:
                fp = item.get("fp")
                form = item.get("form") or ""
                val = item.get("val")
                if form in ["10-K", "20-F"] and fp == "FY":
                    if annual is None:
                        annual = val
                elif fp == "Q1":
                    if quarters[1] is None:
                        quarters[1] = val
                elif fp == "Q2":
                    if quarters[2] is None:
                        quarters[2] = val
                elif fp == "Q3":
                    if quarters[3] is None:
                        quarters[3] = val
                elif fp == "Q4":
                    if quarters[4] is None:
                        quarters[4] = val
        return annual, quarters

    def _compute_ltm(self, data: list, base_year: int, style: str) -> tuple[float | None, str]:
        """
        Computes LTM for a metric.
        LTM = FY_annual + sum(current_year_Qs_individual) - sum(prior_year_same_Qs_individual)
        Returns (LTM_value, quarters_used_str).
        
        # Ye sabse main logic hai jahan LTM calculate hoti hai actual formula lagake.
        """
        if not data:
            return None, "NO_DATA"

        # 1. Base year ki annual value lo
        annual_base, base_quarters = self._get_annual_and_quarters(data, base_year)
        if annual_base is None:
            return None, "NO_ANNUAL_BASE"

        # 2. Agle saal (Next year) me jo naye quarters hain wo lo
        _, next_quarters = self._get_annual_and_quarters(data, base_year + 1)

        available_next_quarters = [q for q, val in next_quarters.items() if val is not None]
        if not available_next_quarters:
            # Koi naya quarter nahi aaya, toh LTM pichle saal ke annual ke barabar hi hai.
            return annual_base, "FY"

        # Quarters ko individual format me convert karte hain
        base_ind = self._individualize_quarters(base_quarters, style)
        next_ind = self._individualize_quarters(next_quarters, style)

        added_val = 0.0
        subtracted_val = 0.0
        qs_used = []
        
        # LTM Formula: Add naye quarters, subtract purane same quarters
        for q in available_next_quarters:
            if q in next_ind and q in base_ind:
                added_val += next_ind[q]
                subtracted_val += base_ind[q]
                qs_used.append(f"Q{q}")

        if not qs_used:
            return annual_base, "FY"

        ltm_val = annual_base + added_val - subtracted_val
        return ltm_val, f"FY+{'+'.join(qs_used)}"

    def _get_latest_balance_sheet_val(self, data: list) -> float | None:
        """Find the most recent value in data, regardless of form/period.
        # Balance sheet point-in-time hoti hai, toh sirf sabse recent value utha lo.
        """
        if not data:
            return None
        # Sort by filed or end date
        sorted_data = sorted(data, key=lambda x: x.get("filed", "") or x.get("end", ""), reverse=True)
        return sorted_data[0].get("val")

    def _find_latest_10k_year(self, data: list) -> int | None:
        """Find the latest fiscal year with a filed 10-K.
        # Kis saal ki 10-K recently file hui hai wo detect karte hain taaki base year set ho.
        """
        years = []
        for item in data:
            if item.get("form") in ["10-K", "20-F"] and item.get("fp") == "FY" and item.get("val") is not None:
                years.append(item.get("fy"))
        return max(years) if years else None

    def run(self) -> None:
        # Naye standard ke hisab se "STARTED" log likhna zaroori hai
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_2_LTM_FINANCIALS",
            status="STARTED",
            summary="Fetching and processing LTM financials for target and competitors."
        )

        # Clear existing financials to prevent stale rows (Purana data hata do)
        with self.db_manager.get_connection() as conn:
            try:
                conn.execute(text("DELETE FROM competitor_ltm_financials"))
            except Exception as e:
                logger.warning(f"Failed to clear competitor_ltm_financials: {e}")

        # Read competitors list
        tickers_ciks = []
        with self.db_manager.get_connection() as conn:
            try:
                res = conn.execute(text("SELECT ticker, cik FROM named_competitors")).fetchall()
                tickers_ciks = [(r[0], r[1]) for r in res]
            except Exception as e:
                logger.warning(f"Failed to read named_competitors: {e}")

        # Add target company itself (Target company ka data bhi list me dalo)
        target_cik_padded = str(self.context.cik).zfill(10)
        tickers_ciks.append((self.context.ticker, target_cik_padded))
        
        # De-duplicate while preserving order
        seen = set()
        unique_tickers_ciks = []
        for t, c in tickers_ciks:
            if t not in seen:
                seen.add(t)
                unique_tickers_ciks.append((t, c))

        success_count = 0
        fallback_used_count = 0

        for ticker, cik in unique_tickers_ciks:
            logger.info(f"Processing financials for {ticker} (CIK: {cik})")
            
            # Fetch facts via MCP SEC Server
            facts_data = None
            try:
                cik_str = str(cik).zfill(10)
                facts_raw = call_mcp_tool_sync(
                    "mcp_servers/sec_edgar_server.py", 
                    "get_company_facts", 
                    {"cik": cik_str}
                )
                if isinstance(facts_raw, str):
                    facts_data = json.loads(facts_raw)
                else:
                    facts_data = facts_raw
            except Exception as e:
                logger.warning(f"MCP facts call failed for {ticker}: {e}")

            facts = {}
            if facts_data and facts_data.get("success"):
                facts = facts_data.get("facts", {}).get("us-gaap", {})

            # Determine base year first using raw revenue data
            raw_rev_data = self._get_metric_data(facts, "RevenueFromContractWithCustomerExcludingAssessedTax", ["Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet"])
            comp_base_year = self._find_latest_10k_year(raw_rev_data)
            if not comp_base_year:
                comp_base_year = self.context.most_recent_fiscal_year

            # Now fetch all metric lists, ensuring they have data for the base year
            revenue_data = self._get_metric_data(facts, "RevenueFromContractWithCustomerExcludingAssessedTax", ["Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet"], target_year=comp_base_year)
            if not revenue_data:
                revenue_data = raw_rev_data
                
            gp_data = self._get_metric_data(facts, "GrossProfit", target_year=comp_base_year)
            if not gp_data:
                # Fallback: GrossProfit = Revenue - CostOfRevenue
                cost_data = self._get_metric_data(facts, "CostOfGoodsAndServicesSold", ["CostOfGoodsSold", "CostOfRevenue", "CostOfServices"], target_year=comp_base_year)
                if revenue_data and cost_data:
                    cost_map = {}
                    for e in cost_data:
                        key = (e.get("fy"), e.get("fp"), e.get("form"), e.get("start"), e.get("end"))
                        cost_map[key] = e.get("val", 0.0)
                    gp_data = []
                    for e in revenue_data:
                        key = (e.get("fy"), e.get("fp"), e.get("form"), e.get("start"), e.get("end"))
                        if key in cost_map:
                            gp_val = e.get("val", 0.0) - cost_map[key]
                            gp_entry = dict(e)
                            gp_entry["val"] = gp_val
                            gp_data.append(gp_entry)

            opinc_data = self._get_metric_data(facts, "OperatingIncomeLoss", target_year=comp_base_year)
            da_data = self._get_metric_data(facts, "DepreciationDepletionAndAmortization", ["DepreciationAndAmortization", "Depreciation", "AmortizationOfIntangibleAssets"], target_year=comp_base_year)
            ni_data = self._get_metric_data(facts, "NetIncomeLoss", target_year=comp_base_year)
            ocf_data = self._get_metric_data(facts, "NetCashProvidedByUsedInOperatingActivities", target_year=comp_base_year)
            capex_data = self._get_metric_data(facts, "PaymentsToAcquirePropertyPlantAndEquipment", ["PaymentsToAcquireProductiveAssets", "CapitalExpenditures"], target_year=comp_base_year)
            
            # --- BUG 2 FIXED (Crash Fix): Shifted balance sheet loading BEFORE fallback block ---
            # Balance Sheet data (for latest balance sheet value)
            cash_data = self._get_metric_data(facts, "CashAndCashEquivalentsAtCarryingValue", ["CashAndCashEquivalentsTotal", "CashCashEquivalentsRestrictedCashAndCashEquivalents"])
            st_debt_data = self._get_metric_data(facts, "ShortTermBorrowings", ["DebtCurrent", "LongTermDebtCurrent"])
            lt_debt_data = self._get_metric_data(facts, "LongTermDebt", ["LongTermDebtNoncurrent"])

            # Evaluate their latest value now, taaki UnboundLocalError na aaye
            latest_cash = self._get_latest_balance_sheet_val(cash_data)
            latest_st_debt = self._get_latest_balance_sheet_val(st_debt_data) or 0.0
            latest_lt_debt = self._get_latest_balance_sheet_val(lt_debt_data) or 0.0

            style = self._determine_reporting_style(revenue_data, comp_base_year)
            
            # If target company and MCP failed to load facts, use Target fallback
            if ticker == self.context.ticker and not facts:
                style = "TARGET_FALLBACK"
                fallback_used_count += 1
                logger.info(f"Using fallback data for target company {ticker}")
                
            # Compute LTMs
            ltm_rev, rev_qs = self._compute_ltm(revenue_data, comp_base_year, style)
            ltm_gp, _ = self._compute_ltm(gp_data, comp_base_year, style)
            ltm_opinc, _ = self._compute_ltm(opinc_data, comp_base_year, style)
            ltm_da, _ = self._compute_ltm(da_data, comp_base_year, style)
            ltm_ni, _ = self._compute_ltm(ni_data, comp_base_year, style)
            ltm_ocf, _ = self._compute_ltm(ocf_data, comp_base_year, style)
            ltm_capex, _ = self._compute_ltm(capex_data, comp_base_year, style)

            if ltm_capex is None:
                # Fallback: CapEx = PPE_net_current - PPE_net_prior + Depreciation
                ppe_data = self._get_metric_data(facts, "PropertyPlantAndEquipmentNet", target_year=comp_base_year)
                if ppe_data:
                    ppe_curr, _ = self._get_annual_and_quarters(ppe_data, comp_base_year)
                    ppe_prior, _ = self._get_annual_and_quarters(ppe_data, comp_base_year - 1)
                    if ppe_curr is not None and ppe_prior is not None:
                        depr = ltm_da or 0.0
                        ltm_capex = ppe_curr - ppe_prior + depr
                        logger.info(f"Calculated fallback CapEx for {ticker}: {ltm_capex} (PPE change {ppe_curr} - {ppe_prior} + Depr {depr})")

            # Prior FY Revenue
            prior_fy_rev = None
            for item in revenue_data:
                if item.get("form") in ["10-K", "20-F"] and item.get("fp") == "FY" and item.get("fy") == comp_base_year - 1:
                    prior_fy_rev = item.get("val")
                    break

            # --- Target Fallback Logic ---
            # If target company has missing data, load from SQLite 'financial_data' table (populated by Ingestion/Analysis)
            if ticker == self.context.ticker:
                try:
                    with self.db_manager.get_connection() as conn:
                        row = conn.execute(
                            text(
                                "SELECT revenue, gross_profit, operating_income, "
                                "depreciation_and_amortization, ebitda, net_income, "
                                "operating_cash_flow, capital_expenditures, free_cash_flow, "
                                "cash_and_equivalents, short_term_debt, long_term_debt, net_debt "
                                "FROM financial_data WHERE ticker = :ticker AND fiscal_year = :year"
                            ),
                            {
                                "ticker": self.context.ticker,
                                "year": self.context.most_recent_fiscal_year
                            }
                        ).fetchone()
                        
                        if row:
                            if ltm_rev is None:
                                ltm_rev = row[0]
                                rev_qs = "FY"
                            if ltm_gp is None: ltm_gp = row[1]
                            if ltm_opinc is None: ltm_opinc = row[2]
                            if ltm_da is None: ltm_da = row[3]
                            if ltm_ebitda is None: ltm_ebitda = row[4]
                            if ltm_ni is None: ltm_ni = row[5]
                            if ltm_ocf is None: ltm_ocf = row[6]
                            if ltm_capex is None: ltm_capex = row[7]
                            if ltm_fcf is None: ltm_fcf = row[8]
                            
                            # Ab ye crash nahi hoga kyunki variables initialize ho chuke hain
                            if latest_cash is None: latest_cash = row[9]
                            if latest_st_debt == 0.0 or latest_st_debt is None: latest_st_debt = row[10] or 0.0
                            if latest_lt_debt == 0.0 or latest_lt_debt is None: latest_lt_debt = row[11] or 0.0
                            if latest_net_debt is None: latest_net_debt = row[12]

                        # Prior year revenue fallback for target
                        if prior_fy_rev is None:
                            row_prior = conn.execute(
                                text("SELECT revenue FROM financial_data WHERE ticker = :ticker AND fiscal_year = :year"),
                                {
                                    "ticker": self.context.ticker,
                                    "year": self.context.most_recent_fiscal_year - 1
                                }
                            ).fetchone()
                            if row_prior:
                                prior_fy_rev = row_prior[0]
                except Exception as e:
                    logger.warning(f"Failed to load target fallback from financial_data: {e}")

            # Compute derived EBITDA and FCF (if not already populated by fallback)
            ltm_ebitda = None
            if ltm_opinc is not None:
                da_val = ltm_da or 0.0
                ltm_ebitda = ltm_opinc + da_val

            ltm_fcf = None
            if ltm_ocf is not None:
                capex_val = ltm_capex or 0.0
                ltm_fcf = ltm_ocf - capex_val

            # Compute margins
            ltm_gross_margin = (ltm_gp / ltm_rev * 100) if ltm_gp is not None and ltm_rev else None
            ltm_ebitda_margin = (ltm_ebitda / ltm_rev * 100) if ltm_ebitda is not None and ltm_rev else None
            ltm_net_margin = (ltm_ni / ltm_rev * 100) if ltm_ni is not None and ltm_rev else None
            ltm_fcf_margin = (ltm_fcf / ltm_rev * 100) if ltm_fcf is not None and ltm_rev else None

            # Fallback for target balance sheet items from context.target_ratios
            if ticker == self.context.ticker:
                tr = self.context.target_ratios
                net_debt_ratio = tr.get("net_debt_to_ebitda") or tr.get("debt_to_equity")
                if net_debt_ratio and net_debt_ratio.get("inputs_used"):
                    inputs = net_debt_ratio["inputs_used"]
                    if latest_cash is None and "cash_and_equivalents" in inputs:
                        latest_cash = inputs["cash_and_equivalents"]
                    if latest_st_debt == 0.0 and "short_term_debt" in inputs:
                        latest_st_debt = inputs["short_term_debt"] or 0.0
                    if latest_lt_debt == 0.0 and "long_term_debt" in inputs:
                        latest_lt_debt = inputs["long_term_debt"] or 0.0

            latest_net_debt = None
            if latest_cash is not None:
                latest_net_debt = latest_st_debt + latest_lt_debt - latest_cash

            # Row data dictionary to insert into DB
            row = {
                "ticker": ticker,
                "cik": cik,
                "ltm_revenue": ltm_rev,
                "ltm_gross_profit": ltm_gp,
                "ltm_operating_inc": ltm_opinc,
                "ltm_da": ltm_da,
                "ltm_ebitda": ltm_ebitda,
                "ltm_net_income": ltm_ni,
                "ltm_operating_cf": ltm_ocf,
                "ltm_capex": ltm_capex,
                "ltm_fcf": ltm_fcf,
                "ltm_gross_margin": ltm_gross_margin,
                "ltm_ebitda_margin": ltm_ebitda_margin,
                "ltm_net_margin": ltm_net_margin,
                "ltm_fcf_margin": ltm_fcf_margin,
                "latest_cash": latest_cash,
                "latest_st_debt": latest_st_debt,
                "latest_lt_debt": latest_lt_debt,
                "latest_net_debt": latest_net_debt,
                "prior_fy_revenue": prior_fy_rev,
                "quarters_used": rev_qs,
                "reporting_style_detected": style
            }

            with self.db_manager.get_connection() as conn:
                try:
                    conn.execute(
                        text("""
                            INSERT OR REPLACE INTO competitor_ltm_financials (
                                ticker, cik, ltm_revenue, ltm_gross_profit, ltm_operating_inc, ltm_da,
                                ltm_ebitda, ltm_net_income, ltm_operating_cf, ltm_capex, ltm_fcf,
                                ltm_gross_margin, ltm_ebitda_margin, ltm_net_margin, ltm_fcf_margin,
                                latest_cash, latest_st_debt, latest_lt_debt, latest_net_debt,
                                prior_fy_revenue, quarters_used, reporting_style_detected
                            ) VALUES (
                                :ticker, :cik, :ltm_revenue, :ltm_gross_profit, :ltm_operating_inc, :ltm_da,
                                :ltm_ebitda, :ltm_net_income, :ltm_operating_cf, :ltm_capex, :ltm_fcf,
                                :ltm_gross_margin, :ltm_ebitda_margin, :ltm_net_margin, :ltm_fcf_margin,
                                :latest_cash, :latest_st_debt, :latest_lt_debt, :latest_net_debt,
                                :prior_fy_revenue, :quarters_used, :reporting_style_detected
                            )
                        """),
                        row
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to insert LTM record for {ticker}: {e}")

        # Summary ko descriptive aur transparent banane ke liye details add ki hain
        status = "COMPLETED"
        summary = (
            f"LTM financials processed for {len(unique_tickers_ciks)} companies. "
            f"Successfully inserted: {success_count}. "
            f"Database fallback used for {fallback_used_count} companies."
        )
        
        # 'COMPLETED' status with matching module name for duration tracking
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_2_LTM_FINANCIALS",
            status=status,
            summary=summary
        )
        
        logger.info(summary)
