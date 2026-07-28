"""
Module:  paths.py
Agent:   Shared (all agents)
Purpose: Single source of truth for every file path in the DeligenX project.
         All agents import path constants from here — no hardcoded strings elsewhere.
Inputs:  ticker (str), run_id (str)
Outputs: Dict of pathlib.Path objects scoped to a specific run.
"""

from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Project root — derived from this file's location: config/paths.py → ../
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Top-level directories (not run-scoped)
# ---------------------------------------------------------------------------
OUTPUT_DIR: Path = PROJECT_ROOT / "output"
LOGS_DIR: Path = PROJECT_ROOT / "logs"

# Cross-run, 7-day TTL cache for ticker resolution and submission history
TICKER_CACHE_DIR: Path = PROJECT_ROOT / "data" / "cache" / "ticker_lookups"

def generate_run_id(ticker: str) -> str:
    """Generate a canonical run ID: '{TICKER}_{YYYYMMDD_HHMMSS}' in local time."""
    normalized_ticker = ticker.upper().strip()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{normalized_ticker}_{timestamp}"


def get_run_paths(ticker: str, run_id: str) -> dict[str, Path]:
    """Return a dict of all run-scoped paths for the given run.

    Every file any agent reads or writes during a run is named here.
    New paths should be added to this function — never hardcoded in agent code.

    Args:
        ticker: The company ticker (used only for documentation/context here;
                the run_id already encodes it).
        run_id: The canonical run ID from generate_run_id().

    Returns:
        Dict mapping UPPER_SNAKE_CASE key names to pathlib.Path objects.
    """
    run_dir = OUTPUT_DIR / run_id

    return {
        # Root for this run
        "RUN_DIR": run_dir,

        # Shared paths
        "TICKER_CACHE_DIR": TICKER_CACHE_DIR,

        # SQLite database — shared by all agents
        "SQLITE_DB_PATH": run_dir / "deligenx.db",

        # ChromaDB persistent directory — Agent 1 writes, Agents 3/4 read
        "CHROMADB_DIR_PATH": run_dir / "chromadb",

        # Audit log — shared JSONL timeline across all agents
        "AUDIT_LOG_PATH": LOGS_DIR / f"audit_{run_id}.jsonl",

        # Agent 1 → downstream
        "INGESTION_SUMMARY_PATH": run_dir / "ingestion_summary.json",

        # Agent 2 → downstream
        "RATIO_DB_PATH": run_dir / "analysis" / "ratio_database.json",
        "TREND_ANALYSIS_PATH": run_dir / "analysis" / "trend_analysis.json",
        "FRAUD_DISTRESS_PATH": run_dir / "analysis" / "fraud_distress_scores.json",
        "ANOMALY_FLAGS_PATH": run_dir / "analysis" / "anomaly_flags.json",
        "SECTOR_BENCH_JSON": run_dir / "analysis" / "sector_benchmark.json",
        "QOE_SUMMARY_PATH": run_dir / "analysis" / "qoe_summary.json",
        "ANALYSIS_SUMMARY_PATH": run_dir / "analysis_summary.json",

        # Agent 3 → downstream
        "MI_SUMMARY_PATH": run_dir / "market_intel_summary.json",

        # Agent 4 → downstream
        "RISK_SCORECARD_PATH": run_dir / "risk_assessment_summary.json",

        # Agent 5 final output directory
        "MEMO_OUTPUT_DIR": run_dir / "memo",
        "MEMO_HTML_PATH": run_dir / "memo" / f"{run_id}_investment_memo.html",
        "MEMO_JSON_CERT_PATH": run_dir / "memo" / f"{run_id}_data_integrity_certificate.json",
    }



def ensure_run_dirs(run_paths: dict[str, Path]) -> None:
    """Create all directories referenced in run_paths (idempotent).

    Iterates the run_paths dict and creates directories for:
    - Keys ending in '_DIR' or '_DIR_PATH' → create the path itself.
    - All other keys → create the parent directory so the file can be written.

    Args:
        run_paths: The dict returned by get_run_paths().
    """
    for key, path in run_paths.items():
        if key.endswith("_DIR") or key.endswith("_DIR_PATH"):
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
