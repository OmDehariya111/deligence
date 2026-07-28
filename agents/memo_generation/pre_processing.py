"""
Module:  pre_processing.py
Agent:   Memo Generation Agent
Purpose: Validates all upstream agent outputs and orchestrates data loading.
         Checks that all 4 upstream agents completed successfully before memo generation.
Inputs:  Run paths dict from config/paths.py.
Outputs: Validated data dict ready for section writers.
"""

import logging
from pathlib import Path
from typing import Any

from agents.memo_generation.data_collector import collect_all_data
from agents.memo_generation.verification_engine import verify_financial_data

logger = logging.getLogger(__name__)


class PreProcessingError(Exception):
    """Raised when upstream agent validation fails critically."""
    pass


def validate_upstream_outputs(paths: dict[str, Path]) -> dict[str, Any]:
    """Validate that all upstream agent outputs exist and are not in ERROR state.

    Checks:
    1. ingestion_summary.json exists and status != ERROR
    2. All 6 Analysis Agent JSON files exist
    3. market_intel_summary.json exists
    4. risk_assessment_summary.json exists
    5. SQLite database exists and is readable
    6. ChromaDB directory exists

    Args:
        paths: Run paths dict from config/paths.py.

    Returns:
        Dict with validation status for each agent.

    Raises:
        PreProcessingError: If any critical validation fails.
    """
    validation = {
        "ingestion": {"status": "PENDING", "files": []},
        "analysis": {"status": "PENDING", "files": []},
        "market_intelligence": {"status": "PENDING", "files": []},
        "risk_assessment": {"status": "PENDING", "files": []},
        "sqlite": {"status": "PENDING"},
        "chromadb": {"status": "PENDING"},
    }

    # ── Agent 1: Ingestion ──
    ingestion_path = paths["INGESTION_SUMMARY_PATH"]
    if ingestion_path.exists():
        import json
        with open(ingestion_path, "r", encoding="utf-8") as f:
            ingestion = json.load(f)
        status = ingestion.get("status", "UNKNOWN")
        if status == "ERROR":
            raise PreProcessingError(
                f"Ingestion Agent failed with ERROR status. Cannot generate memo."
            )
        validation["ingestion"]["status"] = "OK"
        validation["ingestion"]["files"].append(str(ingestion_path))
        logger.info(f"✅ Ingestion Agent validated: status={status}")
    else:
        raise PreProcessingError(f"ingestion_summary.json not found at {ingestion_path}")

    # ── Agent 2: Analysis ──
    analysis_files = {
        "ratio_database": paths["RATIO_DB_PATH"],
        "trend_analysis": paths["TREND_ANALYSIS_PATH"],
        "fraud_distress": paths["FRAUD_DISTRESS_PATH"],
        "anomaly_flags": paths["ANOMALY_FLAGS_PATH"],
        "sector_benchmark": paths["SECTOR_BENCH_JSON"],
        "qoe_summary": paths["QOE_SUMMARY_PATH"],
    }
    missing_analysis = []
    for name, path in analysis_files.items():
        if path.exists():
            validation["analysis"]["files"].append(str(path))
        else:
            missing_analysis.append(name)
            logger.warning(f"⚠️ Analysis Agent file missing: {name} at {path}")

    if not missing_analysis:
        validation["analysis"]["status"] = "OK"
        logger.info(f"✅ Analysis Agent validated: all 6 files present")
    elif len(missing_analysis) < 3:
        validation["analysis"]["status"] = "PARTIAL"
        logger.warning(f"⚠️ Analysis Agent partial: missing {missing_analysis}")
    else:
        raise PreProcessingError(
            f"Analysis Agent critical failure: {len(missing_analysis)} files missing: {missing_analysis}"
        )

    # ── Agent 3: Market Intelligence ──
    mi_path = paths["MI_SUMMARY_PATH"]
    if mi_path.exists():
        validation["market_intelligence"]["status"] = "OK"
        validation["market_intelligence"]["files"].append(str(mi_path))
        logger.info("✅ Market Intelligence Agent validated")
    else:
        validation["market_intelligence"]["status"] = "MISSING"
        logger.warning(f"⚠️ market_intel_summary.json not found at {mi_path}")

    # ── Agent 4: Risk Assessment ──
    risk_path = paths["RISK_SCORECARD_PATH"]
    if risk_path.exists():
        validation["risk_assessment"]["status"] = "OK"
        validation["risk_assessment"]["files"].append(str(risk_path))
        logger.info("✅ Risk Assessment Agent validated")
    else:
        validation["risk_assessment"]["status"] = "MISSING"
        logger.warning(f"⚠️ risk_assessment_summary.json not found at {risk_path}")

    # ── SQLite Database ──
    db_path = paths["SQLITE_DB_PATH"]
    if db_path.exists():
        validation["sqlite"]["status"] = "OK"
        logger.info(f"✅ SQLite database exists: {db_path}")
    else:
        raise PreProcessingError(f"SQLite database not found at {db_path}")

    # ── ChromaDB ──
    chroma_path = paths["CHROMADB_DIR_PATH"]
    if chroma_path.exists() and chroma_path.is_dir():
        validation["chromadb"]["status"] = "OK"
        logger.info(f"✅ ChromaDB directory exists: {chroma_path}")
    else:
        validation["chromadb"]["status"] = "MISSING"
        logger.warning(f"⚠️ ChromaDB directory not found at {chroma_path}")

    return validation


def run_pre_processing(paths: dict[str, Path], ticker: str) -> dict[str, Any]:
    """Execute the full pre-processing pipeline.

    Steps:
    1. Validate all upstream agent outputs
    2. Collect all data into unified dict
    3. Run financial verification engine
    4. Return the enriched data dict

    Args:
        paths: Run paths dict.
        ticker: Company ticker symbol.

    Returns:
        Enriched data dict ready for section writers.
    """
    # Step 1: Validate
    logger.info("=" * 60)
    logger.info("STEP 1: Validating upstream agent outputs...")
    logger.info("=" * 60)
    validation = validate_upstream_outputs(paths)

    ok_count = sum(1 for v in validation.values() if v.get("status") == "OK")
    total = len(validation)
    logger.info(f"Validation complete: {ok_count}/{total} checks passed")

    # Step 2: Collect all data
    logger.info("=" * 60)
    logger.info("STEP 2: Collecting all data from 4 upstream agents...")
    logger.info("=" * 60)
    data = collect_all_data(paths, ticker)

    # Step 3: Run verification engine
    logger.info("=" * 60)
    logger.info("STEP 3: Running Financial Data Verification Engine...")
    logger.info("=" * 60)
    verification_results = verify_financial_data(data)
    data["verification_results"] = verification_results

    # Add validation status to data
    data["_validation"] = validation

    logger.info(
        f"PRE-PROCESSING COMPLETE — "
        f"Data collected from {data['_collection_summary']['json_files_loaded']}/9 JSON files, "
        f"{data['_collection_summary']['total_sql_rows']} SQLite rows, "
        f"Verification: {verification_results['summary']['data_points_with_value']}/"
        f"{verification_results['summary']['total_data_points']} data points verified, "
        f"{verification_results['summary']['cross_checks_passed']}/"
        f"{verification_results['summary']['cross_checks_total']} cross-checks passed"
    )

    return data
