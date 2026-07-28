import json
import pytest
from pathlib import Path
from sqlalchemy import MetaData, Table, Column, Integer, String, Float

from config.paths import generate_run_id, get_run_paths
from agents.analysis.analysis_agent import AnalysisAgent
from tools.sqlite_tools import DatabaseManager


@pytest.fixture
def run_env(tmp_path, monkeypatch):
    """Sets up a temporary run environment, patching config.paths."""
    ticker = "AAPL"
    run_id = generate_run_id(ticker)
    
    # Patch OUTPUT_DIR and LOGS_DIR so we don't write to real paths
    monkeypatch.setattr("config.paths.OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr("config.paths.LOGS_DIR", tmp_path / "logs")
    
    paths = get_run_paths(ticker, run_id)
    return ticker, run_id, paths

def _setup_ingestion_summary(paths: dict[str, Path], status: str = "COMPLETE", missing_fields: list = None):
    """Helper to mock an ingestion_summary.json."""
    summary_path = paths["INGESTION_SUMMARY_PATH"]
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    
    summary = {
        "status": status,
        "company_identity": {"ticker": "AAPL"},
        "missing_critical_fields": missing_fields or [],
        "reason": "Test reason" if status == "ERROR" else None
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f)

def _setup_financial_data(paths: dict[str, Path], years: list[int]):
    """Helper to mock financial data in SQLite."""
    db = DatabaseManager(paths["SQLITE_DB_PATH"])
    metadata = MetaData()
    
    financial_table = Table(
        "financial_data", metadata,
        Column("id", Integer, primary_key=True),
        Column("ticker", String),
        Column("fiscal_year", Integer),
        Column("revenue", Float)
    )
    
    with db.get_connection() as conn:
        financial_table.create(conn.engine, checkfirst=True)
        for year in years:
            conn.execute(financial_table.insert().values(
                ticker="AAPL",
                fiscal_year=year,
                revenue=1000.0
            ))
    db.dispose()


def test_missing_ingestion_summary(run_env):
    ticker, run_id, paths = run_env
    # We do NOT create an ingestion summary
    
    agent = AnalysisAgent(ticker, run_id)
    agent.run()
    
    # Check that error was handled
    qoe_path = paths["QOE_SUMMARY_PATH"]
    assert qoe_path.exists()
    
    with open(qoe_path) as f:
        qoe = json.load(f)
        assert qoe["status"] == "ERROR"
        assert "not found" in qoe["reason"]


def test_error_ingestion_summary_status(run_env):
    ticker, run_id, paths = run_env
    _setup_ingestion_summary(paths, status="ERROR")
    
    agent = AnalysisAgent(ticker, run_id)
    agent.run()
    
    # Check QOE output
    qoe_path = paths["QOE_SUMMARY_PATH"]
    assert qoe_path.exists()
    with open(qoe_path) as f:
        qoe = json.load(f)
        assert qoe["status"] == "ERROR"
        assert "Test reason" in qoe["reason"]
        
    # Check downstream outputs skipped
    for key in ["RATIO_DB_PATH", "TREND_ANALYSIS_PATH", "FRAUD_DISTRESS_PATH"]:
        with open(paths[key]) as f:
            skipped = json.load(f)
            assert skipped["status"] == "SKIPPED"


def test_data_depth_mode_full(run_env):
    ticker, run_id, paths = run_env
    _setup_ingestion_summary(paths, status="COMPLETE")
    _setup_financial_data(paths, [2020, 2021, 2022, 2023, 2024])
    
    agent = AnalysisAgent(ticker, run_id)
    agent.run()
    
    assert agent.n_years == 5
    assert agent.data_depth_mode == "FULL"
    assert agent.current_year == 2024
    assert agent.prior_year == 2023


def test_data_depth_mode_reduced(run_env):
    ticker, run_id, paths = run_env
    _setup_ingestion_summary(paths, status="COMPLETE")
    _setup_financial_data(paths, [2021, 2022, 2023]) # 3 years
    
    agent = AnalysisAgent(ticker, run_id)
    agent.run()
    
    assert agent.n_years == 3
    assert agent.data_depth_mode == "REDUCED"
    assert agent.current_year == 2023
    assert agent.prior_year == 2022


def test_data_depth_mode_minimal(run_env):
    ticker, run_id, paths = run_env
    _setup_ingestion_summary(paths, status="COMPLETE")
    _setup_financial_data(paths, [2024]) # 1 year
    
    agent = AnalysisAgent(ticker, run_id)
    agent.run()
    
    assert agent.n_years == 1
    assert agent.data_depth_mode == "MINIMAL"
    assert agent.current_year == 2024
    assert agent.prior_year is None
