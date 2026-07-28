"""
Module:  module8_composite_score.py
Agent:   Risk Assessment Agent
Purpose: Calculates final risk score, applies weight redistribution, and sets investment stance.
Inputs:  RiskPreProcessor state, SQL database (risk_dimensions table).
Outputs: Updates composite_risk_output table.

# Hinglish Summary:
# Ye module baki ke 6 modules (Financial, Legal, etc.) ke points ko jod kar ek final "Composite Score" (100 me se) banata hai.
# Isme koi LLM/AI use nahi hota, ye pure mathematical logic par chalta hai (Cost = Zero).
# Iska sabse smart feature "Weight Redistribution" hai: Agar koi module ka data nahi milta, toh ye uske weight ko 
# baki modules me baant deta hai taaki score zero na aaye.
"""

import json
from typing import Any
from sqlalchemy import text
from datetime import datetime, timezone

from tools.sqlite_tools import DatabaseManager

class CompositeRiskScorer:
    def __init__(self, processor: Any):
        self.processor = processor
        self.db_path = processor.paths["SQLITE_DB_PATH"]
        self.ticker = processor.ticker
        
        # Har module ki importance (weightage) pehle se set hai.
        # Sabse zyada importance Financial (25%) aur Legal (20%) ko di gayi hai.
        self.nominal_weights = {
            "FINANCIAL":   0.25,
            "LEGAL":       0.20,
            "MARKET":      0.15,
            "MANAGEMENT":  0.15,
            "OPERATIONAL": 0.15,
            "ESG":         0.10
        }

    def evaluate(self):
        self.processor.log_audit("MODULE_8_COMPOSITE_SCORING", "STARTED", "Calculating composite risk score, risk level, and final investment stance.")
        
        db = DatabaseManager(self.db_path)
        try:
            rows = db.execute(text("SELECT dimension, raw_score, data_completeness FROM risk_dimensions WHERE company_ticker = :t"), {"t": self.ticker}).fetchall()
            dimensions = {str(r[0]): {"raw_score": int(r[1]), "data_completeness": str(r[2])} for r in rows}
        except Exception:
            dimensions = {}
            
        for dim in self.nominal_weights:
            if dim not in dimensions:
                dimensions[dim] = {"raw_score": 0, "data_completeness": "INSUFFICIENT_DATA"}
                
        insufficient = [dim for dim, data in dimensions.items() if data["data_completeness"] == "INSUFFICIENT_DATA"]
        
        redistributed_weights = {}
        # Agar saare modules ka data maujud hai, toh normal weights use karo.
        if not insufficient:
            redistributed_weights = self.nominal_weights.copy()
        # Agar kisi module (e.g., MARKET) ka data 'INSUFFICIENT' hai, toh uska weight baki sab me baant do.
        else:
            dropped_weight = sum(self.nominal_weights[dim] for dim in insufficient)
            remaining_weight = 1.0 - dropped_weight
            
            for dim in self.nominal_weights:
                if dim in insufficient:
                    redistributed_weights[dim] = 0.0
                else:
                    if remaining_weight > 0:
                        redistributed_weights[dim] = self.nominal_weights[dim] / remaining_weight
                    else:
                        redistributed_weights[dim] = 0.0
                        
        # Final math calculation: Har score ko uske weight se multiply karke jod do.
        composite_score = sum(dimensions[dim]["raw_score"] * redistributed_weights[dim] for dim in self.nominal_weights)
        composite_score_rounded = int(round(composite_score))
        
        # Risk Trigger Override
        # Agar overall score theek ho, par koi ek specific module completely fail ho gaya ho (Score >= 76),
        # toh final risk automatically escalate ho jayega.
        max_dim_score = max(dimensions[dim]["raw_score"] for dim in self.nominal_weights)
        
        if composite_score_rounded <= 30:
            risk_level = "LOW RISK"
            stance = "PROCEED — Standard due diligence is sufficient. No material risk factors identified across any of the 6 dimensions."
        elif composite_score_rounded <= 55:
            risk_level = "MEDIUM RISK"
            stance = "CAUTION — Proceed with enhanced due diligence focused on the specific flagged areas. Identified risk factors are manageable but require investigation before closing."
        elif composite_score_rounded <= 75:
            risk_level = "HIGH RISK"
            stance = "SIGNIFICANT CONCERNS — Extensive investigation required across multiple dimensions before proceeding. Unresolved risk factors could materially impact investment return or viability."
        else:
            risk_level = "CRITICAL RISK"
            stance = "AVOID — Material risk factors have been identified that threaten the fundamental viability or integrity of this investment. Do not proceed without resolving all flagged issues."

        # Apply risk trigger overrides
        if max_dim_score >= 76 and risk_level in ["LOW RISK", "MEDIUM RISK"]:
            risk_level = "HIGH RISK"
            stance = f"OVERRIDE (HIGH RISK) — Although the weighted score ({composite_score_rounded}) is low, a critical risk (raw score >= 76) was detected in one or more dimensions, triggering an automatic risk level escalation. Proceed with extreme caution."
        elif max_dim_score >= 56 and risk_level == "LOW RISK":
            risk_level = "MEDIUM RISK"
            stance = f"OVERRIDE (MEDIUM RISK) — Although the weighted score ({composite_score_rounded}) is low, a high risk (raw score >= 56) was detected in one or more dimensions, triggering an automatic risk level escalation."

        db_override = getattr(self.processor, "investment_stance_override", None)
        db_triggered = getattr(self.processor, "deal_breaker_status", False)
        
        # Deal Breaker Override Fix:
        # Agar Module 7 ne 'AVOID' flag set kiya hai, toh Stance ke sath-sath Risk Level ko bhi 'CRITICAL' karna zaroori hai.
        if db_triggered and db_override == "AVOID":
            stance = "AVOID"
            risk_level = "CRITICAL RISK"
        elif db_triggered and db_override == "ENHANCED_DD":
            stance = "ENHANCED_DD"
            if risk_level in ["LOW RISK", "MEDIUM RISK"]:
                risk_level = "HIGH RISK"
            
        if insufficient:
            stance += f" Note: The {', '.join(insufficient)} dimension(s) could not be fully assessed this run (Market Intelligence Agent data unavailable) and its weight was proportionally redistributed across the other dimensions; consider re-running this analysis once market intelligence data is available before finalizing an investment decision."
            
        market_available = 0 if "MARKET" in insufficient else 1
        
        def get_dim_level(dim):
            sc = dimensions[dim]["raw_score"]
            if sc <= 30: return "LOW"
            if sc <= 55: return "MEDIUM"
            if sc <= 75: return "HIGH"
            return "CRITICAL"
            
        heat_map = {
            "dimensions": ["Financial", "Market", "Operational", "Legal", "Management", "ESG"],
            "levels": ["LOW (0-30)", "MEDIUM (31-55)", "HIGH (56-75)", "CRITICAL (76-100)"],
            "scores": {
                "Financial": dimensions.get("FINANCIAL", {}).get("raw_score", 0),
                "Market": dimensions.get("MARKET", {}).get("raw_score", 0),
                "Operational": dimensions.get("OPERATIONAL", {}).get("raw_score", 0),
                "Legal": dimensions.get("LEGAL", {}).get("raw_score", 0),
                "Management": dimensions.get("MANAGEMENT", {}).get("raw_score", 0),
                "ESG": dimensions.get("ESG", {}).get("raw_score", 0)
            },
            "weights_used": {
                "Financial": redistributed_weights["FINANCIAL"],
                "Market": redistributed_weights["MARKET"],
                "Operational": redistributed_weights["OPERATIONAL"],
                "Legal": redistributed_weights["LEGAL"],
                "Management": redistributed_weights["MANAGEMENT"],
                "ESG": redistributed_weights["ESG"]
            },
            "data_completeness": {
                "Financial": dimensions.get("FINANCIAL", {}).get("data_completeness", "INSUFFICIENT_DATA"),
                "Market": dimensions.get("MARKET", {}).get("data_completeness", "INSUFFICIENT_DATA"),
                "Operational": dimensions.get("OPERATIONAL", {}).get("data_completeness", "INSUFFICIENT_DATA"),
                "Legal": dimensions.get("LEGAL", {}).get("data_completeness", "INSUFFICIENT_DATA"),
                "Management": dimensions.get("MANAGEMENT", {}).get("data_completeness", "INSUFFICIENT_DATA"),
                "ESG": dimensions.get("ESG", {}).get("data_completeness", "INSUFFICIENT_DATA")
            },
            "heat_map_matrix": [
                ["Financial", get_dim_level("FINANCIAL")],
                ["Market", get_dim_level("MARKET")],
                ["Operational", get_dim_level("OPERATIONAL")],
                ["Legal", get_dim_level("LEGAL")],
                ["Management", get_dim_level("MANAGEMENT")],
                ["ESG", get_dim_level("ESG")]
            ]
        }
        
        self.processor.risk_heat_map = heat_map
        
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS composite_risk_output (
                company_ticker TEXT PRIMARY KEY, composite_score INTEGER,
                risk_level TEXT, investment_stance TEXT,
                market_risk_data_available INTEGER, weights_used TEXT, heat_map_json TEXT, scored_at TEXT
            )
        """))
        
        for dim, weight in redistributed_weights.items():
            sc = dimensions[dim]["raw_score"]
            db.execute(text("""
                UPDATE risk_dimensions 
                SET weight = :w, weighted_score = :ws 
                WHERE company_ticker = :t AND dimension = :d
            """), {"w": weight, "ws": sc * weight, "t": self.ticker, "d": dim})
            
        db.execute(text("""
            INSERT INTO composite_risk_output (company_ticker, composite_score, risk_level, investment_stance, market_risk_data_available, weights_used, heat_map_json, scored_at)
            VALUES (:t, :cs, :rl, :is, :ma, :wu, :hm, :sa)
            ON CONFLICT(company_ticker) DO UPDATE SET
                composite_score=excluded.composite_score,
                risk_level=excluded.risk_level,
                investment_stance=excluded.investment_stance,
                market_risk_data_available=excluded.market_risk_data_available,
                weights_used=excluded.weights_used,
                heat_map_json=excluded.heat_map_json,
                scored_at=excluded.scored_at
        """), {
            "t": self.ticker, "cs": composite_score_rounded, "rl": risk_level, "is": stance,
            "ma": market_available, "wu": json.dumps(heat_map["weights_used"]), "hm": json.dumps(heat_map),
            "sa": datetime.now(timezone.utc).isoformat() + "Z"
        })
        
        db.dispose()
        
        msg = f"Composite score: {composite_score_rounded}/100 ({risk_level}). Investment stance: {stance.split('—')[0].strip() if '—' in stance else stance.split()[0]}. Deal breaker: {'triggered' if db_triggered else 'none triggered'}."
        if insufficient:
            msg += f" Weight redistribution applied: {', '.join(insufficient)} data unavailable, weight redistributed to remaining dimensions."
            
        self.processor.log_audit("MODULE_8_COMPOSITE_SCORING", "COMPLETED", msg + f" Final Result: Score {composite_score_rounded}/100. Risk Level: {risk_level}. Investment Stance: {stance}.")

    def run(self):
        self.evaluate()
