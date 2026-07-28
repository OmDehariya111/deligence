"""
Module:  test_infra.py
Agent:   Shared (infrastructure)
Purpose: Verify the Phase 0 infrastructure: config/paths.py, tools/sqlite_tools.py,
         and utils/audit_logger.py all work correctly.
Inputs:  None (self-contained tests using tmp_path fixture).
Outputs: pytest results.
"""

import json
import re
import time
from pathlib import Path

import pytest

from config.paths import (
    PROJECT_ROOT,
    ensure_run_dirs,
    generate_run_id,
    get_run_paths,
)
from tools.sqlite_tools import DatabaseManager
from utils.audit_logger import audit_phase, log_audit_event

from sqlalchemy import Column, Integer, Table, Text, text


# ---------------------------------------------------------------------------
# config/paths.py tests
# ---------------------------------------------------------------------------


class TestGenerateRunId:
    """Tests for the generate_run_id function."""

    def test_run_id_format_matches_spec(self):
        """generate_run_id('AAPL') produces 'AAPL_YYYYMMDD_HHMMSS'."""
        run_id = generate_run_id("AAPL")
        assert re.match(r"^AAPL_\d{8}_\d{6}$", run_id), (
            f"run_id '{run_id}' does not match expected format AAPL_YYYYMMDD_HHMMSS"
        )

    def test_ticker_is_normalized_to_uppercase(self):
        """Lowercase ticker input is uppercased in the run_id."""
        run_id = generate_run_id("  aapl  ")
        assert run_id.startswith("AAPL_"), (
            f"Expected run_id to start with 'AAPL_', got '{run_id}'"
        )

    def test_two_calls_produce_different_ids_if_one_second_apart(self):
        """Sequential calls produce distinct run_ids (second-level granularity)."""
        id1 = generate_run_id("MSFT")
        time.sleep(1.1)
        id2 = generate_run_id("MSFT")
        assert id1 != id2, "Two run_ids generated >1s apart should differ"


class TestGetRunPaths:
    """Tests for the get_run_paths function."""

    def test_returns_all_expected_keys(self):
        """get_run_paths returns a dict with every documented path key."""
        run_id = "AAPL_20260101_120000"
        paths = get_run_paths("AAPL", run_id)

        expected_keys = {
            "RUN_DIR",
            "SQLITE_DB_PATH",
            "CHROMADB_DIR_PATH",
            "AUDIT_LOG_PATH",
            "INGESTION_SUMMARY_PATH",
            "RATIO_DB_PATH",
            "TREND_ANALYSIS_PATH",
            "FRAUD_DISTRESS_PATH",
            "ANOMALY_FLAGS_PATH",
            "SECTOR_BENCH_JSON",
            "QOE_SUMMARY_PATH",
            "ANALYSIS_SUMMARY_PATH",
            "MI_SUMMARY_PATH",
            "RISK_SCORECARD_PATH",
            "MEMO_OUTPUT_DIR",
            "FILING_CACHE_DIR",
        }
        assert set(paths.keys()) == expected_keys

    def test_all_values_are_pathlib_paths(self):
        """Every value in run_paths is a pathlib.Path."""
        paths = get_run_paths("AAPL", "AAPL_20260101_120000")
        for key, value in paths.items():
            assert isinstance(value, Path), f"{key} is {type(value)}, expected Path"

    def test_paths_are_scoped_under_run_id(self):
        """Run-scoped paths live under output/{run_id}/."""
        run_id = "AAPL_20260101_120000"
        paths = get_run_paths("AAPL", run_id)
        assert paths["RUN_DIR"].name == run_id
        assert paths["SQLITE_DB_PATH"].parent.name == run_id

    def test_audit_log_path_includes_run_id(self):
        """Audit log file is named audit_{run_id}.jsonl."""
        run_id = "AAPL_20260101_120000"
        paths = get_run_paths("AAPL", run_id)
        assert paths["AUDIT_LOG_PATH"].name == f"audit_{run_id}.jsonl"


class TestEnsureRunDirs:
    """Tests for the ensure_run_dirs function."""

    def test_creates_all_directories(self, tmp_path: Path):
        """ensure_run_dirs creates every directory needed by the run."""
        # Temporarily override PROJECT_ROOT-relative paths by constructing
        # a paths dict that points into tmp_path.
        run_id = "AAPL_20260101_120000"
        run_dir = tmp_path / "output" / run_id

        test_paths = {
            "RUN_DIR": run_dir,
            "SQLITE_DB_PATH": run_dir / "deligenx.db",
            "CHROMADB_DIR_PATH": run_dir / "chromadb",
            "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{run_id}.jsonl",
            "INGESTION_SUMMARY_PATH": run_dir / "ingestion_summary.json",
            "ANALYSIS_SUMMARY_PATH": run_dir / "analysis_summary.json",
            "MI_SUMMARY_PATH": run_dir / "market_intel_summary.json",
            "RISK_SCORECARD_PATH": run_dir / "risk_summary.json",
            "MEMO_OUTPUT_DIR": run_dir / "memo",
        }

        ensure_run_dirs(test_paths)

        assert run_dir.is_dir()
        assert (run_dir / "chromadb").is_dir()
        assert (run_dir / "memo").is_dir()
        assert (tmp_path / "logs").is_dir()


# ---------------------------------------------------------------------------
# tools/sqlite_tools.py tests
# ---------------------------------------------------------------------------


class TestDatabaseManager:
    """Tests for the DatabaseManager singleton."""

    def test_creates_engine_at_correct_path(self, tmp_path: Path):
        """DatabaseManager creates a SQLAlchemy engine for the given db_path."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        try:
            engine = db.get_engine()
            assert engine is not None
            assert "test.db" in str(engine.url)
        finally:
            db.dispose()

    def test_singleton_returns_same_instance(self, tmp_path: Path):
        """Two DatabaseManager calls with the same path return the same instance."""
        db_path = tmp_path / "singleton_test.db"
        db1 = DatabaseManager(db_path)
        db2 = DatabaseManager(db_path)
        try:
            assert db1 is db2
        finally:
            db1.dispose()

    def test_create_table_insert_select_roundtrip(self, tmp_path: Path):
        """Full roundtrip: create table → insert row → select row back."""
        db_path = tmp_path / "roundtrip.db"
        db = DatabaseManager(db_path)

        try:
            # Define a test table
            test_table = Table(
                "test_companies",
                db.metadata,
                Column("id", Integer, primary_key=True),
                Column("ticker", Text, nullable=False),
                Column("fiscal_year", Text, nullable=False),
            )
            db.create_tables([test_table])

            # Insert
            with db.get_connection() as conn:
                conn.execute(
                    test_table.insert(),
                    {"id": 1, "ticker": "AAPL", "fiscal_year": "2024"},
                )

            # Select
            with db.get_connection() as conn:
                result = conn.execute(
                    text("SELECT ticker, fiscal_year FROM test_companies WHERE id = :id"),
                    {"id": 1},
                )
                row = result.fetchone()

            assert row is not None
            assert row[0] == "AAPL"
            assert row[1] == "2024"
        finally:
            db.dispose()

    def test_connection_rolls_back_on_exception(self, tmp_path: Path):
        """An exception inside get_connection() triggers rollback."""
        db_path = tmp_path / "rollback_test.db"
        db = DatabaseManager(db_path)

        try:
            rollback_table = Table(
                "rollback_test",
                db.metadata,
                Column("id", Integer, primary_key=True),
                Column("value", Text),
            )
            db.create_tables([rollback_table])

            # Insert a row that should be rolled back
            with pytest.raises(RuntimeError):
                with db.get_connection() as conn:
                    conn.execute(
                        rollback_table.insert(),
                        {"id": 1, "value": "should_not_persist"},
                    )
                    raise RuntimeError("Intentional test error")

            # Verify the row was NOT persisted
            with db.get_connection() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM rollback_test"))
                count = result.scalar()

            assert count == 0, f"Expected 0 rows after rollback, got {count}"
        finally:
            db.dispose()

    def test_dispose_allows_re_creation(self, tmp_path: Path):
        """After dispose(), a new DatabaseManager for the same path works."""
        db_path = tmp_path / "dispose_test.db"

        db1 = DatabaseManager(db_path)
        db1.get_engine()  # Force engine creation
        db1.dispose()

        db2 = DatabaseManager(db_path)
        engine = db2.get_engine()
        assert engine is not None
        db2.dispose()


# ---------------------------------------------------------------------------
# utils/audit_logger.py tests
# ---------------------------------------------------------------------------


class TestLogAuditEvent:
    """Tests for the log_audit_event function."""

    def test_appends_valid_json_line(self, tmp_path: Path):
        """log_audit_event writes a valid JSON line to the file."""
        log_path = tmp_path / "audit.jsonl"

        log_audit_event(
            audit_log_path=log_path,
            agent="IngestionAgent",
            module="Phase1_TickerResolution",
            status="STARTED",
            summary="Resolving ticker AAPL.",
        )

        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["agent"] == "IngestionAgent"
        assert entry["module"] == "Phase1_TickerResolution"
        assert entry["status"] == "STARTED"
        assert entry["summary"] == "Resolving ticker AAPL."
        assert entry["duration_seconds"] is None
        assert "timestamp" in entry

    def test_appends_multiple_entries(self, tmp_path: Path):
        """Multiple calls append multiple lines to the same file."""
        log_path = tmp_path / "audit.jsonl"

        log_audit_event(log_path, "Agent1", "ModA", "STARTED", "Starting A.")
        log_audit_event(log_path, "Agent1", "ModA", "COMPLETED", "Done.", 1.5)

        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

        second = json.loads(lines[1])
        assert second["status"] == "COMPLETED"
        assert second["duration_seconds"] == 1.5

    def test_rejects_invalid_status(self, tmp_path: Path):
        """An invalid status raises ValueError."""
        log_path = tmp_path / "audit.jsonl"

        with pytest.raises(ValueError, match="Invalid audit status"):
            log_audit_event(log_path, "Agent1", "Mod", "RUNNING", "Bad status.")


class TestAuditPhase:
    """Tests for the audit_phase context manager."""

    def test_logs_started_and_completed(self, tmp_path: Path):
        """Clean execution logs STARTED then COMPLETED with duration."""
        log_path = tmp_path / "audit.jsonl"

        with audit_phase(log_path, "TestAgent", "TestModule"):
            time.sleep(0.05)  # Small delay to verify duration_seconds > 0

        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

        started = json.loads(lines[0])
        completed = json.loads(lines[1])

        assert started["status"] == "STARTED"
        assert completed["status"] == "COMPLETED"
        assert completed["duration_seconds"] > 0

    def test_logs_started_and_failed_on_exception(self, tmp_path: Path):
        """An exception inside the context logs STARTED then FAILED."""
        log_path = tmp_path / "audit.jsonl"

        with pytest.raises(ValueError, match="boom"):
            with audit_phase(log_path, "TestAgent", "FailModule"):
                raise ValueError("boom")

        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

        started = json.loads(lines[0])
        failed = json.loads(lines[1])

        assert started["status"] == "STARTED"
        assert failed["status"] == "FAILED"
        assert "ValueError: boom" in failed["summary"]
        assert failed["duration_seconds"] is not None
