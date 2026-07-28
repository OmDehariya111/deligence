"""
Module:  data_collector.py
Agent:   Memo Generation Agent
Purpose: Central data loader — reads ALL outputs from all 4 upstream agents.
         Loads JSON summary files, SQLite tables, and ChromaDB chunks.
         Produces a single unified data dictionary consumed by all section writers.
Inputs:  Run paths dict from config/paths.py.
Outputs: Dict containing every piece of data from Ingestion, Analysis, MI, and Risk agents.
"""

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text

from tools.sqlite_tools import DatabaseManager

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> dict | list | None:
    """Safely load a JSON file, returning None on failure.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON data (dict or list), or None if file not found or invalid.
    """
    try:
        if not path.exists():
            logger.warning(f"JSON file not found: {path}")
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load JSON from {path}: {e}")
        return None


def _query_table(db: DatabaseManager, query: str, params: dict | None = None) -> list[dict]:
    """Execute a SQL query and return results as list of dicts.

    Args:
        db: DatabaseManager instance.
        query: SQL query string.
        params: Optional bind parameters.

    Returns:
        List of dicts, one per row. Empty list on error.
    """
    try:
        with db.get_connection() as conn:
            result = conn.execute(text(query), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
    except Exception as e:
        logger.error(f"SQL query failed: {e}. Query: {query[:100]}...")
        return []


def _load_chromadb_chunks(chromadb_dir: Path, ticker: str,
                          section_code: str, max_chunks: int = 15) -> str:
    """Load ChromaDB chunks for a specific section.

    Args:
        chromadb_dir: Path to the ChromaDB persistent directory.
        ticker: Company ticker for filtering.
        section_code: Section code to query (e.g., 'item_1', 'item_7').
        max_chunks: Maximum number of chunks to retrieve.

    Returns:
        Concatenated text from matching chunks, or empty string.
    """
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(chromadb_dir))
        collections = client.list_collections()
        if not collections:
            logger.warning("No ChromaDB collections found")
            return ""

        # Find the filings collection
        collection = None
        for col in collections:
            if "filings" in col.name:
                collection = client.get_collection(col.name)
                break

        if collection is None:
            logger.warning("No 'filings' collection found in ChromaDB")
            return ""

        # Query for the specified section
        results = collection.get(
            where={
                "$and": [
                    {"ticker": ticker.upper()},
                    {"section_code": section_code},
                ]
            },
            limit=max_chunks,
        )

        if results and results.get("documents"):
            chunks = results["documents"]
            logger.info(f"Retrieved {len(chunks)} ChromaDB chunks for {section_code}")
            return "\n\n---\n\n".join(chunks)

        return ""

    except Exception as e:
        logger.error(f"ChromaDB query failed for {section_code}: {e}")
        return ""


def collect_all_data(paths: dict[str, Path], ticker: str) -> dict[str, Any]:
    """Load ALL data from all 4 upstream agents into a single unified dictionary.

    This is the single entry point for data collection. Every section writer
    reads from this dictionary — no section writer directly accesses files or databases.

    Args:
        paths: Run paths dict from config/paths.py.
        ticker: Company ticker symbol.

    Returns:
        Dict with keys organized by source agent and data type.
    """
    data: dict[str, Any] = {
        "ticker": ticker.upper(),
        "run_id": paths["RUN_DIR"].name,
    }

    # ══════════════════════════════════════════════════════════════════
    # AGENT 1: INGESTION — JSON + SQLite + ChromaDB
    # ══════════════════════════════════════════════════════════════════
    logger.info("Loading Ingestion Agent data...")

    # 1A. Ingestion Summary JSON
    ingestion_summary = _load_json(paths["INGESTION_SUMMARY_PATH"])
    data["ingestion_summary"] = ingestion_summary or {}

    if ingestion_summary:
        # Extract company identity
        ci = ingestion_summary.get("company_identity", {})
        data["company_name"] = ci.get("company_name", "N/A")
        data["cik"] = ci.get("cik", "N/A")
        data["sic_code"] = ci.get("sic_code", "N/A")
        data["industry_name"] = ci.get("industry_name", "N/A")
        data["exchange"] = ci.get("exchange", "N/A")
        data["state_of_incorp"] = ci.get("state_of_incorp", "N/A")
        data["fiscal_year_end"] = ci.get("fiscal_year_end", "N/A")
        data["fiscal_year_end_month"] = ci.get("fiscal_year_end_month", None)

        # Field coverage
        fcs = ingestion_summary.get("field_coverage_summary", {})
        data["total_fields"] = fcs.get("total_fields", 0)
        data["fields_with_data"] = fcs.get("fields_with_data", 0)
        data["fields_missing"] = fcs.get("fields_missing", 0)
        data["fields_computed"] = fcs.get("fields_computed", 0)

        # Vector DB stats
        data["vector_db_stats"] = ingestion_summary.get("vector_database_stats", {})

        # Financial data coverage
        data["financial_data_coverage"] = ingestion_summary.get("financial_data_coverage", {})

        # Field metadata (source provenance)
        data["field_metadata"] = ingestion_summary.get("field_metadata", {})

        # Missing critical fields
        data["missing_critical_fields"] = ingestion_summary.get("missing_critical_fields", [])

        # Warnings and errors
        data["ingestion_warnings"] = ingestion_summary.get("warnings", [])
        data["ingestion_errors"] = ingestion_summary.get("errors", [])

        # Duration
        data["ingestion_duration"] = ingestion_summary.get("ingestion_duration_seconds", 0)

        # Module status
        data["ingestion_module_status"] = ingestion_summary.get("module_status", {})

    # 1B. SQLite: financial_data (5 years × 44 fields)
    db = DatabaseManager(paths["SQLITE_DB_PATH"])
    data["financial_data"] = _query_table(
        db, "SELECT * FROM financial_data WHERE ticker = :ticker ORDER BY fiscal_year",
        {"ticker": ticker.upper()}
    )
    logger.info(f"Loaded {len(data['financial_data'])} rows from financial_data")

    # 1C. SQLite: market_profile (beta)
    data["market_profile"] = _query_table(
        db, "SELECT * FROM market_profile WHERE ticker = :ticker",
        {"ticker": ticker.upper()}
    )

    # 1D. ChromaDB: Business description (Item 1) and MD&A (Item 7)
    chromadb_dir = paths["CHROMADB_DIR_PATH"]
    if chromadb_dir.exists():
        data["chromadb_item_1"] = _load_chromadb_chunks(chromadb_dir, ticker, "item_1")
        data["chromadb_item_7"] = _load_chromadb_chunks(chromadb_dir, ticker, "item_7")
        logger.info("ChromaDB chunks loaded for Item 1 and Item 7")
    else:
        data["chromadb_item_1"] = ""
        data["chromadb_item_7"] = ""
        logger.warning("ChromaDB directory not found")

    # ══════════════════════════════════════════════════════════════════
    # AGENT 2: ANALYSIS — 6 JSON files + SQLite
    # ══════════════════════════════════════════════════════════════════
    logger.info("Loading Analysis Agent data...")

    # 2A. Ratio Database (ALL 166 RatioRecords)
    data["ratio_database"] = _load_json(paths["RATIO_DB_PATH"]) or []
    logger.info(f"Loaded {len(data['ratio_database'])} ratio records")

    # 2B. Trend Analysis (ALL RatioTrend objects)
    data["trend_analysis"] = _load_json(paths["TREND_ANALYSIS_PATH"]) or []
    logger.info(f"Loaded {len(data['trend_analysis'])} trend records")

    # 2C. Fraud & Distress Scores (Beneish + Altman)
    data["fraud_distress"] = _load_json(paths["FRAUD_DISTRESS_PATH"]) or {}
    logger.info("Loaded fraud/distress scores")

    # 2D. Anomaly Flags (15 rules evaluated)
    data["anomaly_flags"] = _load_json(paths["ANOMALY_FLAGS_PATH"]) or {}
    logger.info("Loaded anomaly flags")

    # 2E. Sector Benchmark (12 metrics + 20 peers)
    data["sector_benchmark"] = _load_json(paths["SECTOR_BENCH_JSON"]) or {}
    logger.info("Loaded sector benchmark")

    # 2F. QoE Summary (Master output)
    data["qoe_summary"] = _load_json(paths["QOE_SUMMARY_PATH"]) or {}
    logger.info("Loaded QoE summary")

    # 2G. SQLite: financial_ratios (166 rows)
    data["financial_ratios_db"] = _query_table(
        db, "SELECT * FROM financial_ratios WHERE ticker = :ticker ORDER BY fiscal_year, ratio_name",
        {"ticker": ticker.upper()}
    )
    logger.info(f"Loaded {len(data['financial_ratios_db'])} rows from financial_ratios")

    # ══════════════════════════════════════════════════════════════════
    # AGENT 3: MARKET INTELLIGENCE — JSON + 8 SQLite tables
    # ══════════════════════════════════════════════════════════════════
    logger.info("Loading Market Intelligence Agent data...")

    # 3A. Market Intelligence Summary JSON (Master output)
    data["market_intel_summary"] = _load_json(paths["MI_SUMMARY_PATH"]) or {}
    logger.info("Loaded market intelligence summary")

    # 3B. SQLite: named_competitors
    data["named_competitors"] = _query_table(db, "SELECT * FROM named_competitors")
    logger.info(f"Loaded {len(data['named_competitors'])} named competitors")

    # 3C. SQLite: competitor_ltm_financials
    data["competitor_ltm_financials"] = _query_table(db, "SELECT * FROM competitor_ltm_financials")
    logger.info(f"Loaded {len(data['competitor_ltm_financials'])} LTM financial rows")

    # 3D. SQLite: competitor_market_data
    data["competitor_market_data"] = _query_table(db, "SELECT * FROM competitor_market_data")
    logger.info(f"Loaded {len(data['competitor_market_data'])} market data rows")

    # 3E. SQLite: trading_comps_table (7 rows: peers + target + sector median/mean)
    data["trading_comps_table"] = _query_table(db, "SELECT * FROM trading_comps_table")
    logger.info(f"Loaded {len(data['trading_comps_table'])} trading comps rows")

    # 3F. SQLite: implied_valuation (3 methods)
    data["implied_valuation"] = _query_table(db, "SELECT * FROM implied_valuation")
    logger.info(f"Loaded {len(data['implied_valuation'])} implied valuation rows")

    # 3G. SQLite: news_sentiment (ALL articles)
    data["news_sentiment"] = _query_table(db, "SELECT * FROM news_sentiment ORDER BY published_date DESC")
    logger.info(f"Loaded {len(data['news_sentiment'])} news sentiment rows")

    # 3H. SQLite: industry_macro
    data["industry_macro"] = _query_table(db, "SELECT * FROM industry_macro")
    logger.info(f"Loaded {len(data['industry_macro'])} industry/macro rows")

    # 3I. SQLite: market_risk_signals
    data["market_risk_signals"] = _query_table(db, "SELECT * FROM market_risk_signals")
    logger.info(f"Loaded {len(data['market_risk_signals'])} market risk signals")

    # ══════════════════════════════════════════════════════════════════
    # AGENT 4: RISK ASSESSMENT — JSON + 5 SQLite tables
    # ══════════════════════════════════════════════════════════════════
    logger.info("Loading Risk Assessment Agent data...")

    # 4A. Risk Assessment Summary JSON (Master output)
    data["risk_assessment_summary"] = _load_json(paths["RISK_SCORECARD_PATH"]) or {}
    logger.info("Loaded risk assessment summary")

    # 4B. SQLite: risk_dimensions (6 rows)
    data["risk_dimensions"] = _query_table(db, "SELECT * FROM risk_dimensions")
    logger.info(f"Loaded {len(data['risk_dimensions'])} risk dimensions")

    # 4C. SQLite: risk_evidence (30+ findings)
    data["risk_evidence"] = _query_table(db, "SELECT * FROM risk_evidence")
    logger.info(f"Loaded {len(data['risk_evidence'])} risk evidence items")

    # 4D. SQLite: deal_breaker_flags (8 conditions)
    data["deal_breaker_flags"] = _query_table(db, "SELECT * FROM deal_breaker_flags")
    logger.info(f"Loaded {len(data['deal_breaker_flags'])} deal breaker flags")

    # 4E. SQLite: risk_mitigation_recommendations
    data["risk_mitigation_recommendations"] = _query_table(
        db, "SELECT * FROM risk_mitigation_recommendations"
    )
    logger.info(f"Loaded {len(data['risk_mitigation_recommendations'])} mitigation recommendations")

    # 4F. SQLite: composite_risk_output
    data["composite_risk_output"] = _query_table(db, "SELECT * FROM composite_risk_output")
    logger.info(f"Loaded {len(data['composite_risk_output'])} composite risk rows")

    # ══════════════════════════════════════════════════════════════════
    # DATA LOADING COMPLETE — Summary
    # ══════════════════════════════════════════════════════════════════
    total_sql_rows = (
        len(data["financial_data"]) + len(data["market_profile"]) +
        len(data["financial_ratios_db"]) + len(data["named_competitors"]) +
        len(data["competitor_ltm_financials"]) + len(data["competitor_market_data"]) +
        len(data["trading_comps_table"]) + len(data["implied_valuation"]) +
        len(data["news_sentiment"]) + len(data["industry_macro"]) +
        len(data["market_risk_signals"]) + len(data["risk_dimensions"]) +
        len(data["risk_evidence"]) + len(data["deal_breaker_flags"]) +
        len(data["risk_mitigation_recommendations"]) + len(data["composite_risk_output"])
    )
    total_json_files = sum(1 for k in ["ingestion_summary", "ratio_database", "trend_analysis",
                                        "fraud_distress", "anomaly_flags", "sector_benchmark",
                                        "qoe_summary", "market_intel_summary",
                                        "risk_assessment_summary"]
                           if data.get(k))

    logger.info(
        f"DATA COLLECTION COMPLETE — {total_json_files}/9 JSON files loaded, "
        f"{total_sql_rows} total SQLite rows across 16 tables, "
        f"ChromaDB chunks loaded for Item 1 and Item 7"
    )

    data["_collection_summary"] = {
        "json_files_loaded": total_json_files,
        "total_sql_rows": total_sql_rows,
        "chromadb_loaded": bool(data.get("chromadb_item_1")),
    }

    return data
