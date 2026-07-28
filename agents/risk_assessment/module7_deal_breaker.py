"""
Module:  module7_deal_breaker.py
Agent:   Risk Assessment Agent
Purpose: Evaluates 8 absolute deal breaker conditions and overrides investment stance if necessary.
Inputs:  RiskPreProcessor state, ChromaDB, SQL database, Analysis Agent outputs.
Outputs: Updates deal_breaker_flags table and processor state.

# Hinglish Summary:
# Ye module points nahi jodta, ye ek "Final Filter" hai. Ye 8 aisi khatarnaak situations dhundhta hai 
# jinke hone par seedha "AVOID" flag lag jata hai (Yani company me invest mat karo).
# FALSE-POSITIVE PREVENTION: LLM prompts ko 'Elite Auditors' ka persona diya gaya hai taaki wo sirf
# sach me hone wale fraud/crises ko pakdein aur generic baaton ko ignore karein.
"""

import json
import os
from typing import Any
import chromadb
from sqlalchemy import text
from datetime import datetime, timezone

from tools.sqlite_tools import DatabaseManager
from agents.risk_assessment.llm_client import tier1_extract_tool

class DealBreakerDetector:
    def __init__(self, processor: Any):
        self.processor = processor
        self.db_path = processor.paths["SQLITE_DB_PATH"]
        self.chromadb_dir = processor.paths["CHROMADB_DIR_PATH"]
        self.run_id = processor.run_id
        self.ticker = processor.ticker
        
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

        self.flags = []
        
    def _read_analysis_json(self):
        summary = getattr(self.processor, "analysis_summary", {})
        
        # Get altman z score
        fd = summary.get("fraud_distress", {})
        altman = fd.get("altman_z_score", {})
        beneish = fd.get("beneish_m_score", {})
        
        # Get ratios
        ratios_recent = summary.get("ratios", {}).get("most_recent_year", {})
        
        # Format for deal breaker
        data = {}
        
        # Map Altman verdict to status and zone
        altman_data = altman.get("most_recent_year", {})
        verdict = altman_data.get("verdict", "UNKNOWN")
        data["altman_z_score"] = {
            "status": "COMPUTED" if verdict != "NOT_APPLICABLE" else "NOT_APPLICABLE",
            "zone": verdict,
            "z_score": altman_data.get("z_score")
        }
        
        # Map Beneish
        verdict_b = beneish.get("verdict", "UNKNOWN")
        data["beneish_m_score"] = {
            "status": "COMPUTED" if verdict_b != "NOT_COMPUTABLE" else "NOT_COMPUTABLE",
            "verdict": verdict_b,
            "m_score": beneish.get("m_score")
        }
        
        # Map Ratios
        data["ratios_recent_year"] = {
            "interest_coverage_ratio": ratios_recent.get("interest_coverage", {}).get("value"),
            "interest_coverage_status": ratios_recent.get("interest_coverage", {}).get("status", "MISSING"),
            "net_profit_margin": ratios_recent.get("net_profit_margin", {}).get("value"),
            "net_debt_to_ebitda": ratios_recent.get("net_debt_to_ebitda", {}).get("value"),
        }
        
        data["anomaly_flags_list"] = summary.get("anomalies", {}).get("triggered_flags", [])
        
        # Calculate negative FCF count
        historical_ratios = summary.get("ratios", {}).get("historical", {})
        fcf_neg_count = 0
        for yr, yr_data in historical_ratios.items():
            fcf = yr_data.get("fcf_margin", {})
            if fcf.get("status") == "COMPUTED" and fcf.get("value", 0) < 0:
                fcf_neg_count += 1
        data["fcf_negative_years_count"] = fcf_neg_count
        
        return data
        
    def _add_flag(self, flag_type: str, triggered: int, completeness: str, evidence_text: str):
        self.flags.append({
            "company_ticker": self.ticker,
            "flag_type": flag_type,
            "triggered": triggered,
            "data_completeness": completeness,
            "evidence_text": evidence_text,
            "evaluated_at": datetime.now(timezone.utc).isoformat() + "Z"
        })

    def _verify_with_llm(self, query: str, sections: list, instruction: str, fy: str = None) -> bool:
        """Query ChromaDB and verify if the flag is actually triggered using the LLM."""
        if not self.sec_collection:
            return False
        try:
            if not fy:
                fy = self.processor.fiscal_year_end_date[:4] if self.processor.fiscal_year_end_date else "Unknown"
                
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
                            {"filing_type": "8-K"},
                            {"filing_type": "USER_FILE"}
                        ]
                    }
                ]
            }
                
            res = self.sec_collection.query(
                query_texts=[query], n_results=3, where=where_cond
            )
            if res and res["documents"] and res["documents"][0]:
                chunks = res["documents"][0]
                # Call LLM to verify
                res_json = tier1_extract_tool(
                    chunks,
                    f"Analyze the context and answer this question: {instruction} "
                    "Return JSON: {\"confirmed\": bool, \"explanation\": \"str\"}"
                )
                if isinstance(res_json, dict):
                    return bool(res_json.get("confirmed", False))
        except Exception:
            pass
        return False

    def _query_chroma(self, query: str, sections: list, fy: str = None, limit: int = 1):
        if not self.sec_collection:
            return False
            
        try:
            if not fy:
                fy = self.processor.fiscal_year_end_date[:4] if self.processor.fiscal_year_end_date else "Unknown"
                
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
                            {"filing_type": "8-K"},
                            {"filing_type": "USER_FILE"}
                        ]
                    }
                ]
            }
                
            res = self.sec_collection.query(
                query_texts=[query], n_results=limit, where=where_cond
            )
            if res and res["documents"] and res["documents"][0]:
                return True
        except: pass
        return False
        
    def _check_8k(self, event_item: str = None, query: str = None):
        if not self.sec_collection:
            return False
        try:
            if event_item:
                # Flat 3-condition $and — most reliable for ChromaDB .get() calls
                where_cond = {
                    "$and": [
                        {"ticker": {"$eq": self.ticker}},
                        {"filing_type": {"$eq": "8-K"}},
                        {"event_item": {"$eq": event_item}}
                    ]
                }
            else:
                where_cond = {
                    "$and": [
                        {"ticker": {"$eq": self.ticker}},
                        {"filing_type": {"$eq": "8-K"}}
                    ]
                }
                
            if query:
                res = self.sec_collection.query(
                    query_texts=[query], n_results=1, where=where_cond
                )
                if res and res["documents"] and res["documents"][0]:
                    return True
            else:
                res = self.sec_collection.get(where=where_cond)
                if res and res["documents"]:
                    return True
        except Exception:
            # Fallback: get all 8-K docs and filter manually
            try:
                res_all = self.sec_collection.get(
                    where={"$and": [{"ticker": {"$eq": self.ticker}}, {"filing_type": {"$eq": "8-K"}}]}
                )
                if res_all and res_all.get("metadatas"):
                    for meta in res_all["metadatas"]:
                        if meta and (event_item is None or meta.get("event_item") == event_item):
                            return True
            except Exception:
                pass
        return False

    def evaluate(self):
        self.processor.log_audit("MODULE_7_DEAL_BREAKER_DETECTION", "STARTED", "Evaluating deal breakers (Bankruptcy, Auditor Resignation, Critical Fraud).")
        fy = self.processor.fiscal_year_end_date[:4] if self.processor.fiscal_year_end_date else None
        analysis_data = self._read_analysis_json()
        
        # DB1: GOING_CONCERN
        # Ye check karta hai ki kya auditor ne bol diya hai ki company shayad 1 saal se zyada nahi chalegi (Substantial Doubt).
        # Financial sector ko Altman Z se chhot (exemption) mili hai, par text RAG wahan bhi check hota hai.
        gc_chroma = self._verify_with_llm("going concern substantial doubt", ["item_8_notes", "item_7"], 
                                         "You are an Elite Forensic Auditor. Determine if there is an EXPLICIT 'going concern' opinion or 'substantial doubt' about the company's survival. Ignore generic risk factors.", fy)
        altman = analysis_data.get("altman_z_score", {})
        altman_verdict = altman.get("status", "UNKNOWN")
        altman_zone = altman.get("zone", "")
        
        if altman_verdict == "NOT_APPLICABLE":
            if gc_chroma:
                self._add_flag("GOING_CONCERN", 1, "FULL", "ChromaDB found going concern language. Altman NOT_APPLICABLE (financial sector).")
            else:
                self._add_flag("GOING_CONCERN", 0, "FULL", "No going concern language in filings. Altman NOT_APPLICABLE.")
        else:
            if gc_chroma or altman_zone == "DISTRESS_ZONE":
                self._add_flag("GOING_CONCERN", 1, "FULL", f"Going concern triggered (ChromaDB: {gc_chroma}, Altman: {altman_zone})")
            else:
                self._add_flag("GOING_CONCERN", 0, "FULL", "No going concern signals.")

        # DB2: EARNINGS_MANIPULATION
        # Ye financial_data table se "Beneish M-Score" uthata hai aur check karta hai ki agar score 'LIKELY_MANIPULATOR' 
        # hai aur sath me 2 ya usse zyada anomalies hain, toh company fraud kar rahi hai.
        beneish = analysis_data.get("beneish_m_score", {})
        ben_status = beneish.get("status", "UNKNOWN")
        ben_verdict = beneish.get("verdict", "")
        
        if ben_status == "NOT_COMPUTABLE":
            self._add_flag("EARNINGS_MANIPULATION", 0, "FULL", "Beneish M-Score not computable — insufficient fiscal year history.")
        else:
            anomalies = analysis_data.get("anomaly_flags_list", [])
            high_anomalies = sum(1 for a in anomalies if a.get("severity") in ["HIGH", "CRITICAL"])
            if ben_verdict == "LIKELY_MANIPULATOR" and high_anomalies >= 2:
                self._add_flag("EARNINGS_MANIPULATION", 1, "FULL", f"Beneish LIKELY_MANIPULATOR with {high_anomalies} high/critical anomalies.")
            else:
                self._add_flag("EARNINGS_MANIPULATION", 0, "FULL", "No material earnings manipulation signal.")
                
        # DB3: ACTIVE_SEC_FRAUD
        # Ye dekhta hai ki kya SEC (Government) ne koi fraud investigation (probe) bitha di hai.
        # Sirf filing nahi, ye 'Market Intelligence Agent' ke news sentiment se bhi cross-verify (confirm) karta hai.
        sec_chroma = self._verify_with_llm("SEC investigation fraud allegation subpoena", ["item_3", "item_1a"], 
                                          "You are an Elite Chief Compliance Officer. Determine if there is an ACTIVE and EXPLICIT formal investigation or subpoena by the SEC/DOJ alleging fraud or misconduct. Ignore generic compliance language or standard industry regulations.", fy)
        if not getattr(self.processor, "news_sentiment_available", False):
            if sec_chroma:
                self._add_flag("ACTIVE_SEC_FRAUD", 1, "PARTIAL_NEWS_UNAVAILABLE", "Company's own 10-K discloses an active SEC investigation/fraud allegation (see ChromaDB evidence). News-based corroboration was not available this run (Market Intelligence Agent's news_sentiment table unavailable) — this deal breaker is triggered on filing-disclosure evidence alone.")
            else:
                self._add_flag("ACTIVE_SEC_FRAUD", 0, "PARTIAL_NEWS_UNAVAILABLE", "No SEC investigation or fraud allegation language found in item_3/item_1a. News-based cross-reference was not available this run — this deal breaker check is INCOMPLETE, not a confirmed clean result. If Market Intelligence Agent's news data becomes available on a future run, re-check is recommended.")
        else:
            db = DatabaseManager(self.db_path)
            news_fraud = False
            try:
                rows = db.execute(text("SELECT * FROM news_sentiment WHERE company_ticker = :t AND crisis_flag = 1 AND crisis_type IN ('SEC_INVESTIGATION', 'FRAUD_ALLEGATION')"), {"t": self.ticker}).fetchall()
                if rows: news_fraud = True
            except: pass
            finally: db.dispose()
            
            if news_fraud and sec_chroma:
                self._add_flag("ACTIVE_SEC_FRAUD", 1, "FULL", "News sentiment confirms SEC_INVESTIGATION/FRAUD_ALLEGATION and 10-K acknowledges it.")
            else:
                self._add_flag("ACTIVE_SEC_FRAUD", 0, "FULL", "No active confirmed SEC fraud.")

        # DB4: INTEREST_NOT_COVERED
        # Ye check karta hai ki kya company itna bhi paisa nahi kama rahi ki wo apne loan ka interest (byaj) de sake (ICR < 1.0)
        # aur sath me unka net margin bhi negative ho.
        ratios = analysis_data.get("ratios_recent_year", {})
        icr = ratios.get("interest_coverage_ratio", None)
        icr_status = ratios.get("interest_coverage_status", "COMPUTED")
        npm = ratios.get("net_profit_margin", None)
        
        if icr_status in ["MISSING", "NOT_APPLICABLE"]:
            self._add_flag("INTEREST_NOT_COVERED", 0, "FULL", f"interest_coverage status is {icr_status}")
        else:
            if icr is not None and npm is not None and icr < 1.0 and npm < 0:
                self._add_flag("INTEREST_NOT_COVERED", 1, "FULL", f"ICR < 1.0 ({icr}) AND net_profit_margin < 0 ({npm})")
            else:
                self._add_flag("INTEREST_NOT_COVERED", 0, "FULL", "Interest covered or profitable.")
                
        # DB5: BANKRUPTCY_IMMINENT
        # Ye Altman Z (Distress zone) ke sath High Leverage (Debt > 8x) aur lagatar Negative Free Cash Flow check karta hai.
        if altman_verdict == "NOT_APPLICABLE":
            self._add_flag("BANKRUPTCY_IMMINENT", 0, "FULL", "Altman Z-Score NOT_APPLICABLE for financial-sector company.")
        else:
            lev = ratios.get("net_debt_to_ebitda", 0)
            fcf_neg_count = analysis_data.get("fcf_negative_years_count", 0)
            if altman_zone == "DISTRESS_ZONE" and lev is not None and lev > 8.0 and fcf_neg_count >= 2:
                self._add_flag("BANKRUPTCY_IMMINENT", 1, "FULL", "Altman distress, high leverage (>8x), and persistent negative FCF.")
            else:
                self._add_flag("BANKRUPTCY_IMMINENT", 0, "FULL", "No imminent bankruptcy signal.")

        # DB6: CUSTOMER_CLIFF
        # Agar koi ek hi customer se 50% se zyada kamayi hoti hai (Concentration) aur us contract ke cancel (renew na hone) 
        # ka dar ho, toh company ek raat me aadhi ho sakti hai.
        db = DatabaseManager(self.db_path)
        m3_triggered = False
        try:
            rows = db.execute(text("SELECT * FROM risk_evidence WHERE company_ticker = :t AND evidence_type = 'CUSTOMER_CONCENTRATION' AND severity = 'CRITICAL'"), {"t": self.ticker}).fetchall()
            if rows: m3_triggered = True
        except: pass
        finally: db.dispose()
        
        if m3_triggered:
            cliff_chroma = self._query_chroma("contract renewal OR contract expiration OR relationship at risk", ["item_1a"], fy)
            if cliff_chroma:
                self._add_flag("CUSTOMER_CLIFF", 1, "FULL", ">50% customer concentration AND renewal risk detected.")
            else:
                self._add_flag("CUSTOMER_CLIFF", 0, "FULL", ">50% customer concentration, but NO renewal risk detected in Item 1A.")
        else:
            self._add_flag("CUSTOMER_CLIFF", 0, "FULL", "No single customer >50%.")
            
        # DB7: REVENUE_RESTATEMENT
        # Agar company bolti hai ki pichle saalo me unke revenue accounts me galti thi (Errors/Fraud) aur wo theek kar rahe hain.
        # Ye sabse bada fraud signal hota hai (Item 4.02).
        res_402 = self._check_8k(event_item="4.02")
        rest_chroma = self._verify_with_llm("restated previously reported restatement", ["item_8_notes"], 
                                           "You are an Elite Audit Risk Analyst. Determine if the company has explicitly stated they are restating previously issued financial statements due to material errors or fraud. Ignore routine accounting principle changes or generic revision language.", fy)
        
        if res_402 or rest_chroma:
            self._add_flag("REVENUE_RESTATEMENT", 1, "FULL", f"Restatement detected (8-K 4.02: {res_402}, 10-K: {rest_chroma}).")
        else:
            self._add_flag("REVENUE_RESTATEMENT", 0, "FULL", "No revenue restatement detected.")

        # DB8: AUDITOR_MATERIAL_WEAKNESS
        # Agar accounts check karne wale CA (Auditor) ne likh diya hai ki inke accounts system me "Weakness" hai.
        aw_chroma = self._verify_with_llm("material weakness internal control over financial reporting", ["item_8_notes", "item_7", "item_9a"], 
                                         "You are an Elite SOX Compliance Auditor. Determine if there is an ACTIVE 'material weakness' in internal controls over financial reporting. Ignore 'significant deficiencies' or weaknesses that have already been remediated.", fy)
        if aw_chroma:
            self._add_flag("AUDITOR_MATERIAL_WEAKNESS", 1, "FULL", "Material weakness in internal controls detected.")
        else:
            self._add_flag("AUDITOR_MATERIAL_WEAKNESS", 0, "FULL", "No material weakness detected.")

        # Step 38: Apply Deal Breaker Override

        triggered_db = [f for f in self.flags if f["triggered"] == 1]
        if len(triggered_db) == 0:
            deal_breaker_status = False
            stance_override = None
        elif any(f["flag_type"] in ["GOING_CONCERN", "ACTIVE_SEC_FRAUD", "BANKRUPTCY_IMMINENT", "REVENUE_RESTATEMENT"] for f in triggered_db):
            deal_breaker_status = True
            stance_override = "AVOID"
        else:
            deal_breaker_status = True
            stance_override = "ENHANCED_DD"
            
        self.processor.deal_breaker_status = deal_breaker_status
        self.processor.investment_stance_override = stance_override
        
        db = DatabaseManager(self.db_path)
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS deal_breaker_flags (
                company_ticker TEXT, flag_type TEXT, triggered INTEGER,
                data_completeness TEXT, evidence_text TEXT, evaluated_at TEXT
            )
        """))
        for f in self.flags:
            db.execute(text("""
                INSERT INTO deal_breaker_flags (company_ticker, flag_type, triggered, data_completeness, evidence_text, evaluated_at)
                VALUES (:t, :ft, :tr, :dc, :et, :ea)
            """), {
                "t": f["company_ticker"], "ft": f["flag_type"], "tr": f["triggered"],
                "dc": f["data_completeness"], "et": f["evidence_text"], "ea": f["evaluated_at"]
            })
        db.dispose()
        
        msg = f"Deal breaker evaluation complete. Analyzed 9 rules. Triggered: {len(triggered_db)}. Stance Override: {stance_override}."
        self.processor.log_audit("MODULE_7_DEAL_BREAKER_DETECTION", "COMPLETED", msg)

    def run(self):
        self.evaluate()
