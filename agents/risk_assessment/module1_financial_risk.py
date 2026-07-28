"""
Module:  module1_financial_risk.py
Agent:   Risk Assessment Agent
Purpose: Scores the Financial Risk dimension using deterministic rules and Item 7 RAG.
Inputs:  RiskPreProcessor state (ratios, anomalies, rulebook, etc.)
Outputs: Updates risk_dimensions and risk_evidence tables via DatabaseManager.

# Hinglish Summary:
# Ye module sirf aur sirf "Financial Risks" (jaise debt, liquidity, going concern) ko dhundhta hai.
# Ye ratios, trends aur anomalies ko check karta hai, aur ChromaDB (RAG) se sirf Item 7 (MD&A), 
# Item 8 (Financials) aur Item 9A (Controls) padhta hai. 
# DOUBLE-COUNTING PREVENTION: Ye jaan-boojh kar Item 1A (Risk Factors) nahi padhta taaki legal ya 
# operational risks yahan dubara (double) count na ho jayein.
"""

from typing import Any
import chromadb
from sqlalchemy import text
from datetime import datetime, timezone
import json

from tools.sqlite_tools import DatabaseManager
from agents.risk_assessment.llm_client import tier1_extract_tool
from agents.risk_assessment.risk_tier import adjust_points, is_universal_red_flag

class FinancialRiskScorer:
    def __init__(self, processor: Any):
        self.processor = processor
        self.db_path = processor.paths["SQLITE_DB_PATH"]
        self.chromadb_dir = processor.paths["CHROMADB_DIR_PATH"]
        self.run_id = processor.run_id
        self.ticker = processor.ticker
        
        # Load rule sets
        fin_rules = processor.scoring_rulebook.get("financial_risk", {})
        self.rule_set_a = fin_rules.get("RULE_SET_A", {})
        self.rule_set_b = fin_rules.get("RULE_SET_B", {})
        self.rule_set_c = fin_rules.get("RULE_SET_C", {})
        self.rule_set_d = fin_rules.get("RULE_SET_D", {})
        self.rule_set_e = fin_rules.get("RULE_SET_E", {})
        self.rule_set_f = fin_rules.get("RULE_SET_F", {})
        
        self.total_points = 0
        self.evidence_list = []
        self.rules_evaluated = 0
        self.rules_skipped = 0
        self.tier = getattr(processor, 'company_tier', 'MID')

    def _add_evidence(self, sub_dimension: str, rule_name: str, evidence_text: str, severity: str, points: int, fiscal_year: str = None):
        """
        # Ye internal function risk points aur uski wajah (evidence) ko list me save karta hai.
        """
        self.total_points += points
        self.evidence_list.append({
            "dimension": "FINANCIAL",
            "sub_dimension": sub_dimension,
            "evidence_type": "FINANCIAL_RATIO",
            "evidence_source": f"RATIO_DB_PATH, FY{fiscal_year or (self.processor.fiscal_year_end_date[:4] if self.processor.fiscal_year_end_date else 'Unknown')}",
            "evidence_text": evidence_text,
            "severity": severity,
            "points_added": points,
            "chunks_retrieved_count": None,
            "llm_tier_used": "NONE_PURE_PYTHON",
            "fiscal_year": fiscal_year
        })

    def _check_status_and_eval(self, ratio_dict: dict, rule_cfg: dict, value_key: str = "value") -> bool:
        """
        # Unified Status Check: Ye check karta hai ki ratio successfully compute hua hai ya nahi.
        # Agar hua hai, toh rule config (jaise < 1.0) ke hisaab se true/false return karta hai.
        """
        if not ratio_dict or not isinstance(ratio_dict, dict) or not rule_cfg:
            self.rules_skipped += 1
            return False
            
        status = ratio_dict.get("status")
        if status in ["MISSING", "NOT_APPLICABLE", "NOT_MEANINGFUL"]:
            self.rules_skipped += 1
            return False
            
        if status == "COMPUTED":
            val = ratio_dict.get(value_key)
            if val is None:
                self.rules_skipped += 1
                return False
                
            self.rules_evaluated += 1
            op = rule_cfg.get("operator")
            thresh = rule_cfg.get("threshold")
            
            if op == "<" and val < thresh:
                return True
            if op == ">" and val > thresh:
                return True
            if op == "<=" and val <= thresh:
                return True
            if op == ">=" and val >= thresh:
                return True
                
        return False

    def step2_liquidity(self):
        """
        # Step 2: Liquidity Check (Current Ratio, Quick Ratio, Cash Ratio).
        # Badi companies (MEGA) kam cash par bhi chal sakti hain, choti (MICRO) nahi.
        # Isliye thresholds tier ke hisaab se adjust kiye gaye hain.
        """
        ratios = self.processor.analysis_summary.get("ratios", {}).get("most_recent_year", {})
        if not ratios:
            return

        # Tier-specific current ratio thresholds
        # Large/mega-caps deliberately operate at lower current ratios (credit access)
        if self.tier in ("MEGA", "LARGE"):
            cr_crit_thresh, cr_high_thresh = 0.50, 0.80
        elif self.tier == "MID":
            cr_crit_thresh, cr_high_thresh = 0.70, 1.00
        else:  # SMALL / MICRO
            cr_crit_thresh, cr_high_thresh = 1.00, 1.50

        cr = ratios.get("current_ratio", {})
        if cr.get("status") == "COMPUTED" and cr.get("value") is not None:
            self.rules_evaluated += 1
            val = cr["value"]
            if val < cr_crit_thresh:
                self._add_evidence("LIQUIDITY", "current_ratio_critical",
                                   f"Current Ratio = {val:.2f} (below critical threshold {cr_crit_thresh} for {self.tier} tier)",
                                   "CRITICAL", 25)
            elif val < cr_high_thresh:
                self._add_evidence("LIQUIDITY", "current_ratio_high",
                                   f"Current Ratio = {val:.2f} (below elevated threshold {cr_high_thresh} for {self.tier} tier)",
                                   "HIGH", 10)

        qr = ratios.get("quick_ratio", {})
        if self._check_status_and_eval(qr, self.rule_set_a.get("quick_ratio_high")):
            self._add_evidence("LIQUIDITY", "quick_ratio_high", f"Quick Ratio = {qr.get('value')} (below threshold 0.8)", "HIGH", 12)

        cash = ratios.get("cash_ratio", {})
        if self._check_status_and_eval(cash, self.rule_set_a.get("cash_ratio_high")):
            self._add_evidence("LIQUIDITY", "cash_ratio_high", f"Cash Ratio = {cash.get('value')} (below threshold 0.05)", "HIGH", 15)


    def step3_leverage(self):
        ratios = self.processor.analysis_summary.get("ratios", {}).get("most_recent_year", {})
        trends = self.processor.analysis_summary.get("trends", {})
        if not ratios:
            return
            
        # Net Debt / EBITDA
        nde = ratios.get("net_debt_ebitda", {})
        nde_fired = False
        if self._check_status_and_eval(nde, self.rule_set_b.get("net_debt_ebitda_critical")):
            self._add_evidence("LEVERAGE", "net_debt_ebitda_critical", f"Net Debt/EBITDA = {nde.get('value')}", "CRITICAL", 30)
            nde_fired = True
        elif self._check_status_and_eval(nde, self.rule_set_b.get("net_debt_ebitda_high")):
            self._add_evidence("LEVERAGE", "net_debt_ebitda_high", f"Net Debt/EBITDA = {nde.get('value')}", "HIGH", 15)
            nde_fired = True
        elif self._check_status_and_eval(nde, self.rule_set_b.get("net_debt_ebitda_medium")):
            self._add_evidence("LEVERAGE", "net_debt_ebitda_medium", f"Net Debt/EBITDA = {nde.get('value')}", "MEDIUM", 5)
            nde_fired = True
            
        # Interest Coverage — universal: if <1.0x company literally can't service debt
        ic = ratios.get("interest_coverage", {})
        if self._check_status_and_eval(ic, self.rule_set_b.get("interest_coverage_critical")):
            self._add_evidence("LEVERAGE", "interest_coverage_critical", f"Interest Coverage = {ic.get('value')}", "CRITICAL", 25)
        elif self._check_status_and_eval(ic, self.rule_set_b.get("interest_coverage_high")):
            self._add_evidence("LEVERAGE", "interest_coverage_high", f"Interest Coverage = {ic.get('value')}", "HIGH", 12)
            
        # Debt/Assets
        da = ratios.get("debt_to_assets", {})
        if self._check_status_and_eval(da, self.rule_set_b.get("debt_to_assets_high")):
            self._add_evidence("LEVERAGE", "debt_to_assets_high", f"Debt/Assets = {da.get('value')}", "HIGH", 15)
        elif self._check_status_and_eval(da, self.rule_set_b.get("debt_to_assets_medium")):
            self._add_evidence("LEVERAGE", "debt_to_assets_medium", f"Debt/Assets = {da.get('value')}", "MEDIUM", 7)
            
        # Debt/Equity
        de = ratios.get("debt_to_equity", {})
        if self._check_status_and_eval(de, self.rule_set_b.get("debt_to_equity_critical")):
            self._add_evidence("LEVERAGE", "debt_to_equity_critical", f"Debt/Equity = {de.get('value')}", "CRITICAL", 20)

        # Trend Acceleration Penalty
        if nde_fired and trends.get("status") != "SKIPPED":
            nde_trend = trends.get("trends", {}).get("net_debt_ebitda", "STABLE")
            if nde_trend == "DECLINING":
                self._add_evidence("LEVERAGE", "trend_acceleration", "Net Debt/EBITDA is in DECLINING trend (worsening) and elevated.", "HIGH", 5)

    def step4_profitability(self):
        ratios = self.processor.analysis_summary.get("ratios", {}).get("most_recent_year", {})
        trends = self.processor.analysis_summary.get("trends", {})
        
        npm = ratios.get("net_profit_margin", {})
        if self._check_status_and_eval(npm, self.rule_set_c.get("net_margin_negative")):
            self._add_evidence("PROFITABILITY", "net_margin_negative", f"Net Margin = {npm.get('value')}", "HIGH", 15)
            
        fcf = ratios.get("fcf_margin", {})
        if self._check_status_and_eval(fcf, self.rule_set_c.get("fcf_negative_current")):
            self._add_evidence("PROFITABILITY", "fcf_negative_current", f"FCF Margin = {fcf.get('value')}", "HIGH", 20)
            
        all_ratios = self.processor.analysis_summary.get("ratios", {}).get("historical", {})
        neg_fcf_count = 0
        if fcf.get("status") == "COMPUTED" and fcf.get("value", 0) < 0:
            neg_fcf_count += 1
            
        for yr, yr_data in all_ratios.items():
            f = yr_data.get("fcf_margin", {})
            if f.get("status") == "COMPUTED" and f.get("value", 0) < 0:
                neg_fcf_count += 1
                
        fcf_consec = {"status": "COMPUTED", "value": neg_fcf_count}
        if self._check_status_and_eval(fcf_consec, self.rule_set_c.get("fcf_negative_consecutive")):
            self._add_evidence("PROFITABILITY", "fcf_negative_consecutive", f"Negative FCF for {neg_fcf_count} years", "CRITICAL", 30)

        if trends.get("status") != "SKIPPED":
            cagr = trends.get("revenue_cagr_3yr", {})
            if isinstance(cagr, dict) and cagr.get("status") == "COMPUTED":
                if self._check_status_and_eval(cagr, self.rule_set_c.get("revenue_cagr_3yr_decline")):
                    self._add_evidence("PROFITABILITY", "revenue_cagr_3yr_decline", f"Revenue 3yr CAGR = {cagr.get('value')}", "HIGH", 20)
                elif self._check_status_and_eval(cagr, self.rule_set_c.get("revenue_cagr_3yr_flat")):
                    self._add_evidence("PROFITABILITY", "revenue_cagr_3yr_flat", f"Revenue 3yr CAGR = {cagr.get('value')}", "MEDIUM", 8)
                    
            ebitda_chg = trends.get("ebitda_margin_3yr_change", {})
            if isinstance(ebitda_chg, dict) and ebitda_chg.get("status") == "COMPUTED":
                if ebitda_chg.get("value", 0) < -self.rule_set_c.get("ebitda_margin_decline_8pt", {}).get("threshold", 8.0):
                    self._add_evidence("PROFITABILITY", "ebitda_margin_decline_8pt", f"EBITDA Margin 3yr Change = {ebitda_chg.get('value')}", "HIGH", 15)

    def step5_earnings_quality(self):
        ratios = self.processor.analysis_summary.get("ratios", {}).get("most_recent_year", {})
        qoe = self.processor.analysis_summary.get("qoe", {})
        
        cc = ratios.get("cash_conversion", {})
        if self._check_status_and_eval(cc, self.rule_set_d.get("cash_conversion_critical")):
            self._add_evidence("EARNINGS_QUALITY", "cash_conversion_critical", f"Cash Conversion = {cc.get('value')}", "CRITICAL", 30)
        elif self._check_status_and_eval(cc, self.rule_set_d.get("cash_conversion_high")):
            self._add_evidence("EARNINGS_QUALITY", "cash_conversion_high", f"Cash Conversion = {cc.get('value')}", "HIGH", 20)
            
        eqs_val = qoe.get("earnings_quality_score")
        if eqs_val is not None:
            self.rules_evaluated += 1
            if eqs_val < self.rule_set_d.get("eqs_score_high", {}).get("threshold", 40):
                self._add_evidence("EARNINGS_QUALITY", "eqs_score_high", f"Earnings Quality Score = {eqs_val}", "HIGH", 20)
            elif eqs_val < self.rule_set_d.get("eqs_score_medium", {}).get("threshold", 60):
                self._add_evidence("EARNINGS_QUALITY", "eqs_score_medium", f"Earnings Quality Score = {eqs_val}", "MEDIUM", 10)

    def step6_fraud_distress(self):
        fd = self.processor.analysis_summary.get("fraud_distress", {})
        
        beneish = fd.get("beneish_m_score", {})
        bv = beneish.get("verdict")
        b_critical = False
        if bv == "LIKELY_MANIPULATOR":
            pts = self.rule_set_e.get("beneish_likely_manipulator", {}).get("points", 35)
            self._add_evidence("FRAUD_DISTRESS", "beneish_likely_manipulator", "Beneish M-Score: LIKELY_MANIPULATOR", "CRITICAL", pts)
            b_critical = True
        elif bv == "GREY_ZONE":
            pts = self.rule_set_e.get("beneish_grey_zone", {}).get("points", 15)
            self._add_evidence("FRAUD_DISTRESS", "beneish_grey_zone", "Beneish M-Score: GREY_ZONE", "HIGH", pts)

        altman = fd.get("altman_z_score", {}).get("most_recent_year", {})
        av = altman.get("verdict")
        a_critical = False
        if av == "DISTRESS_ZONE":
            pts = self.rule_set_e.get("altman_distress_zone", {}).get("points", 35)
            self._add_evidence("FRAUD_DISTRESS", "altman_distress_zone", "Altman Z-Score: DISTRESS_ZONE", "CRITICAL", pts)
            a_critical = True
        elif av == "GREY_ZONE":
            pts = self.rule_set_e.get("altman_grey_zone", {}).get("points", 15)
            self._add_evidence("FRAUD_DISTRESS", "altman_grey_zone", "Altman Z-Score: GREY_ZONE", "HIGH", pts)
            
        if b_critical and a_critical:
            self._add_evidence("FRAUD_DISTRESS", "compound_distress", "Beneish LIKELY_MANIPULATOR and Altman DISTRESS_ZONE simultaneously", "CRITICAL", 10)

        anomalies = self.processor.analysis_summary.get("anomalies", {}).get("triggered_flags", [])
        crit_count = sum(1 for anom in anomalies if anom.get("severity") == "CRITICAL")
        high_count = sum(1 for anom in anomalies if anom.get("severity") == "HIGH")
        med_count = sum(1 for anom in anomalies if anom.get("severity") == "MEDIUM")
                
        crit_pts = min(crit_count * self.rule_set_f.get("anomaly_critical_per_flag", {}).get("points", 15),
                       self.rule_set_f.get("anomaly_critical_per_flag", {}).get("max_total", 30))
        if crit_pts > 0:
            self._add_evidence("FRAUD_DISTRESS", "anomaly_critical", f"{crit_count} CRITICAL anomaly flags", "CRITICAL", crit_pts)
            
        high_pts = min(high_count * self.rule_set_f.get("anomaly_high_per_flag", {}).get("points", 10),
                       self.rule_set_f.get("anomaly_high_per_flag", {}).get("max_total", 25))
        if high_pts > 0:
            self._add_evidence("FRAUD_DISTRESS", "anomaly_high", f"{high_count} HIGH anomaly flags", "HIGH", high_pts)
            
        med_pts = min(med_count * self.rule_set_f.get("anomaly_medium_per_flag", {}).get("points", 5),
                      self.rule_set_f.get("anomaly_medium_per_flag", {}).get("max_total", 15))
        if med_pts > 0:
            self._add_evidence("FRAUD_DISTRESS", "anomaly_medium", f"{med_count} MEDIUM anomaly flags", "MEDIUM", med_pts)

    def step7_chromadb_rag(self):
        if not self.processor.chromadb_available:
            self.processor.log_audit("MODULE_1_FINANCIAL_RISK", "WARNING", "ChromaDB unavailable, falling back to Zero-Chunk Guard.")
            
        queries = [
            ("going concern OR ability to continue as a going concern", "going_concern"),
            ("covenant breach OR loan default OR waiver from lender", "covenant"),
            ("liquidity concerns OR capital requirements OR additional funding", "liquidity"),
            ("material uncertainty OR significant doubt OR substantial doubt", "uncertainty"),
            ("debt maturity OR refinancing risk OR ability to refinance", "refinancing"),
            ("working capital deficit OR negative working capital", "working_capital")
        ]
        
        fy = self.processor.fiscal_year_end_date[:4] if self.processor.fiscal_year_end_date else "Unknown"
        
        client = None
        if self.processor.chromadb_available:
            try:
                client = chromadb.PersistentClient(path=str(self.chromadb_dir))
                coll_name = self.processor.chromadb_collection_name or "sec_filings"
                collection = client.get_collection(coll_name)
            except Exception:
                client = None
                
        def log_cb(entry: dict):
            self.processor.log_audit("MODULE_1_FINANCIAL_RISK", entry["status"], f"Tier 1 LLM: {entry.get('input_tokens')} in, {entry.get('output_tokens')} out.")
            
        chunks = []
        if client:
            try:
                res = collection.query(
                    query_texts=["going concern OR covenant breach OR loan default OR liquidity concerns OR capital requirements OR refinancing risk OR debt maturity OR working capital deficit"],
                    n_results=5,
                    where={
                        "$and": [
                            {"ticker": self.ticker},
                            {
                                "$or": [
                                    {
                                        "$and": [
                                            {"filing_type": "10-K"},
                                            {"fiscal_year": fy},
                                            {"section_code": {"$in": ["item_7", "item_8", "item_9a"]}}
                                        ]
                                    },
                                    {
                                        "$and": [
                                            {"filing_type": "10-Q"},
                                            {"section_code": {"$in": ["part1_item1", "part1_item2"]}}
                                        ]
                                    },
                                    {"filing_type": "8-K"},
                                    {"filing_type": "USER_FILE"}
                                ]
                            }
                        ]
                    }
                )
                if res and res["documents"] and res["documents"][0]:
                    chunks = res["documents"][0][:5]
                    # Extract years from metadatas
                    rag_years = []
                    for m in res.get("metadatas", [[]])[0][:5]:
                        if m and "fiscal_year" in m:
                            yr = str(m["fiscal_year"])
                            if yr and yr not in rag_years:
                                rag_years.append(yr)
                    self.current_rag_years = ", ".join(sorted(rag_years)) if rag_years else None
            except Exception:
                pass
                
        if len(chunks) == 0:
            self.evidence_list.append({
                "dimension": "FINANCIAL",
                "sub_dimension": "FORWARD_LOOKING",
                "evidence_type": "RAG_EXTRACT",
                "evidence_source": "ChromaDB",
                "evidence_text": "No chunks returned for forward-looking queries — no disclosure found in the filing for this topic.",
                "severity": "LOW",
                "points_added": 0,
                "chunks_retrieved_count": 0,
                "llm_tier_used": "NONE_ZERO_CHUNK_GUARD"
            })
        else:
            instruction = (
                "You are an Elite Institutional Financial Data Extraction Algorithm operating within a strict dimensional framework. "
                "Your task is to identify and extract ONLY pure financial risks from the provided text.\n\n"
                "CRITICAL ANTI-DOUBLE-COUNTING RULE:\n"
                "Do NOT extract any generic risks, legal proceedings, operational disruptions, cybersecurity issues, or ESG matters. "
                "Those belong to other modules. Extract ONLY items relating to these 6 pure financial categories:\n"
                "1. Going concern or ability to continue as a going concern\n"
                "2. Covenant breach, loan default, or lender waiver\n"
                "3. Critical liquidity issues, capital shortfalls, or urgent funding needs\n"
                "4. Material uncertainties or substantial doubts regarding financials\n"
                "5. Debt maturity pressures or refinancing risk\n"
                "6. Working capital deficit\n\n"
                "For each warning found, return a JSON object in a list. If none are found, return an empty list [].\n"
                "JSON format:\n"
                "[\n"
                "  {\n"
                "    \"category\": \"going_concern/covenant/liquidity/uncertainty/refinancing/working_capital\",\n"
                "    \"quote\": \"exact quote from text showing warning\",\n"
                "    \"severity\": \"CRITICAL\" (for actual going concern/defaults), \"HIGH\" (for severe liquidity warnings/refinancing risk), \"MEDIUM\" (for mild/general disclaimers), or \"LOW\" (for standard boilerplate)\n"
                "  }\n"
                "]"
            )
            
            result = tier1_extract_tool(chunks, instruction, log_callback=log_cb)
            
            if isinstance(result, list):
                for warning in result:
                    cat = warning.get("category", "general")
                    sev = warning.get("severity", "LOW").upper()
                    quote = warning.get("quote", "")
                    if not quote:
                        continue

                    # Universal red flags — full points regardless of tier
                    red_flags = {"going_concern", "covenant"}
                    base_pts = 0
                    if sev == "CRITICAL":
                        base_pts = 25
                    elif sev == "HIGH":
                        base_pts = 12
                    elif sev == "MEDIUM":
                        base_pts = 5

                    is_rf = cat in red_flags
                    pts = adjust_points(base_pts, self.tier, is_red_flag=is_rf)
                    self.total_points += pts
                    self.evidence_list.append({
                        "dimension": "FINANCIAL",
                        "sub_dimension": "FORWARD_LOOKING",
                        "evidence_type": "RAG_EXTRACT",
                        "evidence_source": "ChromaDB, Item 7/8/9A + 10-Q RAG",
                        "evidence_text": f"Warning flag ({cat.upper()}): {quote}",
                        "severity": sev,
                        "points_added": pts,
                        "chunks_retrieved_count": len(chunks),
                        "llm_tier_used": "TIER_1_EXTRACTION",
                        "fiscal_year": getattr(self, "current_rag_years", None)
                    })

        # Deterministic 8-K financial obligation checks
        if client:
            try:
                # 8-K Item 2.03: Creation of a Direct Financial Obligation
                where_203 = {
                    "$and": [
                        {"ticker": {"$eq": self.ticker}},
                        {
                            "$and": [
                                {"filing_type": {"$eq": "8-K"}},
                                {"event_item": {"$eq": "2.03"}}
                            ]
                        }
                    ]
                }
                res_203 = collection.get(where=where_203)
                if res_203 and res_203["documents"]:
                    count = len(res_203["documents"])
                    pts_203 = min(count * 8, 15)
                    self.total_points += pts_203
                    self.evidence_list.append({
                         "dimension": "FINANCIAL",
                         "sub_dimension": "FORWARD_LOOKING",
                         "evidence_type": "8K_EVENT",
                         "evidence_source": "ChromaDB, 8-K Item 2.03",
                         "evidence_text": f"8-K: {count} filing(s) reporting Creation of Direct Financial Obligation in last 2 years",
                         "severity": "HIGH" if count >= 2 else "MEDIUM",
                         "points_added": pts_203,
                         "chunks_retrieved_count": count,
                         "llm_tier_used": "NONE_PURE_PYTHON",
                         "fiscal_year": None
                    })

                # 8-K Item 2.04: Triggering Events That Accelerate/Increase Obligations
                where_204 = {
                    "$and": [
                        {"ticker": {"$eq": self.ticker}},
                        {
                            "$and": [
                                {"filing_type": {"$eq": "8-K"}},
                                {"event_item": {"$eq": "2.04"}}
                            ]
                        }
                    ]
                }
                res_204 = collection.get(where=where_204)
                if res_204 and res_204["documents"]:
                    self.total_points += 20
                    self.evidence_list.append({
                        "dimension": "FINANCIAL",
                        "sub_dimension": "FORWARD_LOOKING",
                        "evidence_type": "8K_EVENT",
                        "evidence_source": "ChromaDB, 8-K Item 2.04",
                        "evidence_text": "8-K: Triggering event that accelerates/increases a direct financial obligation",
                        "severity": "CRITICAL",
                        "points_added": 20,
                        "chunks_retrieved_count": len(res_204["documents"]),
                        "llm_tier_used": "NONE_PURE_PYTHON",
                        "fiscal_year": None
                    })
            except Exception:
                pass
        self.current_rag_years = None

    def step8_score_aggregation(self):
        final_score = max(0, min(100, self.total_points))
        
        if final_score <= 30:
            risk_level = "LOW"
        elif final_score <= 55:
            risk_level = "MEDIUM"
        elif final_score <= 75:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"
            
        top_finding_evt = None
        for ev in self.evidence_list:
            if top_finding_evt is None or ev["points_added"] > top_finding_evt["points_added"]:
                top_finding_evt = ev
                
        top_finding_text = top_finding_evt["evidence_text"] if top_finding_evt else "No material financial risks found."

        total_eval_rules = self.rules_evaluated + self.rules_skipped
        if total_eval_rules > 0 and (self.rules_evaluated / total_eval_rules) >= 0.8:
            data_completeness = "FULL"
        else:
            data_completeness = "PARTIAL"
            
        self.processor.risk_scorecard["FINANCIAL"] = {
            "raw_score": final_score,
            "risk_level": risk_level,
            "top_finding": top_finding_text,
            "data_completeness": data_completeness,
            "risk_evidence_list": self.evidence_list
        }
        
        db = DatabaseManager(self.db_path)
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS risk_dimensions (
                company_ticker TEXT, dimension TEXT, raw_score INTEGER, risk_level TEXT,
                weight REAL, weighted_score REAL, top_finding TEXT, evidence_count INTEGER,
                data_completeness TEXT, scored_at TEXT
            )
        """))
        db.execute(text("""
            INSERT INTO risk_dimensions (company_ticker, dimension, raw_score, risk_level, weight, weighted_score, top_finding, evidence_count, data_completeness, scored_at)
            VALUES (:t, :d, :rs, :rl, :w, :ws, :tf, :ec, :dc, :sa)
        """), {
            "t": self.ticker, "d": "FINANCIAL", "rs": final_score, "rl": risk_level,
            "w": 0.25, "ws": final_score * 0.25, "tf": top_finding_text,
            "ec": len(self.evidence_list), "dc": data_completeness,
            "sa": datetime.now(timezone.utc).isoformat() + "Z"
        })
        
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS risk_evidence (
                evidence_id INTEGER PRIMARY KEY AUTOINCREMENT, company_ticker TEXT, dimension TEXT, sub_dimension TEXT,
                evidence_type TEXT, evidence_source TEXT, evidence_text TEXT, fiscal_year TEXT, severity TEXT,
                points_added INTEGER, chunks_retrieved_count INTEGER, llm_tier_used TEXT
            )
        """))
        
        for ev in self.evidence_list:
            db.execute(text("""
                INSERT INTO risk_evidence (company_ticker, dimension, sub_dimension, evidence_type, evidence_source, evidence_text, fiscal_year, severity, points_added, chunks_retrieved_count, llm_tier_used)
                VALUES (:t, :d, :sd, :et, :es, :ex, :fy, :sev, :pa, :crc, :ltu)
            """), {
                "t": self.ticker, "d": ev["dimension"], "sd": ev["sub_dimension"], "et": ev["evidence_type"],
                "es": ev["evidence_source"], "ex": ev["evidence_text"], 
                "fy": ev.get("fiscal_year") or (self.processor.fiscal_year_end_date[:4] if self.processor.fiscal_year_end_date else None),
                "sev": ev["severity"], "pa": ev["points_added"], 
                "crc": ev.get("chunks_retrieved_count"), "ltu": ev.get("llm_tier_used")
            })
            
        db.dispose()
        self.processor.log_audit("MODULE_1_FINANCIAL_RISK", "COMPLETED",
            f"Financial Risk evaluated: Score {final_score}/100 ({risk_level}). Liquidity, Leverage, Profitability & Earnings Quality analyzed. Extracted {len(self.evidence_list)} risk signals. Data Completeness: {data_completeness}.")

    def run(self):
        self.processor.log_audit("MODULE_1_FINANCIAL_RISK", "STARTED", "Beginning Financial Risk evaluation.")
        self.step2_liquidity()
        self.step3_leverage()
        self.step4_profitability()
        self.step5_earnings_quality()
        self.step6_fraud_distress()
        self.step7_chromadb_rag()
        self.step8_score_aggregation()
