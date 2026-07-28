"""
Module:  module6_industry_macro.py
Agent:   Market Intelligence Agent
Purpose: Fetch macro indicators (FRED) based on SIC, and assess competitive moat via RAG.
Inputs:  MarketIntelContext.
Outputs: Writes to `industry_macro` SQLite table and updates `MI_SUMMARY_PATH`.
"""

import json
import logging
import os
from datetime import datetime, timezone
import chromadb
import litellm

from sqlalchemy import Column, Float, MetaData, String, Table, text

from config.paths import get_run_paths
from utils.mcp_client import call_mcp_tool_sync
from schemas.pydantic_models import MarketIntelContext
from tools.sqlite_tools import DatabaseManager
from utils.audit_logger import log_audit_event

logger = logging.getLogger(__name__)

def get_industry_macro_table(metadata: MetaData) -> Table:
    """
    # SQLite Database Table: Yahan company se related saare Macro indicators 
    # (Jaise Inflation, Interest Rates) aur AI ki di gayi Moat rating save hogi.
    """
    return Table(
        "industry_macro",
        metadata,
        Column("ticker", String, primary_key=True),
        Column("indicator_name", String, primary_key=True),
        Column("current_value", Float, nullable=True),
        Column("value_1y_ago", Float, nullable=True),
        Column("value_3y_ago", Float, nullable=True),
        Column("trend_direction", String),
        Column("relevance_note", String),
        Column("moat_width", String, nullable=True),
        Column("moat_narrative", String, nullable=True),
        extend_existing=True,
    )

class IndustryMacroExtractor:
    """
    # Ye class Economy (Macro) ka data FRED se laati hai aur 
    # Target company ki takat (Moat) ko RAG (Vector DB) se analyse karti hai.
    """
    def __init__(self, context: MarketIntelContext):
        self.context = context
        self.paths = get_run_paths(context.ticker, context.run_id)
        self.db_manager = DatabaseManager(self.paths["SQLITE_DB_PATH"])
        self.db_manager.create_tables([get_industry_macro_table(self.db_manager.metadata)])

    def _get_indicators_for_sic(self):
        """
        # Ye bahut smart function hai jo Company ke SIC code (Industry) ke hisab se 
        # chun-chun kar wahi indicators laata hai jo us company ke liye sach me matter karte hain.
        """
        try:
            sic = int(self.context.sic_code)
        except ValueError:
            sic = 0
            
        # 2000-3999: Manufacturing Industry
        if 2000 <= sic <= 3999:
            return [
                ("INDPRO", "Industrial Production Index", "A key proxy for manufacturing volume."),
                ("MANEMP", "Manufacturing Employment", "A proxy for PMI and manufacturing sector health."),
                ("PPIACO", "Producer Price Index", "Measures average changes in selling prices received by domestic producers.")
            ]
        # 4000-4999: Transportation & Utilities
        elif 4000 <= sic <= 4999:
            return [
                ("DGS10", "10Y Treasury Yield", "Affects capital cost for infrastructure and utility debt financing."),
                ("MHHNGSP", "Natural Gas Price", "Key input cost for utilities and transport.")
            ]
        # 5000-5999: Wholesale & Retail Trade
        elif 5000 <= sic <= 5999:
            return [
                ("UMCSENT", "Consumer Confidence", "Strongly correlates with discretionary retail spending."),
                ("RSXFS", "Retail Sales", "Direct measure of top-line sector demand."),
                ("PCE", "Personal Consumption", "Broad measure of consumer spending health."),
                ("UNRATE", "Unemployment Rate", "Impacts consumer disposable income.")
            ]
        # 6000-6999: Finance, Insurance & Real Estate (Banks)
        elif 6000 <= sic <= 6999:
            return [
                ("FEDFUNDS", "Fed Funds Rate", "Directly impacts net interest margins for financials."),
                ("DGS10", "10Y Treasury Yield", "Dictates lending rates and fixed income portfolio values."),
                ("BAMLH0A0HYM2", "Credit Spreads", "Indicates overall credit risk and lending appetite in the market.")
            ]
        # 7000-7999: Services & Tech
        elif (7000 <= sic <= 7999) or sic == 7370:
            return [
                ("DGS10", "10Y Treasury Yield", "Higher yields discount future tech cash flows more heavily."),
                ("PCE", "Personal Consumption", "Important for consumer-facing tech services.")
            ]
        # 8000-8099: Healthcare
        elif 8000 <= sic <= 8099:
            return [
                ("PCU325412325412", "PPI Pharmaceuticals", "Tracks pricing power and inflation in the healthcare supply chain.")
            ]
        # Default Indicator
        else:
            return [
                ("DGS10", "10Y Treasury Yield", "Baseline cost of capital indicator."),
                ("CPIAUCSL", "CPI YoY", "General measure of inflation impact."),
                ("UNRATE", "Unemployment Rate", "Broad measure of economic health.")
            ]

    def _compute_trend(self, current, prior1, prior3):
        """
        # Indicator ka trend batata hai. Agar 2% se zyada change hua hai toh UP/DOWN bolta hai.
        """
        if current is None or prior1 is None: return "STABLE"
        # simple threshold: 2% move
        pct_change = (current - prior1) / abs(prior1) if prior1 != 0 else 0
        if pct_change > 0.02:
            return "UP"
        elif pct_change < -0.02:
            return "DOWN"
        return "STABLE"

    def _assess_moat(self):
        """
        # RAG (ChromaDB) + LLM ka use karke ye function Target company ki SEC file padhta hai
        # aur check karta hai ki company ke paas apne competition se bachne ka koi "Moat" (Kila/Taqat) hai ya nahi.
        """
        if not self.context.is_chromadb_reachable:
            return "UNKNOWN", "ChromaDB unavailable — moat assessment could not be performed."
            
        try:
            client = chromadb.PersistentClient(path=str(self.paths["CHROMADB_DIR_PATH"]))
            collection_name = f"{self.context.run_id.lower().replace('_', '-')}-filings"[:63]
            collection = client.get_collection(name=collection_name)
        except Exception as e:
            return "UNKNOWN", f"ChromaDB unavailable — {str(e)}"
            
        # Top 5 types ki Competitive Advantages (Moats) dhoondne ke liye powerful Vector Queries
        queries = [
            "switching cost deeply integrated mission-critical long-term contracts high retention lock-in",
            "network effect platform more users marketplace two-sided ecosystem developer community",
            "lower cost structure economies of scale cost leadership operational efficiency manufacturing scale",
            "brand recognition patents intellectual property regulatory approval fda approved proprietary technology",
            "regulated natural monopoly limited competition exclusive license infrastructure monopoly"
        ]
        
        all_chunks = []
        for q in queries:
            res = collection.query(
                query_texts=[q],
                n_results=3,
                where={"section_code": {"$in": ["item_1", "full_document"]}}
            )
            if res["documents"]:
                for doc in res["documents"][0]:
                    all_chunks.append(doc)
                    
        if not all_chunks:
            return "NARROW", "No discussion of competitive advantages found in Item 1."
            
        # LLM ko chunks bhej kar analyze karwana
        prompt = (
            "Act as an Elite Equity Research Analyst applying the classic Economic Moat framework. "
            "Analyze the following SEC 10-K excerpts. Identify if the company possesses a competitive moat. "
            "Consider the 5 pillars: Network Effects, Switching Costs, Intangible Assets, Cost Advantage, and Efficient Scale. "
            "You MUST output EXACTLY two lines and absolutely nothing else.\n"
            "Line 1: MOAT_WIDTH: [WIDE, MODERATE, or NARROW]\n"
            "Line 2: NARRATIVE: [3-4 sentences explaining the evidence]\n\n"
            "Excerpts:\n" + "\n".join(all_chunks[:10])
        )
        
        # --- BUG 2 FIXED (LLM Hardcoding Removed) ---
        # Ab Vertex AI (Gemini) use hoga properly.
        model_name = os.environ.get("LLM_MODEL_NAME_TIER1", "vertex_ai/gemini-2.5-flash")
        
        try:
            response = litellm.completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            llm_text = response.choices[0].message.content
            width = "UNKNOWN"
            narrative = "Failed to parse LLM response."
            
            for line in llm_text.split("\n"):
                if line.startswith("MOAT_WIDTH:"):
                    w = line.replace("MOAT_WIDTH:", "").strip().upper()
                    if "WIDE" in w: width = "WIDE"
                    elif "MODERATE" in w: width = "MODERATE"
                    elif "NARROW" in w: width = "NARROW"
                elif line.startswith("NARRATIVE:"):
                    narrative = line.replace("NARRATIVE:", "").strip()
                    
            return width, narrative
        except Exception as e:
            return "UNKNOWN", f"LLM error: {str(e)}"

    def run(self) -> None:
        """
        # Module ko execute karne ka main function.
        """
        
        # --- BUG 3 FIXED (Standard Logging) ---
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_6_INDUSTRY_MACRO",
            status="STARTED",
            summary="Beginning Industry and Macro Intelligence."
        )
        
        # Database table se purana data clean karna
        with self.db_manager.get_connection() as conn:
            try:
                conn.execute(text("DELETE FROM industry_macro WHERE ticker = :t"), {"t": self.context.ticker})
            except Exception as e:
                logger.warning(f"Failed to clear industry_macro: {e}")

        indicators = self._get_indicators_for_sic()
        macro_results = []
        
        for series_id, name, note in indicators:
            resp_raw = call_mcp_tool_sync("mcp_servers/fred_server.py", "get_fred_series", {"series_id": series_id, "limit": 37})
            try:
                resp = json.loads(resp_raw) if isinstance(resp_raw, str) else resp_raw
            except Exception:
                resp = {"status": "ERROR", "error_reason": "JSON parse error"}
                
            if resp.get("status") == "OK":
                obs = resp.get("observations", [])
                
                # --- BUG 1 FIXED (FRED Sorting Bug) ---
                # FRED API default me purana data (1950s) pehle bhejti hai.
                # Humne python me sorting laga di taaki index 0 par hamesha latest date (aaj ka) aaye.
                obs = sorted(obs, key=lambda x: x.get("date", ""), reverse=True)
                
                def parse_val(v):
                    try: return float(v)
                    except: return None
                    
                cur_val, val1y, val3y = None, None, None
                
                # Ab guaranteed index 0 current hai, 11th observation lagbhag 1 saal purani (monthly data ke hisab se),
                # aur 35th lagbhag 3 saal purani hogi.
                if len(obs) > 0: cur_val = parse_val(obs[0]["value"])
                if len(obs) > 11: val1y = parse_val(obs[11]["value"])
                if len(obs) > 35: val3y = parse_val(obs[35]["value"])
                
                macro_results.append({
                    "ticker": self.context.ticker,
                    "indicator_name": name,
                    "current_value": cur_val,
                    "value_1y_ago": val1y,
                    "value_3y_ago": val3y,
                    "trend_direction": self._compute_trend(cur_val, val1y, val3y),
                    "relevance_note": note,
                    "moat_width": None,
                    "moat_narrative": None
                })
            else:
                logger.warning(f"FRED query failed for {series_id}: {resp.get('error_reason')}")
                
        # Competitive Moat Assessment (Moat = Kila/Taqat)
        moat_width, moat_narrative = self._assess_moat()
        
        # Ek alag row sirf moat ke result ko save karne ke liye
        macro_results.append({
            "ticker": self.context.ticker,
            "indicator_name": "Competitive Moat Assessment",
            "current_value": None,
            "value_1y_ago": None,
            "value_3y_ago": None,
            "trend_direction": "N/A",
            "relevance_note": "ChromaDB RAG Assessment of Item 1",
            "moat_width": moat_width,
            "moat_narrative": moat_narrative
        })
        
        # SQLite me save karna
        if macro_results:
            insert_sql = """
                INSERT OR REPLACE INTO industry_macro 
                (ticker, indicator_name, current_value, value_1y_ago, value_3y_ago, 
                 trend_direction, relevance_note, moat_width, moat_narrative)
                VALUES 
                (:ticker, :indicator_name, :current_value, :value_1y_ago, :value_3y_ago, 
                 :trend_direction, :relevance_note, :moat_width, :moat_narrative)
            """
            with self.db_manager.get_connection() as conn:
                for r in macro_results:
                    conn.execute(text(insert_sql), r)
                    
        # JSON context update karna (jisse report me asani se print ho sake)
        summary_path = self.paths["MI_SUMMARY_PATH"]
        if summary_path.exists():
            # --- BUG 4 FIXED (UTF-8 Encoding on JSON read/write) ---
            with open(summary_path, "r", encoding="utf-8") as f:
                try: ctx_data = json.load(f)
                except: ctx_data = {}
        else:
            ctx_data = {}
            
        ctx_data["moat_width"] = moat_width
        ctx_data["moat_narrative"] = moat_narrative
        
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(ctx_data, f, indent=2, ensure_ascii=False)
            
        self.db_manager.dispose()
        
        # Transparent Logging
        status = "COMPLETED"
        summary = f"Industry Macro processed. Fetched {len(indicators)} indicators. Competitive Moat assessed as: {moat_width}."
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_6_INDUSTRY_MACRO",
            status=status,
            summary=summary
        )
        logger.info(summary)
