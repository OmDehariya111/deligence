"""
Module:  module7_market_risk.py
Agent:   Market Intelligence Agent
Purpose: Compile findings into a structured market risk signals package.
Inputs:  MarketIntelContext, SQLite tables (comps, market_data, news_sentiment, industry_macro), MI_SUMMARY_PATH
Outputs: Writes to `market_risk_signals` SQLite table.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, MetaData, String, Table, text

from config.paths import get_run_paths
from schemas.pydantic_models import MarketIntelContext
from tools.sqlite_tools import DatabaseManager
from utils.audit_logger import log_audit_event

logger = logging.getLogger(__name__)

def get_market_risk_signals_table(metadata: MetaData) -> Table:
    """
    # SQLite Database Table: Yahan company ke saare 'Red Flags' (Khatre ke nishaan) 
    # aur unke risk points save honge. 
    """
    return Table(
        "market_risk_signals",
        metadata,
        Column("signal_id", Integer, primary_key=True, autoincrement=True),
        Column("signal_category", String),
        Column("signal_name", String),
        Column("signal_value", String),
        Column("risk_level", String),
        Column("points_contribution", Integer),
        Column("evidence_text", String),
        extend_existing=True,
    )

class MarketRiskSignalGenerator:
    """
    # Ye module 1 se leke 6 tak ki saari reports padhta hai aur ek final "Risk Scorecard" 
    # banata hai, bilkul ek Chief Risk Officer (CRO) ki tarah.
    """
    def __init__(self, context: MarketIntelContext):
        self.context = context
        self.paths = get_run_paths(context.ticker, context.run_id)
        self.db_manager = DatabaseManager(self.paths["SQLITE_DB_PATH"])
        self.db_manager.create_tables([get_market_risk_signals_table(self.db_manager.metadata)])
        self.signals = []

    def _add_signal(self, cat: str, name: str, val: str, level: str, points: int, evidence: str):
        """
        # Ek naya risk signal add karne ka helper function.
        """
        self.signals.append({
            "signal_category": cat,
            "signal_name": name,
            "signal_value": val,
            "risk_level": level,
            "points_contribution": points,
            "evidence_text": evidence
        })

    def run(self) -> None:
        """
        # Module ko execute karne ka main function.
        """
        
        # --- LOGGING STANDARD UPDATED ---
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_7_MARKET_RISK_SIGNALS",
            status="STARTED",
            summary="Compiling Market Risk Signals."
        )

        # JSON Context se Data padhna (Moat aur Sentiment)
        summary_path = self.paths["MI_SUMMARY_PATH"]
        ctx_data = {}
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                try: ctx_data = json.load(f)
                except: pass

        # -------------------------------------------------------------------------
        # 1. Competitive Moat Risk (Structural Business Risk) - High Weight (15 pts)
        # -------------------------------------------------------------------------
        moat_width = ctx_data.get("moat_width", "UNKNOWN")
        moat_narrative = ctx_data.get("moat_narrative", "")
        if moat_width == "NARROW":
            self._add_signal(
                "COMPETITIVE", "Narrow Competitive Moat",
                "NARROW", "HIGH", 15,
                moat_narrative
            )
        elif moat_width == "MODERATE":
            self._add_signal(
                "COMPETITIVE", "Moderate Competitive Moat",
                "MODERATE", "LOW", 8,
                moat_narrative
            )

        # -------------------------------------------------------------------------
        # 2. Sentiment Risk - Medium Weight (10 pts)
        # -------------------------------------------------------------------------
        sentiment_trend = ctx_data.get("sentiment_trend", "UNKNOWN")
        if sentiment_trend == "DETERIORATING":
            self._add_signal(
                "SENTIMENT", "Deteriorating News Sentiment", 
                "DETERIORATING", "MEDIUM", 10, 
                "News sentiment for the target company has consistently worsened over the past 90 days."
            )

        with self.db_manager.get_connection() as conn:
            # -------------------------------------------------------------------------
            # 3. Crisis News Risk - Highest Weight (Up to 25 pts)
            # -------------------------------------------------------------------------
            # Agar news me koi Fraud ya SEC Investigation jaisi baat hai toh risk maximum hoga.
            try:
                crisis_res = conn.execute(text("SELECT crisis_type, headline FROM news_sentiment WHERE ticker = :t AND crisis_flag = 1"), {"t": self.context.ticker}).fetchall()
                crisis_pts = 0
                for r in crisis_res:
                    if crisis_pts < 25: # Cap at 25 points maximum (taaki ek hi news se 100 point na ho jayein)
                        pts = min(10, 25 - crisis_pts)
                        crisis_pts += pts
                        self._add_signal(
                            "SENTIMENT", f"Crisis News Detected: {r[0]}",
                            "CRISIS_FLAG=1", "HIGH", pts,
                            f"Crisis keyword triggered on headline: '{r[1]}'"
                        )
            except Exception as e: pass

            # -------------------------------------------------------------------------
            # 4. Market & Operational Risk (Analysts, Shorts, Earnings)
            # -------------------------------------------------------------------------
            try:
                mkt_res = conn.execute(text("SELECT analyst_consensus_rating, short_interest_pct, earn_surp_q1_pct, earn_surp_q2_pct, earn_surp_q3_pct, earn_surp_q4_pct FROM competitor_market_data WHERE ticker = :t"), {"t": self.context.ticker}).fetchone()
                if mkt_res:
                    cols = ["analyst_consensus_rating", "short_interest_pct", "earn_surp_q1_pct", "earn_surp_q2_pct", "earn_surp_q3_pct", "earn_surp_q4_pct"]
                    mdata = dict(zip(cols, mkt_res))
                    
                    # Analyst Rating > 3.5 means "Underperform" or "Sell"
                    if mdata.get("analyst_consensus_rating") and mdata["analyst_consensus_rating"] > 3.5:
                        self._add_signal("MARKET", "Analyst Bearish Consensus", f"Rating: {mdata['analyst_consensus_rating']}", "HIGH", 10, "Average analyst recommends Underperform or Sell.")

                    # Agar 15% se zyada investors company ke girne par paisa laga rahe hain (Shorting)
                    if mdata.get("short_interest_pct") and mdata["short_interest_pct"] > 15:
                        self._add_signal("MARKET", "High Short Interest", f"{mdata['short_interest_pct']}%", "MEDIUM", 8, "Institutional money betting heavily against the stock.")
                    
                    # Agar pichle 4 quarters me se 3 baar company profit expectation meet nahi kar payi (Earnings Miss)
                    eh = [mdata.get("earn_surp_q1_pct"), mdata.get("earn_surp_q2_pct"), mdata.get("earn_surp_q3_pct"), mdata.get("earn_surp_q4_pct")]
                    misses = [h for h in eh if h is not None and h < 0]
                    if len(misses) >= 3:
                        self._add_signal("OPERATIONAL", "Consistent Earnings Misses", f"{len(misses)} misses in last 4 quarters", "MEDIUM", 10, "Target has failed to meet expectations repeatedly.")
                    
                    # Agar koi ek quarter me 15% se zyada bada nuksan ho gaya
                    sig_miss = [h for h in misses if h <= -15]
                    if sig_miss:
                        self._add_signal("OPERATIONAL", "Significant Earnings Miss", f"Missed by {sig_miss[0]}%", "HIGH", 12, "At least one recent quarter missed earnings expectations severely.")
            except Exception: pass

            # -------------------------------------------------------------------------
            # 5. Valuation Risk (Comparing with Competitors/Sector)
            # -------------------------------------------------------------------------
            try:
                target_comp = conn.execute(text("SELECT revenue_growth_pct, ebitda_margin, ev_ebitda FROM trading_comps_table WHERE ticker = :t"), {"t": self.context.ticker}).fetchone()
                median_comp = conn.execute(text("SELECT revenue_growth_pct, ebitda_margin, ev_ebitda FROM trading_comps_table WHERE ticker = 'SECTOR_MEDIAN'")).fetchone()
                
                if target_comp and median_comp:
                    tc = dict(zip(["revenue_growth_pct", "ebitda_margin", "ev_ebitda"], target_comp))
                    mc = dict(zip(["revenue_growth_pct", "ebitda_margin", "ev_ebitda"], median_comp))
                    
                    # Growth industry average se kam hai
                    if tc.get("revenue_growth_pct") is not None and mc.get("revenue_growth_pct") is not None and tc["revenue_growth_pct"] < mc["revenue_growth_pct"]:
                        self._add_signal("OPERATIONAL", "Below Sector Median Growth", f"Target: {tc['revenue_growth_pct']:.2f}%, Median: {mc['revenue_growth_pct']:.2f}%", "MEDIUM", 8, "Target is growing slower than peers.")
                        
                    # Margin (Profitability) industry average se kam hai
                    if tc.get("ebitda_margin") is not None and mc.get("ebitda_margin") is not None and tc["ebitda_margin"] < mc["ebitda_margin"]:
                        self._add_signal("OPERATIONAL", "Below Sector Median Margin", f"Target: {tc['ebitda_margin']:.2f}%, Median: {mc['ebitda_margin']:.2f}%", "MEDIUM", 8, "Target is less profitable than peers.")
                        
                    # Valuation Premium: Agar EV/EBITDA sector ke mukable dedh guna (1.5x) zyada sasti ya mehengi hai (Overvalued)
                    if tc.get("ev_ebitda") is not None and mc.get("ev_ebitda") is not None and mc["ev_ebitda"] > 0 and tc["ev_ebitda"] > (mc["ev_ebitda"] * 1.5):
                        self._add_signal("VALUATION", "Significant Valuation Premium", f"Target: {tc['ev_ebitda']:.2f}x, Median: {mc['ev_ebitda']:.2f}x", "MEDIUM", 8, "Overvalued vs peers — downside risk if growth slows.")
            except Exception: pass

            # -------------------------------------------------------------------------
            # 6. Macro Headwinds (Economy ka bura asar)
            # -------------------------------------------------------------------------
            try:
                macro_res = conn.execute(text("SELECT indicator_name, trend_direction, relevance_note FROM industry_macro WHERE ticker = :t AND trend_direction != 'STABLE'"), {"t": self.context.ticker}).fetchall()
                macro_pts = 0
                for r in macro_res:
                    # simple logic: Agar Interest Rate, Inflation, Unemployment badh rahe hain ya Consumer spend gir raha hai toh wo khatra (Headwind) hai
                    name = r[0]
                    trend = r[1]
                    is_headwind = False
                    if "Yield" in name and trend == "UP": is_headwind = True
                    elif "Unemployment" in name and trend == "UP": is_headwind = True
                    elif "CPI" in name and trend == "UP": is_headwind = True
                    elif "PPI" in name and trend == "UP": is_headwind = True
                    elif "Confidence" in name and trend == "DOWN": is_headwind = True
                    elif "Retail" in name and trend == "DOWN": is_headwind = True
                    elif "Production" in name and trend == "DOWN": is_headwind = True
                    elif "Consumption" in name and trend == "DOWN": is_headwind = True
                    elif "Spreads" in name and trend == "UP": is_headwind = True
                    
                    if is_headwind and macro_pts < 12: # Max 12 points macro risk
                        pts = min(4, 12 - macro_pts)
                        macro_pts += pts
                        self._add_signal("MACRO", f"Macro Headwind: {name}", trend, "LOW", pts, r[2])
            except Exception: pass

        # Saare points ikatthe karke Database me save karna
        if self.signals:
            insert_sql = """
                INSERT INTO market_risk_signals 
                (signal_category, signal_name, signal_value, risk_level, points_contribution, evidence_text)
                VALUES 
                (:signal_category, :signal_name, :signal_value, :risk_level, :points_contribution, :evidence_text)
            """
            with self.db_manager.get_connection() as conn:
                try:
                    conn.execute(text("DELETE FROM market_risk_signals"))
                except Exception as e:
                    logger.warning(f"Failed to clear market_risk_signals: {e}")
                for s in self.signals:
                    conn.execute(text(insert_sql), s)

        self.db_manager.dispose()
        
        # Transparent Completed Log
        total_pts = sum(s["points_contribution"] for s in self.signals)
        status = "COMPLETED"
        summary = f"Generated {len(self.signals)} risk signals totaling {total_pts} points."
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MODULE_7_MARKET_RISK_SIGNALS",
            status=status,
            summary=summary
        )
        logger.info(summary)
