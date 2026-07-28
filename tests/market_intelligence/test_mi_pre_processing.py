"""
Tests for Market Intelligence Pre-Processing Module.
"""
import json
import pytest
from pathlib import Path

from config.paths import get_run_paths, generate_run_id
from agents.market_intelligence.pre_processing import MarketIntelPreProcessor, PreProcessingError

@pytest.fixture
def run_env(tmp_path, monkeypatch):
    """Sets up a temporary output directory mimicking the run environment."""
    ticker = "AAPL"
    run_id = f"{ticker}_20260705_120000"
    
    # Patch OUTPUT_DIR and LOGS_DIR in config.paths to point to tmp_path
    monkeypatch.setattr("config.paths.OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr("config.paths.LOGS_DIR", tmp_path / "logs")
    
    paths = get_run_paths(ticker, run_id)
    
    # Create necessary parent directories
    paths["INGESTION_SUMMARY_PATH"].parent.mkdir(parents=True, exist_ok=True)
    paths["RATIO_DB_PATH"].parent.mkdir(parents=True, exist_ok=True)
    paths["SECTOR_BENCH_JSON"].parent.mkdir(parents=True, exist_ok=True)
    paths["CHROMADB_DIR_PATH"].mkdir(parents=True, exist_ok=True)
    paths["AUDIT_LOG_PATH"].parent.mkdir(parents=True, exist_ok=True)
    
    # Write a valid Ingestion Summary
    ingestion_summary = {
        "run_id": run_id,
        "status": "SUCCESS",
        "module_status": {},
        "company_identity": {
            "company_name": "Apple Inc.",
            "cik": "0000320193",
            "sic_code": "3571",
            "industry_name": "Electronic Computers",
            "fiscal_year_end": "09-30",
            "fiscal_year_end_month": 9
        },
        "financial_data_coverage": {},
        "field_coverage_summary": {
            "total_fields": 100,
            "fields_with_data": 90,
            "fields_missing": 5,
            "fields_computed": 5
        },
        "missing_critical_fields": [],
        "vector_database_stats": {
            "total_chunks": 500,
            "chunks_from_10k": 200,
            "chunks_from_8k": 300,
            "chunks_from_proxy": 0,
            "chunks_from_user_file": 0,
            "filings_processed": {}
        },
        "xbrl_tags_used": {},
        "warnings": [],
        "errors": [],
        "ingestion_timestamp": "2026-07-05T12:00:00Z",
        "ingestion_duration_seconds": 120
    }
    
    with open(paths["INGESTION_SUMMARY_PATH"], "w") as f:
        json.dump(ingestion_summary, f)
        
    # Write a valid Sector Benchmark Report
    sector_benchmark = {
        "ticker": ticker,
        "sic_code": "3571",
        "industry": "Electronic Computers",
        "benchmark_year": 2023,
        "peer_count": 5,
        "top_peers": [
            {"cik": "0000000001", "entity_name": "Peer 1", "revenue": 1000000},
            {"cik": "0000000002", "entity_name": "Peer 2", "revenue": 800000}
        ],
        "metrics": {}
    }
    with open(paths["SECTOR_BENCH_JSON"], "w") as f:
        json.dump(sector_benchmark, f)
        
    # Write a valid Ratio Database
    ratio_db = [
        {
            "ratio_name": "current_ratio",
            "fiscal_year": 2023,
            "value": 1.5,
            "unit": "x",
            "formula": "current_assets / current_liabilities",
            "inputs_used": {"current_assets": 150, "current_liabilities": 100},
            "status": "COMPUTED"
        }
    ]
    with open(paths["RATIO_DB_PATH"], "w") as f:
        json.dump(ratio_db, f)
        
    return ticker, run_id, paths

def test_successful_pre_processing(run_env):
    """Test standard valid case."""
    ticker, run_id, paths = run_env
    processor = MarketIntelPreProcessor(ticker, run_id)
    context = processor.run()
    
    assert context.ticker == ticker
    assert context.most_recent_fiscal_year == 2023
    assert not context.is_sector_benchmark_partial
    assert context.is_chromadb_reachable
    assert len(context.top_peers) == 2
    assert "current_ratio" in context.target_ratios

def test_halt_on_ingestion_error(run_env):
    """Test PreProcessingError when Ingestion Summary has status ERROR."""
    ticker, run_id, paths = run_env
    with open(paths["INGESTION_SUMMARY_PATH"], "w") as f:
        json.dump({"status": "ERROR", "reason": "Bad ticker"}, f)
        
    processor = MarketIntelPreProcessor(ticker, run_id)
    with pytest.raises(PreProcessingError, match="Upstream Ingestion Agent failed"):
        processor.run()
        
    # Verify MI_SUMMARY_PATH was written
    assert paths["MI_SUMMARY_PATH"].exists()
    with open(paths["MI_SUMMARY_PATH"]) as f:
        err_data = json.load(f)
        assert err_data["status"] == "ERROR"
        assert err_data["reason"] == "Upstream Ingestion Agent failed: Bad ticker"

def test_halt_on_missing_sector_benchmark(run_env):
    """Test Fix M-1: Agent must halt if SECTOR_BENCH_JSON does not exist."""
    ticker, run_id, paths = run_env
    paths["SECTOR_BENCH_JSON"].unlink() # Delete the file
    
    processor = MarketIntelPreProcessor(ticker, run_id)
    with pytest.raises(PreProcessingError, match="Sector Benchmark file not found"):
        processor.run()

def test_degradation_on_partial_sector_benchmark(run_env):
    """Test graceful degradation when SECTOR_BENCH_JSON exists but is PARTIAL."""
    ticker, run_id, paths = run_env
    with open(paths["SECTOR_BENCH_JSON"], "w") as f:
         json.dump({"status": "PARTIAL", "peer_count": 0, "reason": "No peers found"}, f)
         
    processor = MarketIntelPreProcessor(ticker, run_id)
    context = processor.run()
    
    assert context.is_sector_benchmark_partial is True
    assert len(context.top_peers) == 0

def test_audit_log_entries_written(run_env):
    """Verify STARTED and COMPLETED are logged correctly."""
    ticker, run_id, paths = run_env
    processor = MarketIntelPreProcessor(ticker, run_id)
    processor.run()
    
    assert paths["AUDIT_LOG_PATH"].exists()
    with open(paths["AUDIT_LOG_PATH"]) as f:
        logs = [json.loads(line) for line in f.readlines()]
    
    assert len(logs) >= 2
    assert logs[0]["module"] == "PRE_PROCESSING"
    assert logs[0]["status"] == "STARTED"
    assert logs[-1]["module"] == "PRE_PROCESSING"
    assert logs[-1]["status"] == "COMPLETED"
