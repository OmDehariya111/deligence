"""
Module:  module3_operational_risk.py
Agent:   Risk Assessment Agent
Purpose: Scores the Operational Risk dimension.
Inputs:  RiskPreProcessor state
Outputs: Updates risk_dimensions and risk_evidence tables via DatabaseManager.

# Hinglish Summary:
# Ye module company ke 'Operational Risks' (Daily business chalane ke risks) dhundhta hai.
# Jaise: Key Person (CEO) dependency, Supply Chain tootna, Cybersecurity breach, Customer ya Geography
# par zyada depend hona. Ye ChromaDB aur SEC 8-K filings se direct evidence nikalta hai.
# DOUBLE-COUNTING PREVENTION: Ye module 'item_1a' padhta hai, isliye prompts me explicitly 
# financial (debt/loan), market (interest rate), aur legal (lawsuit) risks ko reject karne ko bola gaya hai.
"""

import json
from typing import Any
import chromadb
from sqlalchemy import text
from datetime import datetime, timezone

from tools.sqlite_tools import DatabaseManager
from agents.risk_assessment.llm_client import tier1_extract_tool
from agents.risk_assessment.risk_tier import adjust_points

class OperationalRiskScorer:
    def __init__(self, processor: Any):
        self.processor = processor
        self.db_path = processor.paths["SQLITE_DB_PATH"]
        self.chromadb_dir = processor.paths["CHROMADB_DIR_PATH"]
        self.run_id = processor.run_id
        self.ticker = processor.ticker
        
        self.total_points = 0
        self.evidence_list = []
        self.chunks_retrieved_any = False
        self.tier = getattr(processor, 'company_tier', 'MID')
        
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
                      evidence_source: str = "ChromaDB, Item 1A/1/7", chunks: int = None, llm_tier: str = "TIER_1_EXTRACTION", fiscal_year: str = None):
        self.total_points += points
        fy = fiscal_year or getattr(self, "current_rag_years", None)
        self.evidence_list.append({
            "dimension": "OPERATIONAL",
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
                                    {"filing_type": "8-K"},
                                    {
                                        "$and": [
                                            {"filing_type": "10-Q"},
                                            {"section_code": {"$in": ["part2_item1a", "part1_item2"]}}
                                        ]
                                    },
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
            self.chunks_retrieved_any = True
            
        def log_cb(entry: dict):
            self.processor.log_audit("MODULE_3_OPERATIONAL_RISK", entry["status"], f"Tier 1 LLM: {entry.get('input_tokens')} in, {entry.get('output_tokens')} out.")
            
        if len(all_chunks) == 0:
            self._add_evidence(
                sub_dimension=sub_dim_name,
                rule_name="RAG_EXTRACT",
                evidence_text="No chunks returned from ChromaDB.",
                severity="LOW",
                points=3,
                evidence_source="Zero-Chunk Guard",
                chunks=0,
                llm_tier="NONE_ZERO_CHUNK_GUARD"
            )
            return None
            
        result = tier1_extract_tool(all_chunks, llm_instruction, log_callback=log_cb)
        scoring_logic_cb(result, all_chunks)
        self.current_rag_years = None
        
    def _count_8k_events(self, condition):
        if not self.sec_collection:
            return 0
        try:
            res = self.sec_collection.get(where=condition)
            if res and res["documents"]:
                return len(res["documents"])
        except Exception:
            pass
        return 0

    def step13_key_person(self):
        """
        # Step 13: Key Person Risk
        # Agar company kisi ek insaan (jaise founder/CEO) par completely depend karti hai, toh ye risk hai.
        # Agar koi succession plan (kon aage sambhalega) nahi bataya, aur 8-K (5.02) me log ja rahe hain, toh CRITICAL.
        """
        queries = [
            ("depends on key personnel OR loss of key executives", 5),
            ("founder OR co-founder is critical to operations", 5),
            ("key man OR key person risk", 5),
            ("management team departure OR retention risk", 5)
        ]
        
        where_502 = {
            "$and": [
                {"ticker": {"$eq": self.ticker}},
                {
                    "$and": [
                        {"filing_type": {"$eq": "8-K"}},
                        {"event_item": {"$eq": "5.02"}}
                    ]
                }
            ]
        }
        departures = self._count_8k_events(where_502)
        
        instr = (
            "You are an Elite Institutional Operational Risk Analyst. "
            "Read these passages and extract evidence strictly regarding 'Key Person Risk'.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Ignore all legal proceedings, debt defaults, or market fluctuations. Focus ONLY on executive leadership reliance.\n\n"
            "1. Is there explicit language indicating the company depends heavily on one or a few specific individuals?\n"
            "2. Does the company acknowledge any succession planning or lack thereof?\n"
            "3. List any specific names mentioned.\n"
            "Return JSON: {\"key_person_language\": bool, \"succession_planning_mentioned\": bool, \"specific_names_at_risk\": [\"str\"], \"severity\": \"LOW/MEDIUM/HIGH/CRITICAL\"}"
        )
        
        def scorer(res, chunks):
            pts = 3
            sev = "LOW"
            evt_text = "No explicit key person language."
            if isinstance(res, dict):
                kp_lang = res.get("key_person_language", False)
                sp_ment = res.get("succession_planning_mentioned", False)
                
                if kp_lang and not sp_ment and departures >= 2:
                    pts = adjust_points(20, self.tier); sev = "CRITICAL"
                    evt_text = f"Founder/CEO dependency + no succession plan + {departures} recent departures."
                elif kp_lang and not sp_ment:
                    pts = adjust_points(14, self.tier); sev = "HIGH"
                    evt_text = "Explicit key person language + no succession planning mentioned."
                elif kp_lang and sp_ment:
                    pts = adjust_points(8, self.tier); sev = "MEDIUM"
                    evt_text = "Implicit dependency but succession plan exists."
            
            self._add_evidence("KEY_PERSON", "RAG_EXTRACT", evt_text, sev, pts, "ChromaDB, Item 1A/1 & 8-K", len(chunks))
            
        self._run_rag_sub_dimension("KEY_PERSON", queries, ["item_1a", "item_1"], instr, scorer)

    def step14_supply_chain(self):
        """
        # Step 14: Supply Chain & Vendor Concentration
        # Agar company kisi ek (single-source) supplier par depend karti hai, toh ye operational failure ka bada reason ban sakta hai.
        # Mitigation plans (plan B) check karta hai.
        """
        queries = [
            ("single source OR sole source supplier", 5),
            ("supply chain disruption OR supply chain risk", 5),
            ("primary supplier OR key supplier OR vendor concentration", 5),
            ("raw material cost increase OR shortage", 5)
        ]
        
        instr = (
            "You are an Elite Institutional Operational Risk Analyst. "
            "Extract evidence related to Supply Chain and Vendor Concentration vulnerabilities.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Do NOT extract generic financial losses, lawsuits, or customer (buyer) concentration. Focus strictly on UPSTREAM (supplier/vendor) risks.\n\n"
            "1. Is there a single-source supplier dependency disclosed?\n"
            "2. Are there identified supply chain disruption risks?\n"
            "3. Does the company have any mitigation plans?\n"
            "4. Classify severity: CRITICAL (single-source, no alternatives), HIGH (concentrated supply, partial alternatives), MEDIUM (disclosed risk with mitigation), LOW (diversified).\n"
            "Return JSON: {\"single_source_disclosed\": bool, \"disruption_risk_disclosed\": bool, \"mitigation_mentioned\": bool, \"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\", \"evidence_quote\": \"<relevant quote from the passage>\"}"
        )
        
        def scorer(res, chunks):
            pts = 3
            sev = "LOW"
            evt_text = "No supply chain concentration disclosed."
            if isinstance(res, dict):
                ss = res.get("single_source_disclosed", False)
                mitig = res.get("mitigation_mentioned", False)
                csev = res.get("severity", "LOW").upper()
                quote = res.get("evidence_quote", "")
                
                if ss and not mitig:
                    pts = adjust_points(20, self.tier); sev = "CRITICAL"; evt_text = f"Single source disclosed, no mitigation: {quote}"
                elif csev == "HIGH" or (ss and mitig):
                    pts = adjust_points(14, self.tier); sev = "HIGH"; evt_text = f"Significant supply concentration: {quote}"
                elif csev == "MEDIUM" or mitig:
                    pts = adjust_points(8, self.tier); sev = "MEDIUM"; evt_text = f"Supply risk disclosed but mitigation plans exist: {quote}"
                    
            self._add_evidence("SUPPLY_CHAIN", "RAG_EXTRACT", evt_text, sev, pts, "ChromaDB, Item 1A/1/7", len(chunks))
            
        self._run_rag_sub_dimension("SUPPLY_CHAIN", queries, ["item_1a", "item_1", "item_7"], instr, scorer)

    def step15_tech_cyber(self):
        """
        # Step 15: Tech & Cybersecurity Risk
        # Ye dekhta hai ki past me koi hack ya data breach hua hai kya, ya systems kitne purane (obsolete) hain.
        # 8-K Item 1.05 (Material Cybersecurity Incident) ko direct check karta hai.
        """
        queries = [
            ("cybersecurity OR data breach OR cyber attack", 5),
            ("system failure OR IT infrastructure OR technology failure", 5),
            ("technology obsolescence OR platform disruption OR legacy systems", 5),
            ("cloud dependency OR third-party technology OR vendor lock-in", 5)
        ]
        
        instr = (
            "You are an Elite Cybersecurity and Operational Risk Assessor. "
            "Identify systemic IT, cloud, or cybersecurity vulnerabilities.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Do NOT extract general lawsuits (unless specifically about a cyber breach). Ignore standard financial risks.\n\n"
            "1. Any disclosed cybersecurity incidents (past breaches, active threats)?\n"
            "2. Any acknowledged technology obsolescence risk?\n"
            "3. Critical third-party technology dependency?\n"
            "4. Return severity: CRITICAL (past breach disclosed / severe obsolescence risk), HIGH (significant tech risk, no breach yet), MEDIUM (standard tech risk language), LOW (minimal).\n"
            "Return JSON: {\"past_breach_disclosed\": bool, \"tech_obsolescence_risk\": bool, \"third_party_dependency\": bool, \"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\", \"evidence_quote\": \"<relevant quote from the passage>\"}"
        )
        
        def scorer(res, chunks):
            pts = 3
            sev = "LOW"
            evt_text = "Minimal technology risk disclosed."
            if isinstance(res, dict):
                breach = res.get("past_breach_disclosed", False)
                obsol = res.get("tech_obsolescence_risk", False)
                csev = res.get("severity", "LOW").upper()
                quote = res.get("evidence_quote", "")
                
                if breach or obsol or csev == "CRITICAL":
                    pts = adjust_points(20, self.tier); sev = "CRITICAL"; evt_text = f"Disclosed past cyber breach OR severe technology obsolescence: {quote}"
                elif csev == "HIGH":
                    pts = adjust_points(14, self.tier); sev = "HIGH"; evt_text = f"Significant disclosed cyber or tech risk: {quote}"
                elif csev == "MEDIUM":
                    pts = adjust_points(8, self.tier); sev = "MEDIUM"; evt_text = f"Standard tech risk disclosures: {quote}"
                    
            self._add_evidence("TECH_CYBER", "RAG_EXTRACT", evt_text, sev, pts, "ChromaDB, Item 1A/7", len(chunks))
            
        self._run_rag_sub_dimension("TECH_CYBER", queries, ["item_1a", "item_7"], instr, scorer)

        # Deterministic 8-K Item 1.05: Material Cybersecurity Incident
        if self.sec_collection:
            try:
                res_105 = self.sec_collection.get(where={"$and": [{"ticker": self.ticker}, {"filing_type": "8-K"}, {"event_item": "1.05"}]})
                if res_105 and res_105["documents"]:
                    count = len(res_105["documents"])
                    # 8-K 1.05 is a universal red flag (mandatory SEC incident disclosure)
                    pts = min(count * 20, 30)  # no tier dampening
                    self._add_evidence(
                        "TECH_CYBER", "8K_1.05",
                        f"8-K: {count} Material Cybersecurity Incident(s) disclosed (SEC Item 1.05 mandatory 4-day disclosure)",
                        "CRITICAL", pts, "ChromaDB, 8-K Item 1.05", count, "NONE_PURE_PYTHON"
                    )
            except Exception:
                pass

    def step16_customer_concentration(self):
        """
        # Step 16: Customer Concentration Risk
        # Agar ek hi buyer (customer) total revenue ka >10% ya >50% deta hai, toh customer ke chale jane par company doob sakti hai.
        """
        queries = [
            ("customer concentration OR significant customer", 5),
            ("major customer OR largest customer OR single customer", 5),
            ("customer A OR customer 1", 5),
            ("revenue concentration OR customer dependency", 5)
        ]
        
        instr = (
            "You are an Elite Institutional Risk Analyst focusing on DOWNSTREAM Revenue Vulnerability. "
            "Extract specific data regarding customer concentration.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Focus STRICTLY on buyers (customers). Do NOT extract supplier/vendor risks (those belong to supply chain). Ignore macroeconomic risks.\n\n"
            "1. Does any single customer account for >10% of revenue?\n"
            "2. What is the approximate percentage?\n"
            "3. Is there contract renewal risk disclosed?\n"
            "Return JSON: {\"top_customer_pct\": 0.0, \"num_major_customers\": 0, \"contract_renewal_risk\": bool, \"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\"}"
        )
        
        def scorer(res, chunks):
            pts = 3
            sev = "LOW"
            evt_text = "No material customer concentration."
            if isinstance(res, dict):
                pct = res.get("top_customer_pct") or 0.0
                csev = res.get("severity", "LOW").upper()
                
                if pct > 50 or csev == "CRITICAL":
                    pts = adjust_points(20, self.tier); sev = "CRITICAL"; evt_text = f"Top customer > 50% revenue ({pct}%)"
                elif pct >= 25 or csev == "HIGH":
                    pts = adjust_points(14, self.tier); sev = "HIGH"; evt_text = f"Top customer 25-50% OR top 3 > 60% ({pct}%)"
                elif pct >= 10 or csev == "MEDIUM":
                    pts = adjust_points(8, self.tier); sev = "MEDIUM"; evt_text = f"Top customer 10-25% ({pct}%)"
                    
            self._add_evidence("CUSTOMER_CONCENTRATION", "RAG_EXTRACT", evt_text, sev, pts, "ChromaDB, Item 1A/1/7", len(chunks))
            
        self._run_rag_sub_dimension("CUSTOMER_CONCENTRATION", queries, ["item_1a", "item_1", "item_7"], instr, scorer)

    def step17_geographic_concentration(self):
        """
        # Step 17: Geographic Concentration & Sanctions Risk
        # Agar company ka zyadatar business aise desho se aata hai jahan political tensions (jaise China/Russia/OFAC countries) hain.
        """
        queries = [
            ("geographic concentration OR country risk OR revenue by geography", 5),
            ("international operations OR emerging markets risk", 5),
            ("political risk OR regulatory risk in specific country", 5),
            ("foreign currency risk OR exchange rate impact", 5)
        ]
        
        instr = (
            "You are an Elite Geopolitical Risk Analyst. "
            "Identify revenue dependencies on high-risk jurisdictions.\n\n"
            "CRITICAL ANTI-DOUBLE-COUNTING RULE: Ignore standard foreign currency (FX) translation risks (those belong to Market Risk). Focus STRICTLY on geopolitical stability, sanctions, and physical presence risks.\n\n"
            "1. Does the company have significant revenue or operations in high-risk geographies (e.g. China, Russia, Iran, Venezuela)?\n"
            "2. What percentage of revenue is from high-risk geographies?\n"
            "3. Are sanctions or export control risks explicitly mentioned?\n"
            "Return JSON: {\"high_risk_geography\": bool, \"geography_name\": \"<name of geography>\", \"revenue_pct\": 0.0, \"sanctions_risk\": bool, \"severity\": \"CRITICAL/HIGH/MEDIUM/LOW\"}"
        )
        
        def scorer(res, chunks):
            pts = 3
            sev = "LOW"
            evt_text = "No material geographic concentration."
            if isinstance(res, dict):
                sanctions = res.get("sanctions_risk", False)
                pct = res.get("revenue_pct") or 0.0
                geo = res.get("geography_name", "")
                csev = res.get("severity", "LOW").upper()
                
                if sanctions or (pct > 30 and "China" in geo) or csev == "CRITICAL":
                    pts = adjust_points(20, self.tier); sev = "CRITICAL"; evt_text = f"Sanctions risk OR operations in OFAC countries / >30% China: {geo}"
                elif pct > 30 or csev == "HIGH":
                    pts = adjust_points(14, self.tier); sev = "HIGH"; evt_text = f">30% revenue from geopolitically elevated-risk geography: {geo} ({pct}%)"
                elif pct >= 10 or csev == "MEDIUM":
                    pts = adjust_points(8, self.tier); sev = "MEDIUM"; evt_text = f"10-30% from elevated-risk geography: {geo} ({pct}%)"
                    
            self._add_evidence("GEOGRAPHIC_CONCENTRATION", "RAG_EXTRACT", evt_text, sev, pts, "ChromaDB, Item 1A/7/7A", len(chunks))
            
        self._run_rag_sub_dimension("GEOGRAPHIC_CONCENTRATION", queries, ["item_1a", "item_7", "item_7a"], instr, scorer)

    def step18_score_aggregation(self):
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
                
        top_finding_text = top_finding_evt["evidence_text"] if top_finding_evt else "No material operational risks found."

        data_completeness = "FULL" if self.chunks_retrieved_any else "PARTIAL"
            
        self.processor.risk_scorecard["OPERATIONAL"] = {
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
            "t": self.ticker, "d": "OPERATIONAL", "rs": final_score, "rl": risk_level,
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
        
        msg = f"Operational Risk evaluated: Score {final_score}/100 ({risk_level}). Analyzed Supply Chain, Customer Concentration, Cybersecurity & IT. Found {len(self.evidence_list)} risk signals. Data Completeness: {data_completeness}."
        self.processor.log_audit("MODULE_3_OPERATIONAL_RISK", "COMPLETED", msg)

    def run(self):
        self.processor.log_audit("MODULE_3_OPERATIONAL_RISK", "STARTED", "Beginning Operational Risk evaluation (Supply Chain, IT, Concentration).")
        self.step13_key_person()
        self.step14_supply_chain()
        self.step15_tech_cyber()
        self.step16_customer_concentration()
        self.step17_geographic_concentration()
        self.step18_score_aggregation()
