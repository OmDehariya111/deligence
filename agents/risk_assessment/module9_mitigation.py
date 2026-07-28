"""
Module:  module9_mitigation.py
Agent:   Risk Assessment Agent
Purpose: Generates mitigation recommendations for all HIGH and CRITICAL risk findings.
Inputs:  RiskPreProcessor state, SQL database (risk_evidence table).
Outputs: Updates risk_mitigation_recommendations table and processor state.

# Hinglish Summary:
# Ye module ek "Problem Solver" hai. Pichle modules ne jo bhi HIGH ya CRITICAL khatre dhunde the,
# ye un sabko database se nikalta hai aur ek Smart LLM (Tier 2 - Pro Model) se puchta hai ki inko theek kaise karein.
# LLM Deal Team ko advice deta hai ki kya karna chahiye (Jaise: Deal Covenant me shart rakho, ya Site Visit karo).
"""

import json
from typing import Any
from sqlalchemy import text
from datetime import datetime, timezone

from tools.sqlite_tools import DatabaseManager
from agents.risk_assessment.llm_client import tier2_reason_tool

class MitigationRecommender:
    def __init__(self, processor: Any):
        self.processor = processor
        self.db_path = processor.paths["SQLITE_DB_PATH"]
        self.ticker = processor.ticker

    def evaluate(self):
        self.processor.log_audit("MODULE_9_MITIGATION_RECOMMENDATIONS", "STARTED", "Generating actionable risk mitigation recommendations using Tier-2 LLM.")
        
        db = DatabaseManager(self.db_path)
        
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS risk_mitigation_recommendations (
                company_ticker TEXT, dimension TEXT, sub_dimension TEXT, 
                finding_text TEXT, severity TEXT, priority TEXT, 
                condition_type TEXT, recommendation_text TEXT, generated_at TEXT
            )
        """))
        
        try:
            # Step 1: Database se sirf HIGH aur CRITICAL risk findings uthao. LOW/MEDIUM ko ignore karo.
            rows = db.execute(text("""
                SELECT dimension, sub_dimension, evidence_text, severity, chunks_retrieved_count 
                FROM risk_evidence 
                WHERE company_ticker = :t AND severity IN ('HIGH', 'CRITICAL')
            """), {"t": self.ticker}).fetchall()
            print(f"[DEBUG MODULE 9] self.ticker={self.ticker}, rows found: {len(rows)}")
        except Exception as e:
            print("[DEBUG MODULE 9] Query failed:")
            import traceback
            traceback.print_exc()
            rows = []
            
        immediate_count = 0
        near_term_count = 0
        monitor_count = 0
        
        if not rows:
            self.processor.log_audit("MODULE_9_MITIGATION_RECOMMENDATIONS", "COMPLETED", "0 recommendations generated (0 IMMEDIATE, 0 NEAR_TERM, 0 MONITOR).")
            db.dispose()
            return
            
        for r in rows:
            dimension = str(r[0])
            sub_dim = str(r[1])
            evidence_text = str(r[2])
            severity = str(r[3]).upper()
            chunks = r[4]
            
            # Agar risk CRITICAL hai toh Priority IMMEDIATE hogi (yani aaj hi deal roko aur solve karo).
            # Agar HIGH hai toh NEAR_TERM hogi (yani invest karne se pehle solve karo).
            priority = "IMMEDIATE" if severity == "CRITICAL" else "NEAR_TERM"
            
            # Step 2: Tier-2 Smart LLM ke liye Elite Prompt.
            prompt = f"""You are an Elite M&A Deal Structuring Lawyer and Institutional Risk Manager.
Based on this specific high-severity risk finding:
  Dimension: {dimension}
  Sub-dimension: {sub_dim}
  Finding: {evidence_text}
  Severity: {severity}
  Data completeness of underlying evidence: {chunks} chunks retrieved
    (if this is 0, the finding was derived from a mathematical guardrail, NOT text. Your recommendation must include physically verifying the numbers with management).

Your task is to write ONE specific, legally or operationally actionable recommendation for the M&A deal team to mitigate this risk.
CRITICAL RULES:
1. Targeted strictly at this EXACT finding (Do NOT give generic business advice).
2. The recommendation MUST fall into one of these strict institutional condition types: INFORMATION_REQUEST (Demand specific documents), SITE_VISIT (Physical inspection), BACKGROUND_CHECK (Investigate individuals), DEAL_COVENANT (Bind them legally), ONGOING_MONITORING, ENHANCED_AUDIT, REPRESENTATION_WARRANTY (Force them to legally guarantee).
3. Be authoritative, concise, and written in 2-4 sentences suitable for a formal investment committee memo.
Return JSON: {{"recommendation_text": "str", "condition_type": "str"}}
"""
            
            def log_cb(entry: dict):
                pass
                
            try:
                res = tier2_reason_tool(prompt, "Return valid JSON matching the schema.", log_callback=log_cb)
                rec_text = res.get("recommendation_text", "Recommend investigating this finding during due diligence.")
                cond_type = res.get("condition_type", "INFORMATION_REQUEST")
                
                # Step 3: LLM ka diya hua solution database ki risk_mitigation_recommendations table me save kardo.
                db.execute(text("""
                    INSERT INTO risk_mitigation_recommendations (company_ticker, dimension, sub_dimension, finding_text, severity, priority, condition_type, recommendation_text, generated_at)
                    VALUES (:t, :d, :sd, :ft, :sev, :pri, :ct, :rt, :ga)
                """), {
                    "t": self.ticker, "d": dimension, "sd": sub_dim, "ft": evidence_text, 
                    "sev": severity, "pri": priority, "ct": cond_type, "rt": rec_text, 
                    "ga": datetime.now(timezone.utc).isoformat() + "Z"
                })
                
                if priority == "IMMEDIATE":
                    immediate_count += 1
                elif priority == "NEAR_TERM":
                    near_term_count += 1
            except Exception as e:
                print(f"[DEBUG MODULE 9] Exception for row: {e}")
                import traceback
                traceback.print_exc()

        db.dispose()
        
        msg = f"Mitigation engine complete. Generated {immediate_count + near_term_count + monitor_count} actionable solutions ({immediate_count} IMMEDIATE, {near_term_count} NEAR_TERM, {monitor_count} MONITOR). Tier-2 Reasoning applied."
        self.processor.log_audit("MODULE_9_MITIGATION_RECOMMENDATIONS", "COMPLETED", msg)

    def run(self):
        self.evaluate()
