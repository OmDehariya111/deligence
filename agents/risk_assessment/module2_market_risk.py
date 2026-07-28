"""
Module:  module2_market_risk.py
Agent:   Risk Assessment Agent
Purpose: Scores the Market Risk dimension using Market Intelligence signals and Item 7A RAG.
Inputs:  RiskPreProcessor state
Outputs: Updates risk_dimensions and risk_evidence tables via DatabaseManager.

# Hinglish Summary:
# Ye module Market Risks (jaise Interest Rates, Foreign Exchange, Commodities) ka assessment karta hai.
# Ye pichle agent (Market Intelligence) ke output se signals uthata hai, aur company ke "Moat" (competitive advantage) 
# ko dekhta hai. Agar moat weak (NARROW) hai, toh ye extra risk points deta hai.
# DOUBLE-COUNTING PREVENTION: Ye module 'item_1a' padhta hai, isliye iska LLM prompt AI ko strictly force karega
# ki wo legal ya operational issues ko ignore karke sirf Quantitative Market Exposures par focus kare.
"""

import json
from typing import Any
import chromadb
from sqlalchemy import text
from datetime import datetime, timezone

from tools.sqlite_tools import DatabaseManager
from agents.risk_assessment.llm_client import tier1_extract_tool
from agents.risk_assessment.risk_tier import adjust_points, is_crisis_keyword_universal

class MarketRiskScorer:
    def __init__(self, processor: Any):
        self.processor = processor
        self.db_path = processor.paths["SQLITE_DB_PATH"]
        self.chromadb_dir = processor.paths["CHROMADB_DIR_PATH"]
        self.run_id = processor.run_id
        self.ticker = processor.ticker
        self.tier = getattr(processor, 'company_tier', 'MID')
        # Sentiment dampening multipliers by tier
        self._sentiment_mult = {
            "MEGA": 0.30, "LARGE": 0.50, "MID": 1.00, "SMALL": 1.30, "MICRO": 1.60
        }.get(self.tier, 1.0)
        
        self.total_points = 0
        self.evidence_list = []

    def _add_evidence(self, sub_dimension: str, rule_name: str, evidence_text: str, severity: str, points: int,
                      evidence_source: str = "Market Intelligence", chunks: int = None, llm_tier: str = "NONE_PURE_PYTHON", fiscal_year: str = None):
        self.total_points += points
        fy = fiscal_year or getattr(self, "current_rag_years", None)
        self.evidence_list.append({
            "dimension": "MARKET",
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

    def step9_market_signals(self):
        """
        # Step 9: Market Intelligence Signals
        # Ye pichle agent (Market Intel) se negative news, competitor pressure ya macro risks ke points uthata hai.
        # Isme 'sentiment_mult' use hota hai (Mega caps ko negative news kam affect karti hai, startups ko zyada).
        """
        if not self.processor.market_intel_available:
            self.processor.log_audit("MODULE_2_MARKET_RISK", "INFO", 
                "market_risk_signals plug-in skipped — Market Intelligence Agent output unavailable this run.")
            return

        # Read market risk signals
        db = DatabaseManager(self.db_path)
        try:
            rows = db.execute(
                text("SELECT * FROM market_risk_signals")
            ).fetchall()
        except Exception:
            rows = []
        finally:
            db.dispose()

        if not rows:
            self.processor.log_audit("MODULE_2_MARKET_RISK", "INFO", 
                "market_risk_signals table present but empty for this ticker.")
            return

        for row in rows:
            r = dict(row._mapping)
            signal_name = r.get("signal_name", "")
            evidence_txt = r.get("evidence_text", "Market signal")
            base_pts = r.get("points_contribution", 0)
            severity = r.get("risk_level", "LOW")

            # Universal crisis keywords bypass dampening
            if is_crisis_keyword_universal(evidence_txt) or is_crisis_keyword_universal(signal_name):
                final_pts = base_pts  # no dampening
            else:
                final_pts = round(base_pts * self._sentiment_mult)
                final_pts = max(0, final_pts)

            self._add_evidence(
                sub_dimension=r.get("signal_category", "UNKNOWN_CATEGORY"),
                rule_name="MARKET_SIGNAL",
                evidence_text=evidence_txt,
                severity=severity,
                points=final_pts,
                evidence_source=f"market_risk_signals table, signal_id_{r.get('signal_id', 'unknown')}"
            )

    def step10_moat_adjustment(self):
        """
        # Step 10: Moat Adjustment
        # Ye dekhta hai ki company market competition me kitni strong hai.
        # NARROW = 20 risk points (Bina structural advantage ke market me tikna mushkil hai)
        # MODERATE = 10 risk points, WIDE = 0 points.
        """
        if not self.processor.market_intel_available:
            # Skip adjustment entirely
            return

        moat = self.processor.moat_width.upper() if self.processor.moat_width else "UNKNOWN"
        
        if moat == "NARROW":
            self._add_evidence(
                sub_dimension="COMPETITIVE_MOAT",
                rule_name="MOAT_ADJUSTMENT",
                evidence_text="Target has a NARROW competitive moat — intensely contested market with no identified structural advantage over rivals.",
                severity="HIGH",
                points=20
            )
        elif moat == "MODERATE":
            self._add_evidence(
                sub_dimension="COMPETITIVE_MOAT",
                rule_name="MOAT_ADJUSTMENT",
                evidence_text="Target has a MODERATE competitive moat — some advantages present but not durable enough to be classified as WIDE.",
                severity="MEDIUM",
                points=10
            )
        elif moat == "WIDE":
            # 0 points, no risk evidence entry written
            pass
        elif moat == "UNKNOWN":
            # 0 points, write informational evidence per workflow
            self._add_evidence(
                sub_dimension="COMPETITIVE_MOAT",
                rule_name="MOAT_ADJUSTMENT",
                evidence_text="Competitive moat assessment unavailable this run — no adjustment applied. This is a data gap, not a finding of moat strength.",
                severity="LOW",
                points=0
            )

    def step11_chromadb_rag(self):
        if not self.processor.chromadb_available:
            self.processor.log_audit("MODULE_2_MARKET_RISK", "WARNING", "ChromaDB unavailable, Item 7A queries returning zero chunks.")
            
        queries = [
            ("interest rate risk OR variable rate debt", "interest_rate"),
            ("foreign currency risk OR exchange rate exposure", "foreign_exchange"),
            ("commodity price risk OR raw material cost exposure", "commodity"),
            ("sensitivity analysis OR market risk quantification", "sensitivity")
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
            self.processor.log_audit("MODULE_2_MARKET_RISK", entry["status"], f"Tier 1 LLM: {entry.get('input_tokens')} in, {entry.get('output_tokens')} out.")

        item_7a_points = 0
        
        chunks = []
        if client:
            try:
                res = collection.query(
                    query_texts=["interest rate risk OR variable rate debt OR foreign currency risk OR exchange rate exposure OR commodity price risk OR raw material cost OR sensitivity analysis OR market risk quantification"],
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
                                            {"section_code": {"$in": ["item_7a", "item_1a", "item_1", "item_7"]}}
                                        ]
                                    },
                                    {
                                        "$and": [
                                            {"filing_type": "10-Q"},
                                            {"section_code": {"$in": ["part1_item2", "part1_item3"]}}
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
                "dimension": "MARKET",
                "sub_dimension": "QUANTITATIVE_EXPOSURE",
                "evidence_type": "RAG_EXTRACT",
                "evidence_source": "ChromaDB",
                "evidence_text": "No chunks returned for market risk sensitivity queries — no Item 7A disclosures found.",
                "severity": "LOW",
                "points_added": 0,
                "chunks_retrieved_count": 0,
                "llm_tier_used": "NONE_ZERO_CHUNK_GUARD"
            })
        else:
            instruction = (
                "You are an Elite Institutional Financial Data Extraction Algorithm operating within a strict dimensional framework. "
                "Read this passage and identify ONLY quantitative or material market risk exposures.\n\n"
                "CRITICAL ANTI-DOUBLE-COUNTING RULE:\n"
                "Do NOT extract legal risks, lawsuits, operational disruptions, cybersecurity issues, ESG concerns, or general business risks. "
                "Extract ONLY items related to the following Market Risks:\n"
                "- Interest rate risk or variable rate debt exposure\n"
                "- Foreign currency (FX) or exchange rate exposure\n"
                "- Commodity price risk or raw material cost exposure\n\n"
                "For each valid market risk:\n"
                "1. Identify the exposure type.\n"
                "2. Extract the approximate magnitude or sensitivity (e.g. '10% decrease in FX would reduce earnings by $11,596M').\n"
                "3. Classify the severity: HIGH (material to earnings > 5% impact), MEDIUM (meaningful but manageable), LOW (immaterial).\n"
                "Return JSON: [{\"exposure_type\": \"string\", \"magnitude_description\": \"string\", \"severity\": \"string\"}]"
            )
            
            result = tier1_extract_tool(chunks, instruction, log_callback=log_cb)
            
            if isinstance(result, list):
                for exposure in result:
                    sev = exposure.get("severity", "LOW").upper()
                    base_pts = 0
                    if sev == "HIGH":
                        base_pts = 10
                    elif sev == "MEDIUM":
                        base_pts = 5
                    pts = adjust_points(base_pts, self.tier)
                    desc = exposure.get("magnitude_description", "No magnitude provided")
                    typ = exposure.get("exposure_type", "Unknown exposure")
                    
                    if item_7a_points + pts > 20:
                        pts = max(0, 20 - item_7a_points)
                    item_7a_points += pts
                    self.total_points += pts
                    
                    self.evidence_list.append({
                        "dimension": "MARKET",
                        "sub_dimension": "QUANTITATIVE_EXPOSURE",
                        "evidence_type": "RAG_EXTRACT",
                        "evidence_source": "ChromaDB, Item 7A/1A/1/7 + 10-Q RAG",
                        "evidence_text": f"{typ}: {desc}",
                        "severity": sev,
                        "points_added": pts,
                        "chunks_retrieved_count": len(chunks),
                        "llm_tier_used": "TIER_1_EXTRACTION",
                        "fiscal_year": getattr(self, "current_rag_years", None)
                    })
        self.current_rag_years = None

    def step12_score_aggregation(self):
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
                
        top_finding_text = top_finding_evt["evidence_text"] if top_finding_evt else "No material market risks found."

        # Data Completeness Assignment (Fix R-5)
        if self.processor.market_intel_available and self.processor.moat_width != "UNKNOWN":
            data_completeness = "FULL"
        elif not self.processor.market_intel_available:
            data_completeness = "INSUFFICIENT_DATA"
        else:
            data_completeness = "PARTIAL"
            
        self.processor.risk_scorecard["MARKET"] = {
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
            "t": self.ticker, "d": "MARKET", "rs": final_score, "rl": risk_level,
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
        
        msg = f"Market Risk evaluated: Score {final_score}/100 ({risk_level}). Moat and Live Market Data analyzed. Extracted {len(self.evidence_list)} risk signals. Data Completeness: {data_completeness}. Market Intel API: {'ONLINE' if self.processor.market_intel_available else 'OFFLINE'}."
        if data_completeness == "INSUFFICIENT_DATA":
            msg += " This dimension's weight will be redistributed in Module 8."
            
        self.processor.log_audit("MODULE_2_MARKET_RISK", "COMPLETED", msg)

    def run(self):
        self.processor.log_audit("MODULE_2_MARKET_RISK", "STARTED", "Beginning Market Risk evaluation (Live Signals, Moat Adjustment, Sector Competitiveness).")
        self.step9_market_signals()
        self.step10_moat_adjustment()
        self.step11_chromadb_rag()
        self.step12_score_aggregation()
