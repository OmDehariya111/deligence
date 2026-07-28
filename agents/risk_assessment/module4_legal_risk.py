"""
Module:  module4_legal_risk.py
Agent:   Risk Assessment Agent
Purpose: Scores the Legal and Regulatory Risk dimension.
Inputs:  RiskPreProcessor state
Outputs: Updates risk_dimensions and risk_evidence tables via DatabaseManager.

# Hinglish Summary:
# Ye sabse "Special" module hai! Ye company par chal rahe kisi bhi lawsuit, fine, ya SEC investigation ko pakadta hai.
# SPECIAL FEATURE: Is module me 'fiscal_year' ka filter NAHI laga hai. Ye pichle 3 saal ki har filing padhta hai 
# taaki koi chupa hua purana lawsuit bach ke na nikal jaye.
# DOUBLE-COUNTING PREVENTION: Prompts ko order diya gaya hai ki wo sirf legal matters par focus karein, 
# aur ordinary business losses (operational) ya market fluctuations (financial) ko ignore karein.
"""

import json
from typing import Any
import chromadb
from sqlalchemy import text
from datetime import datetime, timezone

from tools.sqlite_tools import DatabaseManager
from agents.risk_assessment.llm_client import tier1_extract_tool
from agents.risk_assessment.risk_tier import adjust_points, is_valid_regulator, VALID_REGULATORS

class LegalRiskScorer:
    def __init__(self, processor: Any):
        self.processor = processor
        self.db_path = processor.paths["SQLITE_DB_PATH"]
        self.chromadb_dir = processor.paths["CHROMADB_DIR_PATH"]
        self.run_id = processor.run_id
        self.ticker = processor.ticker
        self.tier = getattr(processor, 'company_tier', 'MID')
        
        self.total_points = 0
        self.evidence_list = []
        self.chunks_retrieved_any = False
        
        self.item3_found_major = False
        self.item3_found_sec = False
        self.item3_found_fraud = False
        self.found_bankruptcy_8k = False
        self.found_downgrade_8k = False
        
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
            "dimension": "LEGAL",
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
                               llm_instruction: str, scoring_logic_cb):
        
        chunks_per_query = []
        metadatas_per_query = []
        for q_text, limit in queries:
            if self.sec_collection:
                try:
                    res = self.sec_collection.query(
                        query_texts=[q_text],
                        n_results=limit,
                        where={
                            "$and": [
                                {"ticker": {"$eq": self.ticker}},
                                {
                                    "$or": [
                                        {
                                            "$and": [
                                                {"filing_type": {"$eq": "10-K"}},
                                                {"section_code": {"$in": sections}}
                                            ]
                                        },
                                        {
                                            "$and": [
                                                {"filing_type": {"$eq": "DEF 14A"}},
                                                {"section_code": {"$in": sections}}
                                            ]
                                        },
                                        {
                                            "$and": [
                                                {"filing_type": {"$eq": "10-Q"}},
                                                {"section_code": {"$in": ["part2_item1", "part2_item1a"]}}
                                            ]
                                        },
                                        {"filing_type": {"$eq": "8-K"}},
                                        {"filing_type": {"$eq": "USER_FILE"}}
                                    ]
                                }
                            ]
                        }
                    )
                    if res and res["documents"] and res["documents"][0]:
                        chunks_per_query.append(res["documents"][0][:4])
                        metadatas_per_query.append(res.get("metadatas", [[]])[0][:4])
                except Exception:
                    pass
                    
        # Round-robin merge to ensure diversity and relevance, capping at 4 chunks total
        # Keeping context small to avoid LLM API timeouts on dense legal text
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
            self.chunks_retrieved_any = True
            
        def log_cb(entry: dict):
            self.processor.log_audit("MODULE_4_LEGAL_RISK", entry["status"], f"Tier 1 LLM: {entry.get('input_tokens')} in, {entry.get('output_tokens')} out.")
            
        if len(all_chunks) == 0:
            return None
            
        # Truncate each chunk to 800 characters to prevent API timeouts on large contexts.
        # Legal filings are especially dense; shorter context = faster, more reliable LLM calls.
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
        
    def _check_news_sentiment(self, crisis_types: list):
        if not getattr(self.processor, "news_sentiment_available", False):
            self.processor.log_audit("MODULE_4_LEGAL_RISK", "INFO", 
                "news_sentiment cross-reference skipped — scored from disclosure only.")
            return []
            
        db = DatabaseManager(self.db_path)
        try:
            placeholders = ",".join([f"'{c}'" for c in crisis_types])
            sql = f"SELECT * FROM news_sentiment WHERE company_ticker = :ticker AND crisis_flag = 1 AND crisis_type IN ({placeholders})"
            rows = db.execute(text(sql), {"ticker": self.ticker}).fetchall()
            return [dict(row._mapping) for row in rows]
        except Exception:
            return []
        finally:
            db.dispose()

    def step19_active_litigation(self):
        """
        # Step 19: Active Litigation (Lawsuits & Court Cases)
        # Ye dekhta hai ki company par koi class-action, patent, ya securities fraud ka case toh nahi chal raha.
        # Alag-alag lawsuits ke alag-alag weight/points hote hain (Jaise 'Securities Fraud' sabse khatarnaak hai).
        """
        queries = [
            ("lawsuit OR legal proceedings OR class action OR securities litigation", 3),
            ("arbitration OR settlement OR alleged damages OR claims against", 3),
            ("shareholder lawsuit OR class action OR patent infringement", 3)
        ]
        
        instr = (
            "You are an Elite Institutional Legal Risk Assessor. "
            "Read these Legal Proceedings passages and extract ONLY formal, active, or recently settled litigation.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Ignore standard operational disruptions (e.g. factory closures), market fluctuations, or debt covenant warnings unless they are actively being litigated in court.\n\n"
            "For each disclosed legal matter, extract:\n"
            "1. Type: SECURITIES_LITIGATION / PATENT / PRODUCT_LIABILITY / ANTITRUST / EMPLOYMENT / REGULATORY / OTHER\n"
            "2. Plaintiff or regulator\n"
            "3. Estimated monetary exposure if disclosed\n"
            "4. Status: PENDING / RECENTLY_SETTLED / APPEAL / DISMISSED\n"
            "5. Severity: CRITICAL (>10% of revenue exposure or securities fraud), HIGH (material but bounded), MEDIUM, LOW.\n"
            "Return JSON: [{\"type\": \"SECURITIES_LITIGATION/PATENT/PRODUCT_LIABILITY/ANTITRUST/EMPLOYMENT/REGULATORY/OTHER\", \"plaintiff\": \"<plaintiff or regulator name>\", \"exposure\": \"<estimated monetary exposure>\", \"status\": \"PENDING/RECENTLY_SETTLED/APPEAL/DISMISSED\", \"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\"}]"
        )
        
        def scorer(res, chunks):
            if isinstance(res, list):
                high_count = 0
                medium_count = 0
                for matter in res:
                    m_type = matter.get("type", "")
                    sev = matter.get("severity", "LOW").upper()
                    if m_type == "SECURITIES_LITIGATION":
                        self.item3_found_sec = True
                        self.item3_found_fraud = True
                        
                    csev = sev
                    ctype = m_type
                    pts = 0
                    # Base points by litigation type
                    if ctype in ("SECURITIES_LITIGATION", "CLASS_ACTION"):
                        base = {"CRITICAL": 25, "HIGH": 15, "MEDIUM": 8}.get(csev, 0)
                    elif ctype == "ANTITRUST":
                        base = {"CRITICAL": 20, "HIGH": 12, "MEDIUM": 6}.get(csev, 0)
                    elif ctype in ("PRODUCT_LIABILITY", "ENVIRONMENTAL"):
                        base = {"CRITICAL": 12, "HIGH": 8, "MEDIUM": 4}.get(csev, 0)
                    elif ctype in ("PATENT", "IP"):
                        base = {"CRITICAL": 10, "HIGH": 7, "MEDIUM": 4}.get(csev, 0)
                    elif ctype == "EMPLOYMENT":
                        base = {"CRITICAL": 8, "HIGH": 5, "MEDIUM": 3}.get(csev, 0)
                    else:
                        base = {"CRITICAL": 6, "HIGH": 4, "MEDIUM": 2}.get(csev, 0)
                    pts = adjust_points(base, self.tier)

                    if csev == "CRITICAL":
                        self._add_evidence("LITIGATION", "CRITICAL_LAWSUIT", f"Critical litigation: {ctype}", "CRITICAL", pts, "ChromaDB, Item 3", len(chunks))
                        self.item3_found_major = True
                    elif csev == "HIGH":
                        if high_count < 2:
                            high_count += 1
                            self._add_evidence("LITIGATION", "HIGH_LAWSUIT", f"High litigation: {ctype}", "HIGH", pts, "ChromaDB, Item 3", len(chunks))
                    elif csev == "MEDIUM":
                        if medium_count < 2:
                            medium_count += 1
                            self._add_evidence("LITIGATION", "MEDIUM_LAWSUIT", f"Medium litigation: {ctype}", "MEDIUM", pts, "ChromaDB, Item 3", len(chunks))
                            
        self._run_rag_sub_dimension("LITIGATION", queries, ["item_3", "item_8", "item_1a", "item_1"], instr, scorer)
        
        news = self._check_news_sentiment(['MAJOR_LAWSUIT', 'SEC_INVESTIGATION', 'FRAUD_ALLEGATION'])
        for n in news:
            c_type = n.get("crisis_type")
            if c_type == 'MAJOR_LAWSUIT' and self.item3_found_major: continue
            if c_type == 'SEC_INVESTIGATION' and self.item3_found_sec: continue
            if c_type == 'FRAUD_ALLEGATION' and self.item3_found_fraud: continue
            
            self._add_evidence("LITIGATION", "NEWS_CRISIS_FLAG", f"News confirms new {c_type}", "HIGH", 10, "news_sentiment", 0, "NONE_PURE_PYTHON")

    def step20_regulatory_investigations(self):
        """
        # Step 20: Regulatory Investigations (SEC / DOJ)
        # Agar government agency (SEC, DOJ, FTC) company par investigation kar rahi hai, toh ye CRITICAL risk hai.
        # Isme 'tier dampening' apply NAHI hota, kyunki SEC/DOJ har company (chahe Mega ho ya Micro) ke liye equal risk hain!
        """
        queries = [
            ("SEC investigation OR enforcement action OR DOJ investigation", 3),
            ("regulatory fine OR penalty OR FTC antitrust", 3),
            ("GDPR OR CCPA OR FDA warning letter", 3)
        ]
        
        instr = (
            "You are an Elite Chief Compliance Officer. "
            "Identify any government or regulatory investigations/enforcement actions.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Focus STRICTLY on government regulators (SEC, DOJ, FTC, FDA, etc.). Do NOT extract private civil lawsuits (those belong to Active Litigation). Ignore standard operational compliance audits.\n\n"
            "For each finding:\n"
            "1. Which regulatory body?\n"
            "2. Nature of investigation?\n"
            "3. Status: disclosed / informal inquiry / formal investigation / settled?\n"
            "Return JSON: [{\"regulator\": \"<regulatory body name>\", \"nature\": \"<nature of investigation>\", \"status\": \"disclosed/informal inquiry/formal investigation/settled\", \"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\"}]"
        )
        
        def scorer(res, chunks):
            if isinstance(res, list):
                seen_regulators = set()
                for matter in res:
                    reg = matter.get("regulator", "").upper()
                    status = matter.get("status", "").lower()
                    
                    # Dedup: skip if we already logged this regulator
                    dedup_key = f"{reg}_{status}"
                    if dedup_key in seen_regulators:
                        continue
                    seen_regulators.add(dedup_key)
                    
                    regulator = matter.get("regulator", "")
                    if not is_valid_regulator(regulator):
                        continue

                    csev = matter.get("severity", "LOW").upper()
                    rtype = reg  # reg is already uppercased
                    pts = 0
                    sev = "LOW"
                    is_formal = rtype in ("SEC", "DOJ", "ANTITRUST", "CRIMINAL", "FORMAL_INVESTIGATION") or csev == "CRITICAL"
                    if is_formal:
                        pts = 30; sev = "CRITICAL"  # Universal red flag - no tier scaling
                    elif csev == "HIGH":
                        pts = adjust_points(10, self.tier); sev = "HIGH"
                    elif csev == "MEDIUM":
                        pts = adjust_points(5, self.tier); sev = "MEDIUM"

                    if pts > 0:
                        self._add_evidence("REGULATORY", "RAG_EXTRACT", f"{reg} Investigation: {status}", sev, pts, "ChromaDB, Item 1A/3/7", len(chunks))
                        
        self._run_rag_sub_dimension("REGULATORY", queries, ["item_1a", "item_1", "item_3", "item_7", "item_8"], instr, scorer)
        
        news = self._check_news_sentiment(['SEC_INVESTIGATION', 'FRAUD_ALLEGATION'])
        for n in news:
            c_type = n.get("crisis_type")
            if c_type == 'SEC_INVESTIGATION' and not self.item3_found_sec:
                self._add_evidence("REGULATORY", "NEWS_CRISIS_FLAG", f"News confirms {c_type} not in filings", "HIGH", 10, "news_sentiment", 0, "NONE_PURE_PYTHON")
            elif c_type == 'FRAUD_ALLEGATION' and not self.item3_found_fraud:
                self._add_evidence("REGULATORY", "NEWS_CRISIS_FLAG", f"News confirms {c_type} not in filings", "HIGH", 10, "news_sentiment", 0, "NONE_PURE_PYTHON")

    def step21_ip_patent(self):
        """
        # Step 21: IP & Patent Risk
        # Agar koi aur company target company par patent chori ka ilzaam lagati hai, jisse unka core product ban ho sakta hai.
        """
        queries = [
            ("patent infringement OR intellectual property claim", 3),
            ("trade secret OR license dispute OR IP misappropriation", 3),
            ("patent cannot be protected OR IP risk", 3)
        ]
        
        instr = (
            "You are an Elite Intellectual Property Counsel. "
            "Read these passages and identify formal intellectual property risks.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Focus ONLY on patents, copyrights, and trade secrets. Ignore generic technology failures (those are Operational risks).\n\n"
            "Return severity based on: CRITICAL (threatens core revenue), HIGH (material patent claim filed against company), MEDIUM (general IP risk language), LOW (none).\n"
            "Return JSON: {\"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\", \"description\": \"<detailed description of IP risk found>\"}"
        )
        
        def scorer(res, chunks):
            pts = 0; sev = "LOW"; desc = "No significant IP risk disclosed."
            if isinstance(res, dict):
                csev = res.get("severity", "LOW").upper()
                desc = res.get("description", desc)
                if csev == "CRITICAL": pts = adjust_points(10, self.tier); sev = "CRITICAL"
                elif csev == "HIGH": pts = adjust_points(7, self.tier); sev = "HIGH"
                elif csev == "MEDIUM": pts = adjust_points(4, self.tier); sev = "MEDIUM"
                
            if pts > 0:
                self._add_evidence("IP_PATENT", "RAG_EXTRACT", desc, sev, pts, "ChromaDB, Item 1A/3", len(chunks))
                
        self._run_rag_sub_dimension("IP_PATENT", queries, ["item_1a", "item_1", "item_3", "item_8"], instr, scorer)

    def step22_environmental_compliance(self):
        """
        # Step 22: Environmental & EPA Compliance
        # Agar company par pollution/EPA ke laws break karne ka fine laga ho, ya bhari remediation (safayi) ka kharcha ho.
        """
        queries = [
            ("environmental liability OR EPA enforcement OR remediation", 3),
            ("carbon emissions regulation OR climate risk compliance", 3),
            ("environmental law OR discharge permit OR environmental penalty", 3)
        ]
        
        instr = (
            "You are an Elite ESG & Environmental Liability Auditor. "
            "Identify strict environmental or EPA liabilities.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Extract ONLY formal environmental liabilities, remediation costs, or EPA enforcement. Ignore generic weather-related supply chain risks (Operational).\n\n"
            "CRITICAL (Active EPA enforcement/material liability), HIGH (Significant regulation risk), MEDIUM (Standard environmental risk language), LOW.\n"
            "Return JSON: {\"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\", \"description\": \"<detailed description of environmental compliance risk found>\"}"
        )
        
        def scorer(res, chunks):
            pts = 0; sev = "LOW"; desc = "No environmental risk disclosed."
            if isinstance(res, dict):
                csev = res.get("severity", "LOW").upper()
                desc = res.get("description", desc)
                if csev == "CRITICAL": pts = adjust_points(10, self.tier); sev = "CRITICAL"
                elif csev == "HIGH": pts = adjust_points(7, self.tier); sev = "HIGH"
                elif csev == "MEDIUM": pts = adjust_points(4, self.tier); sev = "MEDIUM"
                
            if pts > 0:
                self._add_evidence("ENVIRONMENTAL", "RAG_EXTRACT", desc, sev, pts, "ChromaDB, Item 1A/7", len(chunks))
                
        self._run_rag_sub_dimension("ENVIRONMENTAL", queries, ["item_1a", "item_1", "item_7", "item_8"], instr, scorer)

    def step23_contract_covenant(self):
        """
        # Step 23: Contract Covenants & Change of Control
        # Agar company loan/bond ke contract conditions (covenants) tod chuki hai, jisse unko loan turant chukana pad sakta hai.
        """
        queries = [
            ("change of control provision OR debt covenant requirement", 3),
            ("covenant breach OR waiver OR credit agreement amendment", 3),
            ("termination rights acquisition OR merger OR covenant restriction", 3)
        ]
        
        instr = (
            "You are an Elite Corporate Debt Counsel. "
            "Identify covenant breaches, waivers, or change-of-control restrictions in legal agreements.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Extract ONLY the legal mechanics of the covenant (breach, waiver, default clause). Do NOT analyze the underlying financial leverage numbers (those are handled by the Financial Risk module).\n\n"
            "HIGH (Change-of-control in major debt/customer contracts or active covenant breach), MEDIUM (Covenant restrictions present but manageable), LOW.\n"
            "Return JSON: {\"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\", \"description\": \"<detailed description of covenant/change-of-control risk found>\"}"
        )
        
        def scorer(res, chunks):
            pts = 0; sev = "LOW"; desc = "No material covenant risk."
            if isinstance(res, dict):
                csev = res.get("severity", "LOW").upper()
                desc = res.get("description", desc)
                if csev in ("HIGH", "CRITICAL"): pts = adjust_points(10, self.tier); sev = "HIGH"
                elif csev == "MEDIUM": pts = adjust_points(5, self.tier); sev = "MEDIUM"
                
            if pts > 0:
                self._add_evidence("COVENANT", "RAG_EXTRACT", desc, sev, pts, "ChromaDB, Item 7/8", len(chunks))
                
        self._run_rag_sub_dimension("COVENANT", queries, ["item_7", "item_8"], instr, scorer)

    def step24_8k_crisis_events(self):
        """
        # Step 24: Direct 8-K Crisis Events
        # Ye bina LLM ke directly ChromaDB se dangerous 8-K items dhundhta hai.
        # 1.03 (Bankruptcy), 2.06 (Impairment), 3.01 (Stock delisting/Downgrade), 4.02 (Restatement of Financials).
        """
        if not self.sec_collection: return
        
        # Helper: fetch 8-K chunks by event_item using flat 3-condition $and (most reliable)
        def _get_8k(event_item: str):
            try:
                res = self.sec_collection.get(where={
                    "$and": [
                        {"ticker": {"$eq": self.ticker}},
                        {"filing_type": {"$eq": "8-K"}},
                        {"event_item": {"$eq": event_item}}
                    ]
                })
                if res and res["documents"]:
                    return res
            except Exception:
                pass
            # Fallback: get all 8-K docs and filter manually
            try:
                res_all = self.sec_collection.get(
                    where={"$and": [{"ticker": {"$eq": self.ticker}}, {"filing_type": {"$eq": "8-K"}}]}
                )
                if res_all and res_all.get("metadatas"):
                    matches = [
                        (doc, meta) for doc, meta in
                        zip(res_all.get("documents", []), res_all["metadatas"])
                        if meta and meta.get("event_item") == event_item
                    ]
                    if matches:
                        return {"documents": [m[0] for m in matches]}
            except Exception:
                pass
            return None
        
        res_103 = _get_8k("1.03")
        if res_103:
            self.found_bankruptcy_8k = True
            self._add_evidence("CRISIS_EVENTS", "8K_1.03", "8-K: Bankruptcy or Receivership filed", "CRITICAL", 25, "ChromaDB, 8-K", 0, "NONE_PURE_PYTHON")
            
        res_402 = _get_8k("4.02")
        if res_402:
            self._add_evidence("CRISIS_EVENTS", "8K_4.02", "8-K: Non-Reliance on Financial Statements", "CRITICAL", 25, "ChromaDB, 8-K", 0, "NONE_PURE_PYTHON")

        res_301 = _get_8k("3.01")
        if res_301:
            self.found_downgrade_8k = True
            self._add_evidence("CRISIS_EVENTS", "8K_3.01", "8-K: Rating Agency Actions (Downgrade)", "HIGH", 15, "ChromaDB, 8-K", 0, "NONE_PURE_PYTHON")

        res_206 = _get_8k("2.06")
        if res_206:
            self._add_evidence("CRISIS_EVENTS", "8K_2.06", "8-K: Material Impairments", "HIGH", 10, "ChromaDB, 8-K", 0, "NONE_PURE_PYTHON")
            
        news = self._check_news_sentiment(['BANKRUPTCY_SIGNAL', 'CREDIT_DOWNGRADE'])
        for n in news:
            c_type = n.get("crisis_type")
            if c_type == 'BANKRUPTCY_SIGNAL' and not self.found_bankruptcy_8k:
                self._add_evidence("CRISIS_EVENTS", "NEWS_CRISIS_FLAG", f"News confirms {c_type}", "HIGH", 15, "news_sentiment", 0, "NONE_PURE_PYTHON")
            elif c_type == 'CREDIT_DOWNGRADE' and not self.found_downgrade_8k:
                self._add_evidence("CRISIS_EVENTS", "NEWS_CRISIS_FLAG", f"News confirms {c_type}", "HIGH", 10, "news_sentiment", 0, "NONE_PURE_PYTHON")

    def step25_score_aggregation(self):
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
                
        top_finding_text = top_finding_evt["evidence_text"] if top_finding_evt else "No material legal/regulatory risks found."

        data_completeness = "FULL" if self.chunks_retrieved_any and getattr(self.processor, "news_sentiment_available", False) else "PARTIAL"
            
        self.processor.risk_scorecard["LEGAL"] = {
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
            "t": self.ticker, "d": "LEGAL", "rs": final_score, "rl": risk_level,
            "w": 0.20, "ws": final_score * 0.20, "tf": top_finding_text, 
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
        
        msg = f"Legal & Regulatory Risk evaluated: Score {final_score}/100 ({risk_level}). Processed 10-K Item 3. Analyzed Litigation, IP, Compliance, Antitrust. Extracted {len(self.evidence_list)} risk signals. Data Completeness: {data_completeness}."
        self.processor.log_audit("MODULE_4_LEGAL_RISK", "COMPLETED", msg)

    def run(self):
        self.processor.log_audit("MODULE_4_LEGAL_RISK", "STARTED", "Beginning Legal & Regulatory Risk evaluation (Litigation, IP, Antitrust).")
        self.step19_active_litigation()
        self.step20_regulatory_investigations()
        self.step21_ip_patent()
        self.step22_environmental_compliance()
        self.step23_contract_covenant()
        self.step24_8k_crisis_events()
        self.step25_score_aggregation()
