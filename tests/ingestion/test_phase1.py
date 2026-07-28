import json
import shutil
from pathlib import Path

import pytest

from agents.ingestion.phase1_company_identity import Phase1Error, run_phase1
from config.paths import generate_run_id, get_run_paths


@pytest.fixture
def mock_paths(tmp_path):
    # Set up temporary directories for testing
    run_id = generate_run_id("TEST")
    
    # Overwrite the output and logs to be in tmp_path
    output_dir = tmp_path / "output"
    logs_dir = tmp_path / "logs"
    data_dir = tmp_path / "data"
    
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)
    
    ticker_cache_dir = data_dir / "cache" / "ticker_lookups"
    
    paths = {
        "RUN_DIR": run_dir,
        "SQLITE_DB_PATH": run_dir / "deligenx.db",
        "CHROMADB_DIR_PATH": run_dir / "chromadb",
        "AUDIT_LOG_PATH": logs_dir / f"audit_{run_id}.jsonl",
        "INGESTION_SUMMARY_PATH": run_dir / "ingestion_summary.json",
        "TICKER_CACHE_DIR": ticker_cache_dir,
        "FILING_CACHE_DIR": run_dir / "filing_cache",
    }
    return paths


def test_phase1_aapl_resolves_identity(mock_paths):
    result = run_phase1("AAPL", "RUN_AAPL_123", mock_paths)
    
    assert result.cik == "0000320193"
    assert result.company_identity.company_name == "Apple Inc."
    assert result.company_identity.sic_code == "3571"
    assert result.company_identity.fiscal_year_end_month == 9
    
    # Ensure audit log was written
    audit_text = mock_paths["AUDIT_LOG_PATH"].read_text()
    assert "PHASE_1_COMPANY_IDENTITY" in audit_text
    assert "COMPLETED" in audit_text


def test_phase1_selects_correct_filing_counts(mock_paths):
    result = run_phase1("AAPL", "RUN_AAPL_123", mock_paths)
    
    # Check that we got exactly up to 3 10-Ks
    assert len(result.selected_filings.ten_k) <= 3
    
    # Check that all returned 10-Ks are actually 10-Ks
    for f in result.selected_filings.ten_k:
        assert f.form == "10-K"
        
    # Check 8-Ks
    for f in result.selected_filings.eight_k:
        assert f.form == "8-K"
        
    # Check DEF 14A
    if result.selected_filings.def_14a:
        assert result.selected_filings.def_14a.form == "DEF 14A"


def test_phase1_invalid_ticker_writes_error_summary(mock_paths):
    with pytest.raises(Phase1Error) as excinfo:
        run_phase1("INVALIDTICKER123", "RUN_ERR_123", mock_paths)
        
    assert "Company not found" in str(excinfo.value)
    
    # Verify the error summary was written to INGESTION_SUMMARY_PATH
    summary_path = mock_paths["INGESTION_SUMMARY_PATH"]
    assert summary_path.exists()
    
    summary_data = json.loads(summary_path.read_text())
    assert summary_data["status"] == "ERROR"
    assert "Company not found" in summary_data["reason"]
    assert summary_data["module_status"]["phase_1_company_identity"] == "FAILED"


def test_phase1_caches_result(mock_paths, monkeypatch):
    import agents.ingestion.phase1_company_identity
    
    # First run will fetch from network
    run_phase1("MSFT", "RUN_MSFT_1", mock_paths)
    
    # Now monkeypatch the resolve function to raise an error if it's called
    # This guarantees the second run uses the cache
    def mock_resolve(*args, **kwargs):
        raise AssertionError("Network was called, cache was bypassed!")
        
    monkeypatch.setattr(agents.ingestion.phase1_company_identity, "resolve_ticker_to_cik", mock_resolve)
    
    # Second run should succeed via cache
    result = run_phase1("MSFT", "RUN_MSFT_2", mock_paths)
    assert result.cik == "0000789019"


def test_phase1_force_refresh_bypasses_cache(mock_paths, monkeypatch):
    import agents.ingestion.phase1_company_identity
    
    # First run will fetch and cache
    run_phase1("GOOG", "RUN_GOOG_1", mock_paths)
    
    # Track if network was called
    network_called = False
    
    original_resolve = agents.ingestion.phase1_company_identity.resolve_ticker_to_cik
    def mock_resolve(ticker):
        nonlocal network_called
        network_called = True
        return original_resolve(ticker)
        
    monkeypatch.setattr(agents.ingestion.phase1_company_identity, "resolve_ticker_to_cik", mock_resolve)
    
    # Second run with force_refresh=True
    run_phase1("GOOG", "RUN_GOOG_2", mock_paths, force_refresh=True)
    
    assert network_called is True
