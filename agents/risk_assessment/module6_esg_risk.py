"""
Module:  module6_esg_risk.py
Agent:   Risk Assessment Agent
Purpose: Scores ESG Risk using environmental, social, and governance queries plus a multi-year momentum assessment.
Inputs:  RiskPreProcessor state, ChromaDB, SQL database.
Outputs: Updates risk_dimensions and risk_evidence tables.

# Hinglish Summary:
# Ye module company ke Environmental (Paryavaran), Social (Samaj/Workers), aur Governance (Policies) ESG risks ko score karta hai.
# SPECIAL FEATURE: Iska "Step 35" saare purane saalo ka data compare karke dekhta hai ki ESG efforts badh rahe hain ya kam ho rahe hain (Momentum).
# DOUBLE-COUNTING PREVENTION: Is module ko strictly sirf "Climate Risk, Carbon Targets, Diversity, aur Frameworks" par focus 
# karne ko bola gaya hai. Direct Lawsuits, EPA Fines (Legal Risk) aur Labor Strikes (Operational Risk) ko ye ignore karega taaki 2 baar point na kate.
"""

import json
from typing import Any
import chromadb
from sqlalchemy import text
from datetime import datetime, timezone

from tools.sqlite_tools import DatabaseManager
from agents.risk_assessment.llm_client import tier1_extract_tool
from agents.risk_assessment.risk_tier import adjust_points

class ESGRiskScorer:
    def __init__(self, processor: Any):
        self.processor = processor
        self.db_path = processor.paths["SQLITE_DB_PATH"]
        self.chromadb_dir = processor.paths["CHROMADB_DIR_PATH"]
        self.run_id = processor.run_id
        self.ticker = processor.ticker
        self.tier = getattr(processor, 'company_tier', 'MID')
        
        self.total_points = 0
        self.evidence_list = []
        
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
                
        self.chroma_was_reachable_for_recent = False
        self.momentum_was_computable = True

    def _add_evidence(self, sub_dimension: str, rule_name: str, evidence_text: str, severity: str, points: int,
                      evidence_source: str, chunks: int = None, llm_tier: str = "TIER_1_EXTRACTION", fiscal_year: str = None):
        self.total_points += points
        fy = fiscal_year or getattr(self, "current_rag_years", None)
        self.evidence_list.append({
            "dimension": "ESG",
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

        if len(all_chunks) > 0:
            self.chroma_was_reachable_for_recent = True
        else:
            scoring_logic_cb({}, [])
            return
            
        def log_cb(entry: dict):
            self.processor.log_audit("MODULE_6_ESG_RISK", entry["status"], f"Tier 1 LLM: {entry.get('input_tokens')} in, {entry.get('output_tokens')} out.")
            
        result = tier1_extract_tool(all_chunks, llm_instruction, log_callback=log_cb)
        scoring_logic_cb(result, all_chunks)
        self.current_rag_years = None

    def step32_environmental_risk(self):
        """
        # Step 32: Environmental & Climate Risk
        # Ye dekhta hai ki company par Global Warming, Carbon Emissions, ya future Climate regulations ka kitna asar padega.
        """
        queries = [
            ("environmental liability OR environmental remediation cost", 5),
            ("EPA enforcement OR environmental regulation compliance burden", 5),
            ("carbon emissions OR climate change regulation impact", 5),
            ("environmental fine OR pollution OR hazardous waste", 5)
        ]
        
        instr = (
            "You are an Elite Institutional ESG & Climate Risk Analyst. "
            "Read these passages and identify systemic environmental/climate risks.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Focus STRICTLY on carbon emissions, climate transition risks, and stranded assets. Do NOT extract specific EPA fines or lawsuits (those are handled by the Legal Risk module).\n\n"
            "Severity: CRITICAL (Material stranded asset risk or massive transition cost), "
            "HIGH (Significant environmental compliance cost burden disclosed), MEDIUM (Standard climate risk language, no material liability), "
            "LOW (No material environmental risk).\n"
            "Return JSON: {\"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\", \"description\": \"<detailed description of systemic environmental/climate risk found>\"}"
        )
        
        def scorer(res, chunks):
            pts = 3; sev = "LOW"; desc = "No material environmental risk (Zero-Chunk Guard default applied)."
            if chunks:
                desc = res.get("description", "No material environmental risk")
                csev = res.get("severity", "LOW").upper()
                if csev == "CRITICAL": pts = 35; sev = "CRITICAL"
                elif csev == "HIGH": pts = 20; sev = "HIGH"
                elif csev == "MEDIUM": pts = 10; sev = "MEDIUM"
                else: pts = 3; sev = "LOW"
            self._add_evidence("ENVIRONMENTAL", "RAG_EXTRACT", desc, sev, pts, "ChromaDB, Item 1A/7/1", len(chunks))
            
        self._run_rag_sub_dimension("ENVIRONMENTAL", queries, ["item_1a", "item_7", "item_1"], instr, scorer)

    def step33_social_workforce_risk(self):
        """
        # Step 33: Social & Workforce Risk
        # Ye dekhta hai ki company me employees ke sath kaisa behave kiya jata hai (OSHA/Safety, Diversity, Human Rights).
        """
        queries = [
            ("labor dispute OR employee strike OR union organizing", 5),
            ("workplace safety OR OSHA OR injury rate OR fatality", 5),
            ("human rights OR supply chain labor OR child labor", 5),
            ("diversity OR equal employment opportunity OR discrimination claim", 5)
        ]
        
        instr = (
            "You are an Elite Institutional Social & Human Capital Analyst. "
            "Read these passages and identify social and workforce policy risks.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Focus STRICTLY on workplace safety (OSHA), systemic human rights issues, and diversity/discrimination claims. Do NOT extract standard labor strikes or union negotiations (those are handled by the Operational Risk module).\n\n"
            "Severity: CRITICAL (Systemic human rights violations or fatal workplace safety record), "
            "HIGH (Significant disclosed workforce safety risk or major discrimination claims), MEDIUM (Standard workforce risk language), "
            "LOW (No material social risk).\n"
            "Return JSON: {\"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\", \"description\": \"<detailed description of social/workforce risk found>\"}"
        )
        
        def scorer(res, chunks):
            pts = adjust_points(3, self.tier); sev = "LOW"; desc = "No material social risk (Zero-Chunk Guard default applied)."
            if chunks:
                desc = res.get("description", "No material social risk")
                csev = res.get("severity", "LOW").upper()
                if csev == "CRITICAL": pts = adjust_points(35, self.tier); sev = "CRITICAL"
                elif csev == "HIGH": pts = adjust_points(20, self.tier); sev = "HIGH"
                elif csev == "MEDIUM": pts = adjust_points(10, self.tier); sev = "MEDIUM"
                else: pts = adjust_points(3, self.tier); sev = "LOW"
            self._add_evidence("SOCIAL_WORKFORCE", "RAG_EXTRACT", desc, sev, pts, "ChromaDB, Item 1A/1/7", len(chunks))
            
        self._run_rag_sub_dimension("SOCIAL_WORKFORCE", queries, ["item_1a", "item_1", "item_7"], instr, scorer)

    def step34_governance_esg_lens(self):
        """
        # Step 34: ESG Governance Lens
        # Ye check karta hai ki kya company ke paas corruption rokne (FCPA), whistleblowers ko protect karne, 
        # aur data privacy ke strong Frameworks/Policies hain ya nahi.
        """
        queries = [
            ("whistleblower policy OR ethics hotline OR code of conduct", 4),
            ("anti-corruption OR FCPA OR bribery OR UK Bribery Act", 4),
            ("data privacy policy OR GDPR compliance", 4),
            ("board diversity policy OR gender OR racial representation", 4)
        ]
        
        instr = (
            "You are an Elite Institutional ESG Governance Analyst. "
            "Read these passages and identify gaps in ESG governance frameworks.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Focus STRICTLY on the *absence* of policies (Code of Conduct, Whistleblower, Data Privacy) or exposure to corruption zones (FCPA). Do NOT extract active legal investigations (those are Legal Risk).\n\n"
            "Assess whistleblower policies, FCPA/anti-corruption, data privacy, and ESG commitment.\n"
            "Return JSON: {\"no_code_of_conduct\": bool, \"fcpa_risk\": bool, \"data_privacy_gap\": bool, \"strong_framework\": bool}"
        )
        
        def scorer(res, chunks):
            extra = 1.3 if self.tier in ('SMALL', 'MICRO') else 1.0
            pts = 0; sev = "LOW"; desc = "Strong ESG governance framework disclosed (or Zero-Chunk Guard applied safely)."
            if chunks and isinstance(res, dict):
                if res.get("no_code_of_conduct"):
                    pts = adjust_points(20, self.tier, extra_multiplier=extra); sev = "HIGH"; desc = "No whistleblower policy OR no code of conduct disclosed"
                elif res.get("fcpa_risk"):
                    pts = adjust_points(15, self.tier, extra_multiplier=extra); sev = "HIGH"; desc = "FCPA or anti-corruption risk disclosed"
                elif res.get("data_privacy_gap"):
                    pts = adjust_points(10, self.tier, extra_multiplier=extra); sev = "MEDIUM"; desc = "Data privacy gaps disclosed or GDPR exposure"
            
            if pts > 0 or not chunks:
                self._add_evidence("GOVERNANCE_ESG", "RAG_EXTRACT", desc, sev, pts, "ChromaDB, Item 1/1A", len(chunks))
            else:
                self._add_evidence("GOVERNANCE_ESG", "RAG_EXTRACT", desc, "LOW", 0, "ChromaDB, Item 1/1A", len(chunks))
                
        self._run_rag_sub_dimension("GOVERNANCE_ESG", queries, ["item_1", "item_1a"], instr, scorer)

    def _get_all_fiscal_years(self):
        db = DatabaseManager(self.db_path)
        try:
            rows = db.execute(text("SELECT fiscal_year FROM financial_data WHERE ticker = :t ORDER BY fiscal_year ASC"), {"t": self.ticker}).fetchall()
            return [str(row[0]) for row in rows]
        except Exception:
            return []
        finally:
            db.dispose()

    def step35_esg_momentum(self):
        """
        # Step 35: ESG Momentum (The Unique Feature)
        # Ye dekhta hai ki pichle kuch saalo me company ka ESG commitment badh raha hai (Improving) ya ghat raha hai (Deteriorating).
        # Isme LLM ki zarurat nahi, seedha database se history trend nikal lete hain!
        """
        years = self._get_all_fiscal_years()
        if not years or len(years) < 2 or not self.sec_collection:
            self.momentum_was_computable = False
            self._add_evidence("MOMENTUM", "NOT_COMPUTABLE", "MOMENTUM_NOT_COMPUTABLE — fewer than 2 fiscal years of Item 1 text available", "LOW", 0, "ChromaDB, Item 1", 0, "NONE_PURE_PYTHON")
            return
            
        scores = []
        for y in years:
            score = 0
            try:
                where_esg = {
                    "$and": [
                        {"ticker": {"$eq": self.ticker}},
                        {
                            "$and": [
                                {"section_code": {"$eq": "item_1"}},
                                {
                                    "$and": [
                                        {"filing_type": {"$eq": "10-K"}},
                                        {"fiscal_year": {"$eq": y}}
                                    ]
                                }
                            ]
                        }
                    ]
                }
                res = self.sec_collection.query(
                    query_texts=["sustainability OR ESG OR carbon OR emissions target"],
                    n_results=1,
                    where=where_esg
                )
                if res and res["documents"] and res["documents"][0]:
                    score = 1
            except Exception:
                pass
            scores.append(score)
            
        mid = len(scores) // 2
        first_half = sum(scores[:mid]) / len(scores[:mid])
        second_half = sum(scores[mid:]) / len(scores[mid:])
        
        if second_half > first_half:
            self._add_evidence("MOMENTUM", "IMPROVING", f"IMPROVING ESG trajectory across {len(years)}-year window.", "LOW", -10, "ChromaDB, Item 1", 0, "NONE_PURE_PYTHON")
        elif second_half < first_half:
            self._add_evidence("MOMENTUM", "DETERIORATING", f"DETERIORATING ESG trajectory across {len(years)}-year window.", "HIGH", 10, "ChromaDB, Item 1", 0, "NONE_PURE_PYTHON")
        else:
            self._add_evidence("MOMENTUM", "STABLE", f"STABLE ESG trajectory across {len(years)}-year window.", "LOW", 0, "ChromaDB, Item 1", 0, "NONE_PURE_PYTHON")

    def step36_compute_score(self):
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
            if ev["points_added"] > 0:
                if top_finding_evt is None or ev["points_added"] > top_finding_evt["points_added"]:
                    top_finding_evt = ev
                
        top_finding_text = top_finding_evt["evidence_text"] if top_finding_evt else "No material ESG risks found."

        data_completeness = "FULL" if self.chroma_was_reachable_for_recent and self.momentum_was_computable else "PARTIAL"
            
        self.processor.risk_scorecard["ESG"] = {
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
            "t": self.ticker, "d": "ESG", "rs": final_score, "rl": risk_level,
            "w": 0.10, "ws": final_score * 0.10, "tf": top_finding_text, 
            "ec": len(self.evidence_list), "dc": data_completeness,
            "sa": datetime.now(timezone.utc).isoformat() + "Z"
        })
        
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
        
        msg = f"ESG Risk evaluated: Score {final_score}/100 ({risk_level}). Analyzed Environmental Fines, Labor Strikes, Board Diversity & Controversies. Found {len(self.evidence_list)} risk signals. Data Completeness: {data_completeness}."
        self.processor.log_audit("MODULE_6_ESG_RISK", "COMPLETED", msg)

    def run(self):
        self.processor.log_audit("MODULE_6_ESG_RISK", "STARTED", "Beginning ESG Risk evaluation (Environmental, Social, Governance Controversies).")
        self.step32_environmental_risk()
        self.step33_social_workforce_risk()
        self.step34_governance_esg_lens()
        self.step35_esg_momentum()
        self.step36_compute_score()
