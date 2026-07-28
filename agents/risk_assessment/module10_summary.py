"""
Module:  module10_summary.py
Agent:   Risk Assessment Agent
Purpose: Compiles the final JSON payload containing all risk assessment findings.
Inputs:  RiskPreProcessor state, SQL database.
Outputs: Writes risk_assessment_output.json to the configured path.

# Hinglish Summary:
# Ye hamare Risk Assessment Agent ka aakhri (10th) module hai.
# Isme koi AI/LLM use nahi hota. Ye simply SQLite database me bache hue saare 9 modules ke 
# scores, deal breakers, aur mitigations ko uthata hai aur ek badi JSON file banata hai.
# Yahi JSON file Front-end Dashboard ko bheji jayegi jisse graphs aur tables banenge.
"""

import json
from typing import Any
from sqlalchemy import text
from datetime import datetime, timezone
import os

from tools.sqlite_tools import DatabaseManager

class RiskAssessmentSummary:
    def __init__(self, processor: Any):
        self.processor = processor
        self.db_path = processor.paths["SQLITE_DB_PATH"]
        self.ticker = processor.ticker
        self.out_path = processor.paths["RISK_SCORECARD_PATH"]

    def evaluate(self):
        self.processor.log_audit("MODULE_10_FINAL_SUMMARY", "STARTED", "Compiling final risk assessment summary (Combining all modules, deal breakers, and mitigations into Master JSON).")
        db = DatabaseManager(self.db_path)
        
        def get_mod_status(dim):
            try:
                row = db.execute(text("SELECT data_completeness FROM risk_dimensions WHERE company_ticker = :t AND dimension = :d"), {"t": self.ticker, "d": dim}).fetchone()
                if not row: return "INCOMPLETE"
                return "PARTIAL" if row[0] != "FULL" else "COMPLETE"
            except:
                return "INCOMPLETE"
                
        # Step 1: Har module ka status check karo (Ki wo sahi se chala ya nahi)
        mod_status = {
            "module_1_financial_risk": get_mod_status("FINANCIAL"),
            "module_2_market_risk": get_mod_status("MARKET"),
            "module_3_operational_risk": get_mod_status("OPERATIONAL"),
            "module_4_legal_risk": get_mod_status("LEGAL"),
            "module_5_management_quality": get_mod_status("MANAGEMENT"),
            "module_6_esg_risk": get_mod_status("ESG"),
            "module_7_deal_breaker_detection": "COMPLETE", 
            "module_8_composite_scoring": "COMPLETE",
            "module_9_mitigation_recommendations": "COMPLETE",
            "market_intel_available": getattr(self.processor, "market_intel_available", False),
            "news_sentiment_available": getattr(self.processor, "news_sentiment_available", False),
            "chromadb_available": getattr(self.processor, "chromadb_available", False),
            "weight_redistribution_applied": False
        }
        
        # Agar koi module properly nahi chala (PARTIAL/INCOMPLETE), toh overall status 'COMPLETE_WITH_DEGRADATION' ho jayega.
        overall_status = "COMPLETE"
        if any(v == "PARTIAL" or v == "INCOMPLETE" for k, v in mod_status.items() if k.startswith("module_") and k <= "module_6"):
            overall_status = "COMPLETE_WITH_DEGRADATION"
            
        dimensions = {}
        try:
            rows = db.execute(text("SELECT dimension, raw_score, risk_level, weight, weighted_score, data_completeness, top_finding FROM risk_dimensions WHERE company_ticker = :t"), {"t": self.ticker}).fetchall()
            for r in rows:
                dim_str = str(r[0])
                if dim_str == "FINANCIAL": d_key = "Financial"
                elif dim_str == "MARKET": d_key = "Market"
                elif dim_str == "OPERATIONAL": d_key = "Operational"
                elif dim_str == "LEGAL": d_key = "Legal"
                elif dim_str == "MANAGEMENT": d_key = "Management"
                elif dim_str == "ESG": d_key = "ESG"
                else: d_key = dim_str
                
                dimensions[d_key] = {
                    "raw_score": r[1],
                    "risk_level": r[2],
                    "weight": r[3],
                    "weighted_score": r[4],
                    "data_completeness": r[5],
                    "top_finding": r[6]
                }
        except: pass
        
        # Step 2: Database se final scores aur Risk levels nikalo
        try:
            row = db.execute(text("SELECT market_risk_data_available, weights_used, composite_score, risk_level, investment_stance, heat_map_json FROM composite_risk_output WHERE company_ticker = :t"), {"t": self.ticker}).fetchone()
            if row:
                if row[0] == 0:
                    mod_status["weight_redistribution_applied"] = True
                weights_used = json.loads(row[1])
                comp_score = row[2]
                comp_level = row[3]
                comp_stance = row[4]
                heat_map = json.loads(row[5])
            else:
                weights_used = {}
                comp_score = 0
                comp_level = "UNKNOWN"
                comp_stance = "UNKNOWN"
                heat_map = {}
        except:
            weights_used = {}
            comp_score = 0
            comp_level = "UNKNOWN"
            comp_stance = "UNKNOWN"
            heat_map = {}
            
        db_flags = []
        try:
            db_flags = db.execute(text("SELECT flag_type, triggered FROM deal_breaker_flags WHERE company_ticker = :t"), {"t": self.ticker}).fetchall()
        except: pass
        
        triggered_count = sum(1 for f in db_flags if f[1] == 1)
        all_checked = len(db_flags)
        
        deal_breaker_status_obj = {
            "all_checked": all_checked,
            "triggered": triggered_count,
            "not_triggered": all_checked - triggered_count,
            "details": "See deal_breaker_flags table for full audit trail of each condition checked, including data_completeness per condition."
        }
        
        stats = getattr(self.processor, "llm_usage_stats", {})
        total_t1 = stats.get("TIER_1_EXTRACTION", 0)
        total_t2 = stats.get("TIER_2_REASONING", 0)
        
        # Suggestions 3: Narrative Highlights
        narratives = {}
        try:
            evt_rows = db.execute(text("SELECT dimension, sub_dimension, severity, evidence_text FROM risk_evidence WHERE company_ticker = :t AND severity IN ('HIGH', 'CRITICAL')"), {"t": self.ticker}).fetchall()
            for er in evt_rows:
                dim_str = str(er[0]).capitalize()
                sub_dim = str(er[1])
                sev = str(er[2])
                txt = str(er[3])
                
                if dim_str not in narratives:
                    narratives[dim_str] = []
                narratives[dim_str].append(f"[{sev}] {sub_dim}: {txt}")
        except:
            pass

        # Step 3: LLM Cost Summary aur Master JSON Object banao
        summary = {
            "ticker": self.ticker,
            "company_name": getattr(self.processor, "company_name", "Unknown"),
            "run_id": self.processor.run_id,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "status": overall_status,
            "modules_status": mod_status,
            "LLM_USAGE_SUMMARY": {
                "total_llm_calls": total_t1 + total_t2,
                "tier_1_extraction_calls": total_t1,
                "tier_2_reasoning_calls": total_t2,
                "total_estimated_cost_usd": (total_t1 * 0.001) + (total_t2 * 0.01),
                "total_llm_duration_seconds": (total_t1 * 0.5) + (total_t2 * 1.5)
            },
            "COMPOSITE_RISK": {
                "composite_score": comp_score,
                "final_risk_level": comp_level,
                "investment_stance": comp_stance,
                "deal_breaker": getattr(self.processor, "deal_breaker_status", False),
                "deal_breaker_type": getattr(self.processor, "investment_stance_override", None),
                "weights_used": weights_used,
                "headline": f"{getattr(self.processor, 'company_name', 'Company')} scores {comp_level} overall risk ({comp_score}/100)."
            },
            "DIMENSION_SCORES": dimensions,
            "DEAL_BREAKER_STATUS": deal_breaker_status_obj,
            "NARRATIVE_HIGHLIGHTS": narratives,
            "RISK_HEAT_MAP": heat_map
        }
        
        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)
        with open(self.out_path, "w") as f:
            json.dump(summary, f, indent=2)
            
        db.dispose()
        self.processor.log_audit("MODULE_10_FINAL_SUMMARY", "COMPLETED", f"Master JSON Report successfully compiled to {self.out_path.name}. Data ready for frontend dashboard visualization.")

    def run(self):
        self.evaluate()
