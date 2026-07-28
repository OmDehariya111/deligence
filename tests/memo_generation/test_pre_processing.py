"""
Module:  test_pre_processing.py
Agent:   Memo Generation Agent
Purpose: Test the MemoPreProcessor class logic.
Inputs:  None
Outputs: None
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from agents.memo_generation.pre_processing import MemoPreProcessor

@pytest.fixture
def mock_run_dir(tmp_path):
    run_id = "AAPL_20260703_190501"
    run_dir = tmp_path / "output" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Write mock ingestion summary
    ingestion_summary = {
        "status": "COMPLETE",
        "missing_critical_fields": [],
        "field_coverage_summary": {"fields_missing": 0}
    }
    with open(run_dir / "ingestion_summary.json", "w") as f:
        json.dump(ingestion_summary, f)
        
    # Write mock qoe summary
    qoe_summary = {
        "status": "COMPLETE",
        "earnings_quality_label": "GOOD"
    }
    (run_dir / "analysis").mkdir(exist_ok=True)
    with open(run_dir / "analysis" / "qoe_summary.json", "w") as f:
        json.dump(qoe_summary, f)
        
    # Write mock MI summary
    mi_summary = {"status": "COMPLETE"}
    with open(run_dir / "market_intel_summary.json", "w") as f:
        json.dump(mi_summary, f)
        
    # Write mock risk summary
    risk_summary = {"status": "COMPLETE"}
    with open(run_dir / "risk_assessment_summary.json", "w") as f:
        json.dump(risk_summary, f)

    return tmp_path, run_dir, run_id

@patch("agents.memo_generation.pre_processing.DatabaseManager")
@patch("agents.memo_generation.pre_processing.get_run_paths")
def test_pre_processing_success(mock_get_paths, mock_db_manager, mock_run_dir):
    tmp_path, run_dir, run_id = mock_run_dir
    
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{run_id}.jsonl",
        "MEMO_JSON_CERT_PATH": run_dir / "memo" / f"{run_id}_data_integrity_certificate.json",
        "INGESTION_SUMMARY_PATH": run_dir / "ingestion_summary.json",
        "QOE_SUMMARY_PATH": run_dir / "analysis" / "qoe_summary.json",
        "MI_SUMMARY_PATH": run_dir / "market_intel_summary.json",
        "RISK_SCORECARD_PATH": run_dir / "risk_assessment_summary.json",
        "CHROMADB_DIR_PATH": run_dir / "chromadb",
        "SQLITE_DB_PATH": run_dir / "deligenx.db"
    }
    
    # Mock safe_query calls in preprocessor to return empty dataframes mostly
    mock_db_instance = mock_db_manager.return_value
    
    processor = MemoPreProcessor("AAPL", run_id)
    
    # Mock subprocess for LO
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result, data, tables, num_lookup, num_meta = processor.run()
        
    assert result.status == "COMPLETE"
    assert result.market_intel_available is True
    assert result.risk_assessment_available is True

@patch("agents.memo_generation.pre_processing.DatabaseManager")
@patch("agents.memo_generation.pre_processing.get_run_paths")
def test_pre_processing_degrades_gracefully(mock_get_paths, mock_db_manager, mock_run_dir):
    tmp_path, run_dir, run_id = mock_run_dir
    
    # Remove MI and Risk summaries to simulate unavailability
    (run_dir / "market_intel_summary.json").unlink()
    (run_dir / "risk_assessment_summary.json").unlink()
    
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{run_id}.jsonl",
        "MEMO_JSON_CERT_PATH": run_dir / "memo" / f"{run_id}_data_integrity_certificate.json",
        "INGESTION_SUMMARY_PATH": run_dir / "ingestion_summary.json",
        "QOE_SUMMARY_PATH": run_dir / "analysis" / "qoe_summary.json",
        "MI_SUMMARY_PATH": run_dir / "market_intel_summary.json",
        "RISK_SCORECARD_PATH": run_dir / "risk_assessment_summary.json",
        "CHROMADB_DIR_PATH": run_dir / "chromadb",
        "SQLITE_DB_PATH": run_dir / "deligenx.db"
    }
    
    processor = MemoPreProcessor("AAPL", run_id)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result, _, _, _, _ = processor.run()
        
    assert result.status == "COMPLETE"
    assert result.market_intel_available is False
    assert result.risk_assessment_available is False
