"""
Module:  module8_mi_summary.py
Agent:   Market Intelligence Agent
Purpose: Compile the final Market Intelligence JSON summary.
Inputs:  MarketIntelContext, all SQLite tables, existing MI_SUMMARY_PATH
Outputs: Writes finalized JSON to `MI_SUMMARY_PATH`.
"""

import json
import logging
import os
from datetime import datetime, timezone
import litellm

from sqlalchemy import text

from config.paths import get_run_paths
from schemas.pydantic_models import MarketIntelContext
from tools.sqlite_tools import DatabaseManager
from utils.audit_logger import log_audit_event

logger = logging.getLogger(__name__)

class MarketIntelligenceSummarizer:
    """
    # Ye class final "Executive Report" (JSON) banati hai jisme pichle saare modules ka nichod (summary) hota hai.
    # Ye wahi file hai jo finally frontend dashboard par user ko dikhai jayegi.
    """
    def __init__(self, context: MarketIntelContext):
        self.context = context
        self.paths = get_run_paths(context.ticker, context.run_id)
        self.db_manager = DatabaseManager(self.paths["SQLITE_DB_PATH"])

    def _check_table_exists_and_has_data(self, conn, table_name: str) -> bool:
        """
        # Ek chota sa check ki kya database ki table me data majood hai ya nahi.
        """
        try:
            res = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            return res > 0
        except Exception:
            return False

    def run(self) -> None:
        """
        # Module ko execute karne ka main function.
        """
        # --- BUG 2 FIXED (Standard Logging) ---
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_8_FINAL_SUMMARY",
            status="STARTED",
            summary="Compiling Final Market Intelligence Summary."
        )

        with self.db_manager.get_connection() as conn:
            # Step 1: Check Modules Status
            # Saare modules ke status (FAILED/COMPLETED) ko audit log se uthata hai 
            # taaki user ko pata chale ki konsa module nahi chala.
            modules_status = {
                "module_1_named_competitors": "FAILED",
                "module_2_ltm_financials": "FAILED",
                "module_3_live_market_data": "FAILED",
                "module_4_comps_and_valuation": "FAILED",
                "module_5_news_sentiment": "FAILED",
                "module_6_industry_macro": "FAILED",
                "module_7_market_risk_signals": "FAILED",
            }
            audit_path = self.paths["AUDIT_LOG_PATH"]
            if audit_path.exists():
                try:
                    with open(audit_path, "r", encoding="utf-8") as f:
                        for line in f:
                            entry = json.loads(line)
                            mod = entry.get("module")
                            status = entry.get("status")
                            if mod == "MODULE_1_NAMED_COMPETITORS":
                                modules_status["module_1_named_competitors"] = status
                            elif mod == "MODULE_2_LTM_FINANCIALS":
                                modules_status["module_2_ltm_financials"] = status
                            elif mod == "MODULE_3_LIVE_MARKET_DATA":
                                modules_status["module_3_live_market_data"] = status
                            elif mod == "MODULE_4_COMPS_AND_VALUATION":
                                modules_status["module_4_comps_and_valuation"] = status
                            elif mod == "MODULE_5_NEWS_SENTIMENT":
                                modules_status["module_5_news_sentiment"] = status
                            elif mod == "MODULE_6_INDUSTRY_MACRO":
                                modules_status["module_6_industry_macro"] = status
                            elif mod == "MODULE_7_MARKET_RISK_SIGNALS":
                                modules_status["module_7_market_risk_signals"] = status
                except Exception as e:
                    logger.warning(f"Error parsing audit log for statuses: {e}")

            try:
                comp_count = conn.execute(text("SELECT COUNT(*) FROM named_competitors WHERE ticker != :t"), {"t": self.context.ticker}).scalar()
                modules_status["competitor_count"] = comp_count
            except: pass

            # Step 2: Build the Main JSON Structure
            master_json = {
                "ticker": self.context.ticker,
                "company_name": self.context.company_name,
                "analysis_timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "modules_status": modules_status,
                "NAMED_COMPETITORS": [],
                "COMPS_TABLE_REFERENCE": "See trading_comps_table in SQLite for full structured table"
            }

            # Step 3: Competitors ki summary
            try:
                comps = conn.execute(text("""
                    SELECT n.ticker, n.company_name, n.why_selected, 
                           m.market_cap, t.ebitda_margin, t.ev_ebitda,
                           m.ytd_return_pct, m.analyst_consensus_rating, m.analyst_price_target
                    FROM named_competitors n
                    LEFT JOIN competitor_market_data m ON n.ticker = m.ticker
                    LEFT JOIN trading_comps_table t ON n.ticker = t.ticker
                    WHERE n.ticker != :t
                """), {"t": self.context.ticker}).fetchall()
                
                for c in comps:
                    master_json["NAMED_COMPETITORS"].append({
                        "ticker": c[0],
                        "company_name": c[1],
                        "why_selected": c[2],
                        "market_cap_bn": round(c[3] / 1e9, 2) if c[3] else None,
                        "ltm_ebitda_margin_pct": c[4],
                        "ev_ebitda_ltm": c[5],
                        "ytd_return_pct": c[6],
                        "analyst_consensus": c[7],
                        "analyst_price_target_usd": c[8]
                    })
            except Exception as e: logger.warning(f"Error building competitors json: {e}")

            # Step 4: Implied Valuation (Target company ka fair price kya hona chahiye)
            master_json["IMPLIED_VALUATION"] = {}
            try:
                val_rows = conn.execute(text("SELECT method, peer_25p_multiple, peer_median_mult, peer_75p_multiple, target_metric, implied_ev_low, implied_ev_base, implied_ev_high, implied_eq_low, implied_eq_base, implied_eq_high, implied_ps_low, implied_ps_base, implied_ps_high, vs_current_price FROM implied_valuation")).fetchall()
                for r in val_rows:
                    master_json["IMPLIED_VALUATION"][r[0]] = {
                        "peer_25p_multiple": r[1],
                        "peer_median_multiple": r[2],
                        "peer_75p_multiple": r[3],
                        "target_metric": r[4],
                        "implied_ev_low": r[5],
                        "implied_ev_base": r[6],
                        "implied_ev_high": r[7],
                        "implied_eq_low": r[8],
                        "implied_eq_base": r[9],
                        "implied_eq_high": r[10],
                        "implied_ps_low": r[11],
                        "implied_ps_base": r[12],
                        "implied_ps_high": r[13],
                        "upside_downside_pct": r[14]
                    }
            except Exception as e:
                logger.warning(f"Error reading implied valuation table: {e}")

            # Purana JSON read karke usme se Moat aur Sentiment nikalna
            summary_path = self.paths["MI_SUMMARY_PATH"]
            ctx_data = {}
            if summary_path.exists():
                # --- BUG 3 FIXED (UTF-8 Encoding safety) ---
                with open(summary_path, "r", encoding="utf-8") as f:
                    try: ctx_data = json.load(f)
                    except: pass
            
            # Step 5: News Sentiment aur Crisis flags
            try:
                crisis_flags = conn.execute(text("SELECT headline, crisis_type, retrieval_source FROM news_sentiment WHERE ticker = :t AND crisis_flag = 1"), {"t": self.context.ticker}).fetchall()
                master_json["NEWS_SENTIMENT"] = {
                    "sentiment_trend": ctx_data.get("sentiment_trend", "UNKNOWN"),
                    "crisis_flags": [{"headline": c[0], "crisis_type": c[1]} for c in crisis_flags],
                    "llm_narrative": ctx_data.get("sentiment_narrative", "")
                }
            except: pass

            # Step 6: Competitive Moat (Moat_width aur uska reason)
            master_json["COMPETITIVE_MOAT"] = {
                "moat_width": ctx_data.get("moat_width", "UNKNOWN"),
                "moat_narrative": ctx_data.get("moat_narrative", "")
            }

            # Step 7: Macro Headwinds
            try:
                macro_res = conn.execute(text("SELECT indicator_name, current_value, trend_direction, relevance_note FROM industry_macro WHERE ticker = :t"), {"t": self.context.ticker}).fetchall()
                master_json["INDUSTRY_MACRO"] = {
                    "key_factors": [{"factor": m[0], "current_value": m[1], "trend": m[2], "relevance": m[3]} for m in macro_res if m[0] != "Competitive Moat Assessment"]
                }
            except: pass

            # Step 8: Market Risk Score (Kitne khatre hain)
            try:
                risk_res = conn.execute(text("SELECT risk_level, points_contribution FROM market_risk_signals")).fetchall()
                high = sum(1 for r in risk_res if r[0] == "HIGH")
                med = sum(1 for r in risk_res if r[0] == "MEDIUM")
                low = sum(1 for r in risk_res if r[0] == "LOW")
                pts = sum(r[1] for r in risk_res)
                master_json["MARKET_RISK_SIGNALS_COUNT"] = {
                    "high_severity": high,
                    "medium_severity": med,
                    "low_severity": low,
                    "total_points": pts,
                    "summary": "See market_risk_signals table for full details"
                }
            except: pass

            # -------------------------------------------------------------------------
            # Step 9: LLM Final Verdict (The "No. 1" Executive Summary)
            # LLM ko saara JSON data bhej kar us se ek final report likhwana
            # -------------------------------------------------------------------------
            prompt = (
                f"Act as a Chief Investment Officer (CIO) writing the Executive Summary for an Equity Research Report. "
                f"Analyze the following comprehensive market intelligence data for {self.context.company_name} ({self.context.ticker}). "
                "Generate a structured assessment of the company's Overall Competitive Position. "
                "Weigh High-Severity Risk Signals and Crisis Flags heavily. If valuation implies massive downside and risks are high, lean towards BELOW AVERAGE. "
                "Return EXACTLY AND ONLY valid JSON matching this schema:\n"
                "{\n"
                '  "verdict": "ABOVE AVERAGE | AVERAGE | BELOW AVERAGE",\n'
                '  "basis": "Short paragraph explaining the verdict",\n'
                '  "key_advantages": ["bullet 1", "bullet 2"],\n'
                '  "key_vulnerabilities": ["bullet 1", "bullet 2"]\n'
                "}\n\n"
                f"Data:\n{json.dumps(master_json, indent=2)}"
            )

            # --- BUG 1 FIXED (LLM Hardcoding Hata Di Gayi) ---
            # Ab Vertex AI (Gemini) use hoga, aur 'response_format' hata diya hai kyunki 
            # Vertex AI me prompt se hi JSON aayega safely.
            model_name = os.environ.get("LLM_MODEL_NAME_TIER1", "vertex_ai/gemini-2.5-flash")

            try:
                response = litellm.completion(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                # Clean LLM response (in case it wraps with ```json)
                llm_out = response.choices[0].message.content.strip()
                if llm_out.startswith("```json"):
                    llm_out = llm_out[7:]
                if llm_out.endswith("```"):
                    llm_out = llm_out[:-3]
                    
                master_json["OVERALL_COMPETITIVE_POSITION"] = json.loads(llm_out.strip())
            except Exception as e:
                logger.warning(f"Failed to parse LLM final verdict: {e}")
                master_json["OVERALL_COMPETITIVE_POSITION"] = {"verdict": "UNKNOWN", "basis": f"LLM Error: {str(e)}", "key_advantages": [], "key_vulnerabilities": []}

            # Final JSON ko wapas save karna
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(master_json, f, indent=2, ensure_ascii=False)

        self.db_manager.dispose()
        
        # Transparent Completed Log
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_8_FINAL_SUMMARY",
            status="COMPLETED",
            summary=f"Final Market Intelligence summary compiled for {self.context.ticker}."
        )
