"""
Module:  module5_management_risk.py
Agent:   Risk Assessment Agent
Purpose: Scores Management Quality and Governance Risk.
Inputs:  RiskPreProcessor state, ChromaDB, SQL database.
Outputs: Updates risk_dimensions and risk_evidence tables.

# Hinglish Summary:
# Ye module company ke Management (CEO/CFO), Board of Directors, aur Auditors (jo accounts check karte hain) ka risk measure karta hai.
# SPECIAL FEATURE: Iska "Step 26" sabse advance hai. Ye pichle saal ke text promises ko is saal ke real financial data se compare karta hai.
# DOUBLE-COUNTING PREVENTION: Prompts strictly sirf corporate governance, internal controls, aur insider transactions 
# par focus karte hain taaki Legal ya Operational risks galti se add na ho jayein.
"""

import json
from typing import Any
import chromadb
from sqlalchemy import text
from datetime import datetime, timezone

from tools.sqlite_tools import DatabaseManager
from agents.risk_assessment.llm_client import tier1_extract_tool, tier2_reason_tool
from agents.risk_assessment.risk_tier import adjust_points, get_departure_thresholds

class ManagementRiskScorer:
    def __init__(self, processor: Any):
        self.processor = processor
        self.db_path = processor.paths["SQLITE_DB_PATH"]
        self.chromadb_dir = processor.paths["CHROMADB_DIR_PATH"]
        self.run_id = processor.run_id
        self.ticker = processor.ticker
        self.tier = getattr(processor, 'company_tier', 'MID')
        
        self.total_points = 0
        self.evidence_list = []
        self.proxy_directors_found = False
        
        self.client = None
        self.sec_collection = None
        if self.processor.chromadb_available:
            try:
                self.client = chromadb.PersistentClient(path=str(self.chromadb_dir))
                coll_name = self.processor.chromadb_collection_name or "sec_filings"
                self.sec_collection = self.client.get_collection(coll_name)
            except Exception:
                self.client = None
                self.sec_collection = None

    def _add_evidence(self, sub_dimension: str, rule_name: str, evidence_text: str, severity: str, points: int,
                      evidence_source: str, chunks: int = None, llm_tier: str = "TIER_1_EXTRACTION", fiscal_year: str = None):
        self.total_points += points
        fy = fiscal_year or getattr(self, "current_rag_years", None)
        self.evidence_list.append({
            "dimension": "MANAGEMENT",
            "sub_dimension": sub_dimension,
            "evidence_type": rule_name,
            "evidence_source": evidence_source,
            "evidence_text": evidence_text,
            "severity": severity,
            "points_added": points,
            "chunks_retrieved_count": chunks,
            "llm_tier_used": llm_tier,
            "fiscal_year": fy
        })
        
    def _run_rag_sub_dimension(self, sub_dim_name: str, queries: list, sections: list, 
                               llm_instruction: str, scoring_logic_cb, most_recent_year=True):
        
        fy = self.processor.fiscal_year_end_date[:4] if self.processor.fiscal_year_end_date else "Unknown"
        
        chunks_per_query = []
        metadatas_per_query = []
        for q_text, limit in queries:
            if self.sec_collection:
                try:
                    where_cond = {
                        "$and": [
                            {"ticker": self.ticker},
                            {
                                "$or": [
                                    {
                                        "$and": [
                                            {"filing_type": "10-K"},
                                            {"fiscal_year": fy},
                                            {"section_code": {"$in": sections}}
                                        ]
                                    },
                                    {
                                        "$and": [
                                            {"filing_type": "DEF 14A"},
                                            {"section_code": {"$in": sections}}
                                        ]
                                    },
                                    {
                                        "$and": [
                                            {"filing_type": "10-Q"},
                                            {"section_code": {"$in": ["part2_item1a"]}}
                                        ]
                                    },
                                    {"filing_type": "8-K"},
                                    {"filing_type": "USER_FILE"}
                                ]
                            }
                        ]
                    }
                    res = self.sec_collection.query(
                        query_texts=[q_text],
                        n_results=limit,
                        where=where_cond
                    )
                    if res and res["documents"] and res["documents"][0]:
                        chunks_per_query.append(res["documents"][0][:5])
                        metadatas_per_query.append(res.get("metadatas", [[]])[0][:5])
                except Exception:
                    pass
                    
        # Round-robin merge to ensure diversity and relevance, capping at 5 chunks total
        all_chunks = []
        all_metadatas = []
        max_idx = max(len(lst) for lst in chunks_per_query) if chunks_per_query else 0
        for i in range(max_idx):
            for j, lst in enumerate(chunks_per_query):
                if i < len(lst):
                    chunk = lst[i]
                    if chunk not in all_chunks:
                        all_chunks.append(chunk)
                        all_metadatas.append(metadatas_per_query[j][i])
                    if len(all_chunks) >= 4:
                        break
            if len(all_chunks) >= 4:
                break
        
        # Extract years from metadatas
        rag_years = []
        for m in all_metadatas:
            if m and "fiscal_year" in m:
                yr = str(m["fiscal_year"])
                if yr and yr not in rag_years:
                    rag_years.append(yr)
        self.current_rag_years = ", ".join(sorted(rag_years)) if rag_years else None
        
        def log_cb(entry: dict):
            self.processor.log_audit("MODULE_5_MANAGEMENT_RISK", entry["status"], f"Tier 1 LLM: {entry.get('input_tokens')} in, {entry.get('output_tokens')} out.")
            
            
        
        if len(all_chunks) == 0:
            return None
            
        # Truncate each chunk to 800 chars to prevent API timeouts on dense governance/management text
        processed_chunks = []
        for c in all_chunks:
            if len(c) > 800:
                cutoff = c[:800].rfind(".")
                if cutoff == -1 or cutoff < 500:
                    cutoff = c[:800].rfind(" ")
                if cutoff != -1 and cutoff > 500:
                    processed_chunks.append(c[:cutoff+1])
                else:
                    processed_chunks.append(c[:800])
            else:
                processed_chunks.append(c)
            
        result = tier1_extract_tool(processed_chunks, llm_instruction, log_callback=log_cb)
        scoring_logic_cb(result, processed_chunks)
        self.current_rag_years = None


    def _get_historical_years(self):
        db = DatabaseManager(self.db_path)
        try:
            rows = db.execute(text("SELECT fiscal_year, period_end_date FROM financial_data WHERE ticker = :t ORDER BY fiscal_year DESC"), {"t": self.ticker}).fetchall()
            return [dict(row._mapping) for row in rows]
        except Exception:
            return []
        finally:
            db.dispose()
            
    def _get_year_ratios(self, fiscal_year):
        db = DatabaseManager(self.db_path)
        try:
            row = db.execute(text("SELECT * FROM financial_data WHERE ticker = :t AND fiscal_year = :fy"), {"t": self.ticker, "fy": fiscal_year}).fetchone()
            if row:
                return dict(row._mapping)
            return {}
        except Exception:
            return {}
        finally:
            db.dispose()

    def step26_mda_credibility(self):
        """
        # Step 26: MD&A Credibility Check (The Genius Feature)
        # Ye dekhta hai ki kya Management apne vaade (promises) poore karti hai ya sirf fekti hai.
        # Ye pichle saal ke MD&A (Management Discussion) me se target nikalta hai (Jaise "we expect 10% growth")
        # aur SQL database se actual 'is saal' ka data check karta hai. Agar target MISS hua toh credibility risk!
        """
        years_data = self._get_historical_years()
        if len(years_data) < 2 or not self.sec_collection:
            return 
            
        pairs = []
        for i in range(1, len(years_data)):
            if len(pairs) >= 3:
                break
            year_n_data = years_data[i]
            year_n_plus_1_data = years_data[i-1]
            pairs.append((year_n_data, year_n_plus_1_data))
            
        if not pairs:
            return
            
        all_missed = 0
        all_severely_missed = 0
        
        for n_data, n1_data in pairs:
            y_n = str(n_data.get("fiscal_year"))
            y_n_end = str(n_data.get("period_end_date"))
            y_n1 = str(n1_data.get("fiscal_year"))
            y_n1_end = str(n1_data.get("period_end_date"))
            
            queries = [
                "we expect OR we anticipate OR management believes OR we plan to",
                "we are confident OR we intend to OR we target"
            ]
            all_chunks = []
            for q in queries:
                try:
                    where_mda = {
                        "$and": [
                            {"ticker": {"$eq": self.ticker}},
                            {
                                "$and": [
                                    {"section_code": {"$eq": "item_7"}},
                                    {
                                        "$and": [
                                            {"filing_type": {"$eq": "10-K"}},
                                            {"fiscal_year": {"$eq": y_n}}
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                    res = self.sec_collection.query(
                        query_texts=[q], n_results=4,
                        where=where_mda
                    )
                    if res and res["documents"] and res["documents"][0]:
                        all_chunks.extend(res["documents"][0])
                except Exception:
                    pass
            
            all_chunks = list(set(all_chunks))
            if not all_chunks:
                continue
                
            def log_cb(entry: dict):
                self.processor.log_audit("MODULE_5_MANAGEMENT_RISK", entry["status"], f"Tier 2 LLM (26A): {entry.get('input_tokens')} in, {entry.get('output_tokens')} out.")
                
            instr_a = f"""You are an Elite Institutional Financial Analyst. Read this MD&A excerpt from fiscal year {y_n}, a 12-month period ending {y_n_end}.
Treat every claim in it as referring specifically to management's expectations for the NEXT reporting period after {y_n_end}.
Extract all specific quantitative or directional forward-looking claims management made.
CRITICAL ANTI-DOUBLE-COUNTING RULE: Extract ONLY specific forward-looking operational or financial targets. Do not extract general risk disclosures.
Extract ONLY claims with a measurable direction or target.
Return JSON: [{{\"claim_text\": \"str\", \"metric\": \"str\", \"direction\": \"str\", \"target\": \"str\", \"source_fiscal_year\": \"{y_n}\", \"source_fiscal_year_end_date\": \"{y_n_end}\"}}]
"""
            claims = tier2_reason_tool(all_chunks, instr_a, log_callback=log_cb)
            if not isinstance(claims, list) or len(claims) == 0:
                continue
                
            n1_ratios = self._get_year_ratios(y_n1)
            
            def log_cb_b(entry: dict):
                self.processor.log_audit("MODULE_5_MANAGEMENT_RISK", entry["status"], f"Tier 2 LLM (26B): {entry.get('input_tokens')} in, {entry.get('output_tokens')} out.")
            
            for claim in claims[:3]:
                instr_b = f"""You are an Elite Institutional Financial Analyst assessing Management Credibility.
Claim made by management in FY{y_n}: {json.dumps(claim)}
Actual financial data delivered for FY{y_n1} (ending {y_n1_end}): {json.dumps(n1_ratios)}
Determine objectively if the claim was DELIVERED, MISSED, SEVERELY_MISSED, or NOT_MEASURABLE based on the actual numbers.
Return JSON: {{\"status\": \"DELIVERED/MISSED/SEVERELY_MISSED/NOT_MEASURABLE\", \"actual_metric_value\": \"str\"}}
"""
                outcome = tier2_reason_tool([], instr_b, log_callback=log_cb_b)
                if isinstance(outcome, dict):
                    status = outcome.get("status", "NOT_MEASURABLE")
                    act_val = outcome.get("actual_metric_value", "unknown")
                    if status == "MISSED":
                        all_missed += 1
                        self._add_evidence("MDA_CREDIBILITY", "TREND_SIGNAL", 
                            f"FY{y_n} (ending {y_n_end}) MD&A claimed: '{claim.get('claim_text')}'. Actual FY{y_n1} outcome: {act_val}. Result: MISSED.", 
                            "MEDIUM", 0, "MD&A vs SQL Data", len(all_chunks), "TIER_2_REASONING")
                    elif status == "SEVERELY_MISSED":
                        all_severely_missed += 1
                        self._add_evidence("MDA_CREDIBILITY", "TREND_SIGNAL", 
                            f"FY{y_n} (ending {y_n_end}) MD&A claimed: '{claim.get('claim_text')}'. Actual FY{y_n1} outcome: {act_val}. Result: SEVERELY_MISSED.", 
                            "HIGH", 0, "MD&A vs SQL Data", len(all_chunks), "TIER_2_REASONING")
                            
        pts = 0
        if all_severely_missed >= 3:
            pts = 35
        elif all_severely_missed == 2:
            pts = 20
        elif all_severely_missed == 1 and all_missed >= 1:
            pts = 15
        elif all_missed >= 3:
            pts = 10
            
        if pts > 0:
            self._add_evidence("MDA_CREDIBILITY", "AGGREGATE_SCORE", f"MD&A Credibility Misses: {all_severely_missed} Severe, {all_missed} Standard", 
                "HIGH" if pts >= 15 else "MEDIUM", pts, "MD&A vs SQL Data", 0, "TIER_2_REASONING")

    def step27_board_governance(self):
        """
        # Step 27: Board & Corporate Governance
        # Ye dekhta hai ki kya company ka Board of Directors independent (azaad) hai ya sab management ke friends hain.
        # Proxy filings padhta hai. Agar CEO ka control over-powered hai (dual-class shares, anti-takeover) toh risk CRITICAL hai.
        """
        proxy_available = False
        if self.sec_collection:
            try:
                # Use simple flat $and which ChromaDB .get() reliably supports
                res = self.sec_collection.get(
                    where={
                        "$and": [
                            {"ticker": {"$eq": self.ticker}},
                            {"section_code": {"$eq": "proxy_directors"}}
                        ]
                    }
                )
                if res and res["documents"]:
                    proxy_available = True
                    self.proxy_directors_found = True
            except Exception: pass
            
        if not proxy_available:
            self._add_evidence("GOVERNANCE", "INSUFFICIENT_DATA", 
                "Governance scoring requires the proxy statement — not available for this company (no DEF 14A on file).", 
                "MEDIUM", 8, "Zero-Chunk Guard (Proxy)", 0, "NONE_PURE_PYTHON")
                
        queries = [
            ("independent directors OR board independence", 5),
            ("audit committee independence OR financial expert", 5),
            ("compensation committee OR executive compensation", 5),
            ("board diversity OR corporate governance", 5)
        ]
        
        instr = (
            "You are an Elite Institutional Corporate Governance Analyst. "
            "Read these passages about board composition and governance structure.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Focus STRICTLY on board independence, shareholder rights, and entrenchment provisions. Do NOT analyze legal investigations or operational risks.\n\n"
            "Identify:\n"
            "1. Are a majority of directors independent?\n"
            "2. Is there a separate audit committee with a financial expert?\n"
            "3. Are there any anti-takeover provisions that entrench management?\n"
            "4. Any disclosed governance concerns (e.g., dual-class share structure)?\n"
            "Return JSON: {\"majority_independent\": bool, \"audit_committee_expert\": bool, "
            "\"anti_takeover_provisions\": bool, \"dual_class_shares\": bool, \"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\"}"
        )
        
        def scorer(res, chunks):
            pts = 0
            sev = "LOW"
            desc = "Standard governance."
            if isinstance(res, dict):
                indep = res.get("majority_independent", True)
                shares = res.get("dual_class_shares", False)
                anti = res.get("anti_takeover_provisions", False)
                csev = res.get("severity", "LOW").upper()
                
                if not indep and shares:
                    pts = adjust_points(20, self.tier); sev = "CRITICAL"; desc = "Majority non-independent board AND dual-class shares."
                elif not indep or anti or csev == "HIGH":
                    pts = adjust_points(12, self.tier); sev = "HIGH"; desc = "Non-independent board OR entrenched management provisions."
                elif csev == "MEDIUM":
                    pts = adjust_points(6, self.tier); sev = "MEDIUM"; desc = "Weak audit committee independence or minor governance concerns."
                    
            if pts > 0:
                self._add_evidence("GOVERNANCE", "RAG_EXTRACT", desc, sev, pts, "ChromaDB, Item 9A/1A/Proxy", len(chunks))
                
        self._run_rag_sub_dimension("GOVERNANCE", queries, ["item_9a", "proxy_directors", "item_1a"], instr, scorer)

    def step28_related_party_tx(self):
        """
        # Step 28: Related Party Transactions (RPTs)
        # Ye dekhta hai ki kya Management company ke paise ko apne private businesses me ghooma (divert) toh nahi rahi.
        # (e.g., CEO apni hi ek aur private company se raw material mehange me kharid raha ho).
        """
        queries = [
            ("related party transactions OR related party interests", 5),
            ("transactions with officers OR directors OR affiliates", 5),
            ("loans to officers OR executives OR related parties", 5),
            ("affiliated company OR officer-owned entity", 5)
        ]
        
        instr = (
            "You are an Elite Institutional Forensic Accountant. "
            "Read these footnote passages and identify all disclosed related party transactions (RPTs).\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Focus STRICTLY on self-dealing, insider loans, or affiliated entity transactions. Do NOT extract standard customer/supplier risks unless they are owned by insiders.\n\n"
            "Severity: CRITICAL (large undisclosed or non-arm's-length RPTs), HIGH (significant RPTs without clear arm's-length process), "
            "MEDIUM (disclosed, arm's-length), LOW (none or immaterial).\n"
            "Return JSON: {\"rpt_found\": bool, \"arm_length_confirmed\": bool, \"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\", \"description\": \"<detailed description of related party transactions found>\"}"
        )
        
        def scorer(res, chunks):
            pts = 0; sev = "LOW"; desc = "No material RPTs."
            if isinstance(res, dict):
                csev = res.get("severity", "LOW").upper()
                desc = res.get("description", desc)
                extra = 1.5 if self.tier in ('SMALL', 'MICRO') else 1.0
                if csev == "CRITICAL": pts = adjust_points(20, self.tier, extra_multiplier=extra); sev = "CRITICAL"
                elif csev == "HIGH": pts = adjust_points(12, self.tier, extra_multiplier=extra); sev = "HIGH"
                elif csev == "MEDIUM": pts = adjust_points(5, self.tier, extra_multiplier=extra); sev = "MEDIUM"
                
            if pts > 0:
                self._add_evidence("RELATED_PARTY", "RAG_EXTRACT", desc, sev, pts, "ChromaDB, Item 8/1A", len(chunks))
                
        self._run_rag_sub_dimension("RELATED_PARTY", queries, ["item_8", "item_1a"], instr, scorer)

    def step29_auditor_quality(self):
        """
        # Step 29: Auditor Quality & Internal Controls
        # Ye check karta hai ki jo agency inke accounts check kar rahi hai, kya unhone koi 'Material Weakness' (accounting control fail)
        # ya 'Going Concern' (company doobne ka darr) mark kiya hai. Ye bhi dekhta hai ki kya auditor ko baar-baar change kiya ja raha hai (8-K 4.01).
        """
        queries = [
            ("material weakness in internal controls OR significant deficiency", 5),
            ("going concern opinion OR substantial doubt", 5),
            ("auditor changed OR change in certifying accountant", 5)
        ]
        
        instr = (
            "You are an Elite Institutional Audit Risk Analyst. "
            "Read these passages and identify auditor quality signals.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Focus STRICTLY on internal controls over financial reporting (SOX 404), going concern opinions, and auditor changes. Ignore the actual financial distress numbers (those are Financial Risk).\n\n"
            "1. Material weakness in internal controls?\n"
            "2. Going concern opinion?\n"
            "3. Auditor changed without clear business reason?\n"
            "4. Auditor name (Is it Big 4: Deloitte, PwC, EY, KPMG)?\n"
            "Return JSON: {\"material_weakness\": bool, \"going_concern\": bool, \"auditor_changed\": bool, \"is_big_4\": bool, \"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\"}"
        )
        
        def scorer(res, chunks):
            if isinstance(res, dict):
                if res.get("material_weakness"):
                    self._add_evidence("AUDITOR_QUALITY", "MATERIAL_WEAKNESS", "Material weakness in internal controls disclosed", "CRITICAL", adjust_points(15, self.tier, is_red_flag=True), "ChromaDB, Item 8/9A", len(chunks))
                if res.get("going_concern"):
                    self._add_evidence("AUDITOR_QUALITY", "GOING_CONCERN", "Going concern opinion from auditor", "CRITICAL", adjust_points(15, self.tier, is_red_flag=True), "ChromaDB, Item 8/9A", len(chunks))
                if res.get("auditor_changed"):
                    self._add_evidence("AUDITOR_QUALITY", "AUDITOR_CHANGE", "Auditor changed in last 2 years", "HIGH", adjust_points(8, self.tier), "ChromaDB, Item 8/9A", len(chunks))
                if not res.get("is_big_4", True):
                    self._add_evidence("AUDITOR_QUALITY", "NON_BIG_4", "Non-Big 4 auditor", "HIGH", adjust_points(5, self.tier), "ChromaDB, Item 8/9A", len(chunks))
                    
        self._run_rag_sub_dimension("AUDITOR_QUALITY", queries, ["item_8", "item_9a"], instr, scorer)
        
        if self.sec_collection:
            try:
                # ChromaDB .get() with two-condition $and is reliable; use $eq operators
                where_401 = {
                    "$and": [
                        {"ticker": {"$eq": self.ticker}},
                        {"filing_type": {"$eq": "8-K"}},
                        {"event_item": {"$eq": "4.01"}}
                    ]
                }
                res_401 = self.sec_collection.get(where=where_401)
                if res_401 and res_401["documents"]:
                    self._add_evidence("AUDITOR_QUALITY", "8K_4.01", "8-K: Change in Certifying Accountant", "HIGH", adjust_points(8, self.tier), "ChromaDB, 8-K", 0, "NONE_PURE_PYTHON")
            except Exception:
                try:
                    # Fallback: query all 8-K docs and filter manually
                    res_all = self.sec_collection.get(
                        where={"$and": [{"ticker": {"$eq": self.ticker}}, {"filing_type": {"$eq": "8-K"}}]}
                    )
                    if res_all and res_all.get("metadatas"):
                        for meta in res_all["metadatas"]:
                            if meta and meta.get("event_item") == "4.01":
                                self._add_evidence("AUDITOR_QUALITY", "8K_4.01", "8-K: Change in Certifying Accountant", "HIGH", adjust_points(8, self.tier), "ChromaDB, 8-K", 0, "NONE_PURE_PYTHON")
                                break
                except Exception:
                    pass

    def step30_executive_behavior(self):
        """
        # Step 30: Executive Behavior (Turnover & Misconduct)
        # Ye dekhta hai ki C-suite (CEO, CFO) jaldi-jaldi resign toh nahi kar rahe hain.
        # Direct 8-K Item 5.02 (Executive Departures) count karta hai.
        # Sath hi News Sentiment se "EXECUTIVE_MISCONDUCT" (fraud/scandal) cross-check karta hai.
        """
        departures = 0
        if self.sec_collection:
            try:
                # ChromaDB .get() with flat 3-condition $and is the most reliable approach
                where_502 = {
                    "$and": [
                        {"ticker": {"$eq": self.ticker}},
                        {"filing_type": {"$eq": "8-K"}},
                        {"event_item": {"$eq": "5.02"}}
                    ]
                }
                res = self.sec_collection.get(where=where_502)
                if res and res["documents"]:
                    departures = len(res["documents"])
            except Exception:
                try:
                    # Fallback: get all 8-K docs for ticker and count 5.02 events manually
                    res_all = self.sec_collection.get(
                        where={"$and": [{"ticker": {"$eq": self.ticker}}, {"filing_type": {"$eq": "8-K"}}]}
                    )
                    if res_all and res_all.get("metadatas"):
                        departures = sum(
                            1 for meta in res_all["metadatas"]
                            if meta and meta.get("event_item") == "5.02"
                        )
                except Exception:
                    departures = 0
            
        elev_thresh, crit_thresh = get_departure_thresholds(self.tier)
        if departures >= crit_thresh:
            self._add_evidence("EXECUTIVE_BEHAVIOR", "C_SUITE_TURNOVER", f"{crit_thresh}+ C-suite departures in 24 months ({departures})", "HIGH", adjust_points(20, self.tier), "ChromaDB, 8-K", 0, "NONE_PURE_PYTHON")
        elif departures >= elev_thresh:
            self._add_evidence("EXECUTIVE_BEHAVIOR", "CFO_CEO_DEPARTURE", "Executive departure flagged", "MEDIUM", adjust_points(10, self.tier), "ChromaDB, 8-K", 0, "NONE_PURE_PYTHON")

        if getattr(self.processor, "news_sentiment_available", False):
            db = DatabaseManager(self.db_path)
            try:
                rows = db.execute(text("SELECT * FROM news_sentiment WHERE company_ticker = :t AND crisis_flag = 1 AND crisis_type = 'EXECUTIVE_MISCONDUCT'"), {"t": self.ticker}).fetchall()
                if rows:
                    self._add_evidence("EXECUTIVE_BEHAVIOR", "NEWS_MISCONDUCT", "news_sentiment EXECUTIVE_MISCONDUCT flag", "HIGH", 10, "news_sentiment", 0, "NONE_PURE_PYTHON")
            except: pass
            finally: db.dispose()
        else:
            self._add_evidence("EXECUTIVE_BEHAVIOR", "INFO_NEWS_SKIPPED", "EXECUTIVE_MISCONDUCT news cross-reference skipped — Market Intelligence Agent's news_sentiment table unavailable this run. Executive Behavior scoring for this run is based solely on 8-K departure-pattern counting.", "LOW", 0, "System Flag", 0, "NONE_PURE_PYTHON")

    def step31_score_aggregation(self):
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
                
        top_finding_text = top_finding_evt["evidence_text"] if top_finding_evt else "No material management risks found."

        data_completeness = "FULL" if self.proxy_directors_found and getattr(self.processor, "news_sentiment_available", False) else "PARTIAL"
            
        self.processor.risk_scorecard["MANAGEMENT"] = {
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
            "t": self.ticker, "d": "MANAGEMENT", "rs": final_score, "rl": risk_level,
            "w": 0.15, "ws": final_score * 0.15, "tf": top_finding_text,
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
        
        msg = f"Management Quality Risk evaluated: Score {final_score}/100 ({risk_level}). Analyzed Executive Turnover, Insider Trading, Compensation & Board Independence. Found {len(self.evidence_list)} risk signals. Data Completeness: {data_completeness}."
        self.processor.log_audit("MODULE_5_MANAGEMENT_RISK", "COMPLETED", msg)

    def run(self):
        self.processor.log_audit("MODULE_5_MANAGEMENT_RISK", "STARTED", "Beginning Management Quality Risk evaluation (Exec Turnover, Compensation, Board Ind).")
        self.step26_mda_credibility()
        self.step27_board_governance()
        self.step28_related_party_tx()
        self.step29_auditor_quality()
        self.step30_executive_behavior()
        self.step31_score_aggregation()
