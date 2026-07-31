"""
Module:  pre_processing.py
Agent:   Risk Assessment Agent
Purpose: Validates inputs from upstream agents and sets up context for risk scoring.
         Normalizes all upstream data structures into the canonical format expected
         by every downstream scoring module.
Inputs:  upstream summary JSONs and SQLite database
Outputs: in-memory state for scoring, audit logs, and potential fast-fail summary
"""

import json
from datetime import datetime, timezone
import chromadb
from pathlib import Path
from typing import Any

from config.paths import get_run_paths
from tools.sqlite_tools import DatabaseManager
from sqlalchemy import text
from agents.risk_assessment.risk_tier import classify_tier


class RiskPreProcessor:
    """
    # Ye class Risk Assessment Agent ka pehla kadam hai (Pre-Processing).
    # Kyun Banai?: Ye ensure karti hai ki pichle saare agents (Ingestion, Analysis, Market Intel)
    # ne apna data sahi se diya hai. Ye alag-alag JSON files ko ek canonical (standard) format 
    # me normalize karti hai taaki aage ke scoring modules bina error ke chal sakein.
    # Inputs: JSON summary files aur SQLite database.
    # Outputs: Normalized memory state jo aage ke modules use karenge (Jaise ratios, trends, etc.)
    """
    def __init__(self, ticker: str, run_id: str):
        self.ticker = ticker.upper().strip()
        self.run_id = run_id
        self.paths = get_run_paths(self.ticker, self.run_id)

        # State Flags
        self.market_intel_available = False
        self.news_sentiment_available = False
        self.moat_width = "UNKNOWN"
        self.chromadb_available = False
        self.chromadb_collection_name = None   # BUG 5 fix: dynamic collection name

        # Company Size Tier (used for materiality-adjusted scoring)
        self.company_tier: str = "MID"         # Default; updated in run_setup()
        self.company_revenue: float | None = None
        self.company_market_cap: float | None = None

        # Data Containers
        self.ingestion_summary: dict[str, Any] = {}
        self.analysis_summary: dict[str, Any] = {}
        self.market_intel_summary: dict[str, Any] = {}
        self.company_name: str = "Unknown"     # BUG 10 fix

        self.fiscal_year_end_date: str = ""
        self.most_recent_fiscal_year: int = 0
        self.market_risk_signals: list[dict[str, Any]] = []
        self.news_sentiment: list[dict[str, Any]] = []

        self.scoring_rulebook: dict[str, Any] = {}
        self.risk_scorecard: dict[str, Any] = {}
        self.llm_usage_stats: dict[str, int] = {
            "TIER_1_EXTRACTION": 0,
            "TIER_2_REASONING": 0
        }

    def log_audit(self, module: str, status: str, summary: str):
        """
        # Centralized logger wrapped around utils.audit_logger
        # Ab ye manual file write karne ke bajaye, standard log_audit_event function ko use karega,
        # jisse time tracking automatic ho jayegi.
        """
        import logging
        from utils.audit_logger import log_audit_event
        
        # Fallback/Filter: Naya audit_logger sirf STARTED, COMPLETED, aur FAILED accept karta hai.
        # Risk Agent ki purani "INFO", "WARNING", "LLM_CALL" entries ko hum standard python logger 
        # se terminal/app log me bhejenge taaki JSONL audit log crash na ho aur clean rahe.
        if status not in {"STARTED", "COMPLETED", "FAILED"}:
            logger = logging.getLogger(__name__)
            logger.info(f"[{module}] {status}: {summary}")
            return
            
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="Risk Assessment Agent",
            module=module,
            status=status,
            summary=summary
        )

    def read_json_safe(self, path: Path) -> dict[str, Any] | list:
        """Safely read a JSON file, returning empty dict if missing."""
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def write_error_summary(self, reason: str):
        """Write an ERROR status to the output scorecard and log it."""
        out_path = self.paths["RISK_SCORECARD_PATH"]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": "ERROR",
            "reason": reason,
            "run_id": self.run_id
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        self.log_audit("PRE_PROCESSING", "FAILED", reason)

    # -------------------------------------------------------------------------
    # BUG 1 FIX: Normalize ratio_database.json (flat list → structured dict)
    # -------------------------------------------------------------------------
    def _normalize_ratios(self, ratios_raw: list) -> dict[str, Any]:
        """
        # Ye function Analysis Agent se aayi hui flat ratio list ko ek structured dictionary me badalta hai.
        # Kyun zaroori hai?: Taaki aage ke modules easily 'most_recent_year' ka data bina loop chalaye nikal sakein.
        # Structure: {"most_recent_year": {...}, "historical": {...}}
        """
        if not ratios_raw or not isinstance(ratios_raw, list):
            return {"most_recent_year": {}, "historical": {}}

        # Find most recent fiscal year
        most_recent_fy = max(r.get("fiscal_year", 0) for r in ratios_raw)
        self.most_recent_fiscal_year = most_recent_fy

        most_recent = {}
        historical = {}

        for r in ratios_raw:
            name = r.get("ratio_name", "")
            fy = r.get("fiscal_year", 0)
            fy_str = str(fy)

            entry = {
                "value": r.get("value"),
                "status": r.get("status", "MISSING"),
                "unit": r.get("unit"),
                "formula": r.get("formula"),
                "fiscal_year": fy
            }

            names_to_add = [name]
            if name == "net_debt_to_ebitda":
                names_to_add.append("net_debt_ebitda")
            elif name == "fcf_to_net_income":
                names_to_add.append("cash_conversion")

            for n in names_to_add:
                if fy == most_recent_fy:
                    most_recent[n] = entry

                if fy_str not in historical:
                    historical[fy_str] = {}
                historical[fy_str][n] = entry

        return {"most_recent_year": most_recent, "historical": historical}

    # -------------------------------------------------------------------------
    # BUG 2 FIX: Normalize trend_analysis.json (flat list → dict)
    # -------------------------------------------------------------------------
    def _normalize_trends(self, trends_raw: list) -> dict[str, Any]:
        """
        # Ye function Analysis Agent ki flat "trend" list ko structured dictionary me badalta hai.
        # Isse fada ye hai ki Module 1 ko pichle 4 saal ka CAGR aur baaki trend data easily mil jata hai.
        Convert flat list into canonical structure:
        {
          "status": "COMPLETE",  (or "SKIPPED")
          "trends": {ratio_name: {"trend_direction": ..., "year_values": ...}},
          "revenue_cagr_4yr": {"status": "COMPUTED", "value": X},
          "net_income_cagr_4yr": {"status": "COMPUTED", "value": X}
        }
        """
        if not trends_raw:
            return {"status": "SKIPPED", "trends": {}}

        if isinstance(trends_raw, dict) and trends_raw.get("status") == "SKIPPED":
            return trends_raw

        if not isinstance(trends_raw, list):
            return {"status": "SKIPPED", "trends": {}}

        trends_dict = {}
        revenue_cagr = {"status": "NOT_COMPUTABLE"}
        net_income_cagr = {"status": "NOT_COMPUTABLE"}

        for t in trends_raw:
            name = t.get("ratio_name", "")
            if not name:
                continue
            entry = {
                "trend_direction": t.get("trend_direction", "STABLE"),
                "trend_confidence": t.get("trend_confidence", "LOW"),
                "momentum": t.get("momentum", "NONE"),
                "sudden_changes": t.get("sudden_changes", []),
                "year_values": t.get("year_values", {}),
                "linear_slope": t.get("linear_slope"),
                "average_value": t.get("average_value"),
                "std_deviation": t.get("std_deviation")
            }
            names_to_add = [name]
            if name == "net_debt_to_ebitda":
                names_to_add.append("net_debt_ebitda")
            elif name == "fcf_to_net_income":
                names_to_add.append("cash_conversion")

            for n in names_to_add:
                trends_dict[n] = entry
            # BUG 2 sub-fix: extract CAGR fields (4yr not 3yr)
            if name == "revenue_cagr_4yr":
                val = t.get("average_value")  # use value from year_values most recent
                year_vals = t.get("year_values", {})
                if year_vals:
                    val = list(year_vals.values())[-1]
                revenue_cagr = {"status": "COMPUTED", "value": val}
            elif name == "net_income_cagr_4yr":
                year_vals = t.get("year_values", {})
                val = list(year_vals.values())[-1] if year_vals else None
                net_income_cagr = {"status": "COMPUTED", "value": val}

        return {
            "status": "COMPLETE",
            "trends": trends_dict,
            # BUG 2 sub-fix: expose as canonical names (module1 uses these)
            "revenue_cagr_3yr": revenue_cagr,    # aliased from 4yr
            "revenue_cagr_4yr": revenue_cagr,
            "net_income_cagr_3yr": net_income_cagr,
            "net_income_cagr_4yr": net_income_cagr,
        }

    # -------------------------------------------------------------------------
    # BUG 3 FIX: Normalize fraud_distress_scores.json
    # -------------------------------------------------------------------------
    def _normalize_fraud_distress(self, fd_raw: dict) -> dict[str, Any]:
        """
        # Ye Altman Z (Bankruptcy) aur Beneish M (Fraud) ke raw scores ko clean karke unka "most recent year" nikalta hai.
        Convert to canonical structure expected by downstream modules.

        Output structure includes persistence metrics for the deal breaker module:
          beneish_m_score.likely_count = how many year-pairs triggered LIKELY_MANIPULATOR
          beneish_m_score.all_scores   = full history for multi-year analysis
          beneish_m_score.note         = may contain HYPERGROWTH FALSE-POSITIVE WARNING
        """
        if not fd_raw or not isinstance(fd_raw, dict):
            return {"beneish_m_score": {}, "altman_z_score": {}}

        # Beneish: take most recent pair (last in list) + compute persistence metrics
        beneish_result = {}
        beneish_scores = fd_raw.get("beneish_scores", [])
        if beneish_scores:
            latest_b = beneish_scores[-1]  # most recent year pair
            likely_count = sum(1 for s in beneish_scores if s.get("verdict") == "LIKELY_MANIPULATOR")
            grey_count = sum(1 for s in beneish_scores if s.get("verdict") == "GREY_ZONE")
            total_computed = sum(1 for s in beneish_scores if s.get("verdict") not in ["NOT_COMPUTABLE"])
            beneish_result = {
                "verdict": latest_b.get("verdict", "NOT_COMPUTABLE"),
                "m_score": latest_b.get("m_score"),
                "individual_flags": latest_b.get("individual_flags", []),
                "fiscal_year_pair": latest_b.get("fiscal_year_pair"),
                "note": latest_b.get("note", ""),
                "all_scores": beneish_scores,
                "likely_count": likely_count,
                "grey_count": grey_count,
                "total_computed": total_computed,
            }

        # Altman: take most recent fiscal year
        altman_result = {}
        altman_scores = fd_raw.get("altman_scores", [])
        if altman_scores:
            latest_a = max(altman_scores, key=lambda x: x.get("fiscal_year", 0))
            altman_result = {
                "most_recent_year": {
                    "verdict": latest_a.get("verdict", "NOT_APPLICABLE"),
                    "z_score": latest_a.get("z_score"),
                    "fiscal_year": latest_a.get("fiscal_year"),
                    "version": latest_a.get("version")
                },
                "all_years": altman_scores
            }

        return {
            "beneish_m_score": beneish_result,
            "altman_z_score": altman_result
        }

    # -------------------------------------------------------------------------
    # BUG 4 FIX: Normalize anomaly_flags.json
    # -------------------------------------------------------------------------
    def _normalize_anomalies(self, anoms_raw: dict) -> dict[str, Any]:
        """
        Normalize anomaly_flags.json to canonical structure.
        Actual key is 'flags', module expects 'triggered_flags'.
        """
        if not anoms_raw or not isinstance(anoms_raw, dict):
            return {"triggered_flags": [], "rules_skipped_missing_data": []}

        return {
            "triggered_flags": anoms_raw.get("flags", []),
            "rules_skipped_missing_data": anoms_raw.get("rules_skipped_missing_data", []),
            "total_flags": anoms_raw.get("total_flags", 0),
            "critical": anoms_raw.get("critical", 0),
            "high": anoms_raw.get("high", 0),
            "medium": anoms_raw.get("medium", 0),
            "low": anoms_raw.get("low", 0),
        }

    # -------------------------------------------------------------------------
    # BUG 8 FIX: Derive fiscal_year_end_date from ingestion_summary
    # -------------------------------------------------------------------------
    def _derive_fiscal_year_end_date(self) -> str:
        """
        # Ye financial quarter end date nikalta hai (Jaise March 31, ya June 30).
        Derive the most recent fiscal year end date string.
        ingestion_summary.company_identity.fiscal_year_end = "0630" (MMDD format)
        most_recent_fiscal_year = 2025
        → "2025-06-30"
        """
        try:
            fy_end_code = self.ingestion_summary.get("company_identity", {}).get("fiscal_year_end", "")
            if not fy_end_code or len(fy_end_code) != 4:
                # fallback to December
                return f"{self.most_recent_fiscal_year}-12-31"

            month = int(fy_end_code[:2])
            day = int(fy_end_code[2:])
            return f"{self.most_recent_fiscal_year}-{month:02d}-{day:02d}"
        except Exception:
            return f"{self.most_recent_fiscal_year}-12-31"

    # -------------------------------------------------------------------------
    # BUG 5 FIX: Dynamic ChromaDB collection name discovery
    # -------------------------------------------------------------------------
    def _get_chromadb_collection_name(self, client) -> str | None:
        """
        # ChromaDB (Database) me alag-alag companies ka data hota hai. Ye sahi collection naam find karta hai.
        Discover the actual ChromaDB collection name.
        Ingestion Agent creates run-scoped names like: 'msft-20260710-165005-filings'
        """
        try:
            colls = client.list_collections()
            if not colls:
                return None
            # If there's exactly one collection, use it
            if len(colls) == 1:
                return colls[0].name
            # Otherwise look for one matching the run_id pattern
            run_id_lower = self.run_id.lower().replace("_", "-")
            for c in colls:
                if run_id_lower in c.name or "filings" in c.name:
                    return c.name
            # Last resort: return first
            return colls[0].name
        except Exception:
            return None

    def process(self) -> bool:
        """
        # Module ko execute karne ka main function. Ye Step 0C se Step 8 tak saare kaam karta hai.
        # Agar koi upstream agent fail hua hota hai, toh ye yahin par process rok deta hai aur False return karta hai.
        """
        # Step 0C: Check Ingestion Agent status
        self.ingestion_summary = self.read_json_safe(self.paths["INGESTION_SUMMARY_PATH"])
        if not self.ingestion_summary or self.ingestion_summary.get("status") == "ERROR":
            reason = "Upstream Ingestion Agent failed: " + self.ingestion_summary.get("reason", "Unknown or missing")
            self.write_error_summary(reason)
            return False

        # BUG 10 FIX: Extract company_name from ingestion_summary
        self.company_name = (
            self.ingestion_summary.get("company_identity", {}).get("company_name", "Unknown")
        )

        # Step 0D: Check Analysis Agent status
        qoe_summary = self.read_json_safe(self.paths["QOE_SUMMARY_PATH"])
        if not qoe_summary or qoe_summary.get("status") == "ERROR":
            reason = "Upstream Analysis Agent failed: " + qoe_summary.get("reason", "Unknown or missing")
            self.write_error_summary(reason)
            return False

        # Step 0E: Check Market Intelligence Agent status
        self.market_intel_summary = self.read_json_safe(self.paths["MI_SUMMARY_PATH"])
        if not self.market_intel_summary or self.market_intel_summary.get("status") == "ERROR":
            self.market_intel_available = False
            self.news_sentiment_available = False
            self.moat_width = "UNKNOWN"
            self.log_audit("PRE_PROCESSING", "WARNING",
                           "Market Intelligence Agent output unavailable. Degrading gracefully.")
        else:
            self.market_intel_available = True

            # BUG 9 FIX: Correct moat_width extraction
            self.moat_width = (
                self.market_intel_summary
                .get("COMPETITIVE_MOAT", {})
                .get("moat_width", "UNKNOWN")
            )

            # BUG 6 FIX: Use correct column name 'ticker' not 'company_ticker'
            db = DatabaseManager(self.paths["SQLITE_DB_PATH"])
            try:
                row = db.execute(
                    text("SELECT COUNT(*) FROM news_sentiment WHERE ticker = :ticker"),
                    {"ticker": self.ticker}
                ).fetchone()
                self.news_sentiment_available = bool(row and row[0] > 0)
            except Exception:
                self.news_sentiment_available = False
            finally:
                db.dispose()

        # Step 0F: Audit Log STARTED
        summary = (
            f"Ingestion and Analysis status validated. "
            f"Market Intel: {'AVAILABLE' if self.market_intel_available else 'UNAVAILABLE'}, "
            f"news_sentiment: {'AVAILABLE' if self.news_sentiment_available else 'UNAVAILABLE'}, "
            f"moat_width: {self.moat_width}. Beginning setup."
        )
        self.log_audit("PRE_PROCESSING", "STARTED", summary)

        # Step 1: Load and normalize all Analysis Agent outputs
        # BUG 1 FIX: Normalize ratios (flat list → structured dict)
        ratios_raw = self.read_json_safe(self.paths["RATIO_DB_PATH"])
        if isinstance(ratios_raw, list):
            normalized_ratios = self._normalize_ratios(ratios_raw)
        else:
            normalized_ratios = {"most_recent_year": {}, "historical": {}}

        # BUG 2 FIX: Normalize trends (flat list → structured dict)
        trends_raw = self.read_json_safe(self.paths["TREND_ANALYSIS_PATH"])
        if isinstance(trends_raw, list):
            normalized_trends = self._normalize_trends(trends_raw)
        else:
            normalized_trends = self._normalize_trends(trends_raw if isinstance(trends_raw, list) else [])

        # BUG 3 FIX: Normalize fraud_distress
        fd_raw = self.read_json_safe(self.paths["FRAUD_DISTRESS_PATH"])
        normalized_fd = self._normalize_fraud_distress(fd_raw)

        # BUG 4 FIX: Normalize anomaly_flags
        anoms_raw = self.read_json_safe(self.paths["ANOMALY_FLAGS_PATH"])
        normalized_anoms = self._normalize_anomalies(anoms_raw)

        self.analysis_summary = {
            "ratios": normalized_ratios,
            "trends": normalized_trends,
            "fraud_distress": normalized_fd,
            "anomalies": normalized_anoms,
            "qoe": qoe_summary
        }

        # BUG 8 FIX: Derive fiscal_year_end_date from ingestion_summary
        self.fiscal_year_end_date = self._derive_fiscal_year_end_date()

        # Step 3 & 4: Load Market Intel tables
        db = DatabaseManager(self.paths["SQLITE_DB_PATH"])
        try:
            if self.market_intel_available:
                # BUG 7 FIX: market_risk_signals has no company_ticker column
                # It's a global table for this run — fetch all rows
                try:
                    self.market_risk_signals = [
                        dict(r._mapping) for r in db.execute(
                            text("SELECT * FROM market_risk_signals")
                        ).fetchall()
                    ]
                except Exception:
                    self.market_risk_signals = []

                if self.news_sentiment_available:
                    # BUG 6 FIX: Use 'ticker' column not 'company_ticker'
                    try:
                        self.news_sentiment = [
                            dict(r._mapping) for r in db.execute(
                                text("SELECT * FROM news_sentiment WHERE ticker = :ticker AND crisis_flag = 1"),
                                {"ticker": self.ticker}
                            ).fetchall()
                        ]
                    except Exception:
                        self.news_sentiment = []
        finally:
            db.dispose()

        # Step 6: Confirm ChromaDB is reachable + BUG 5 FIX: discover collection name
        try:
            if self.paths["CHROMADB_DIR_PATH"].exists():
                client = chromadb.PersistentClient(path=str(self.paths["CHROMADB_DIR_PATH"]))
                self.chromadb_collection_name = self._get_chromadb_collection_name(client)
                self.chromadb_available = self.chromadb_collection_name is not None
            else:
                self.chromadb_available = False
        except Exception:
            self.chromadb_available = False

        if self.chromadb_available:
            self.log_audit("PRE_PROCESSING", "INFO",
                           f"ChromaDB reachable. Collection: '{self.chromadb_collection_name}'")
        else:
            self.log_audit("PRE_PROCESSING", "WARNING",
                           "ChromaDB unavailable or no collections found.")

        # Step 7: Load SCORING_RULEBOOK
        rulebook_path = Path("config/risk_scoring_config.json").resolve()
        self.scoring_rulebook = self.read_json_safe(rulebook_path)

        # Step 7b: Detect company size tier for materiality-adjusted scoring
        try:
            fin_db = DatabaseManager(self.paths["SQLITE_DB_PATH"])
            row = fin_db.execute(
                text("SELECT revenue, market_cap FROM financial_data "
                     "WHERE ticker = :t ORDER BY fiscal_year DESC LIMIT 1"),
                {"t": self.ticker}
            ).fetchone()
            fin_db.dispose()
            if row:
                self.company_revenue     = row[0]
                self.company_market_cap  = row[1]
            self.company_tier = classify_tier(self.company_market_cap, self.company_revenue)
            self.log_audit("PRE_PROCESSING", "INFO",
                           f"Company tier: {self.company_tier} "
                           f"(revenue={self.company_revenue}, market_cap={self.company_market_cap})")
        except Exception as e:
            self.company_tier = "MID"
            self.log_audit("PRE_PROCESSING", "WARNING",
                           f"Tier detection failed ({e}); defaulting to MID.")

        # Step 8: Initialize RISK_SCORECARD
        dimensions = ["FINANCIAL", "MARKET", "OPERATIONAL", "LEGAL", "MANAGEMENT", "ESG"]
        for dim in dimensions:
            self.risk_scorecard[dim] = {
                "raw_score": 0,
                "risk_evidence_list": [],
                "data_completeness": "FULL"
            }

        self.log_audit("PRE_PROCESSING", "COMPLETED", "Pre-processing setup complete.")
        return True
