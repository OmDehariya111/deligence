"""
Tests for Risk Assessment Pre-Processing Module
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from agents.risk_assessment.pre_processing import RiskPreProcessor
from config.paths import get_run_paths

@pytest.fixture
def run_id():
    return "AAPL_20260705_120000"

@pytest.fixture
def ticker():
    return "AAPL"

@pytest.fixture
def mock_paths(tmp_path, ticker, run_id):
    paths = get_run_paths(ticker, run_id)
    mocked = {}
    for k, v in paths.items():
        mocked[k] = tmp_path / v.name
    return mocked

def test_ingestion_failure_halts_agent(mock_paths, ticker, run_id):
    mock_paths["INGESTION_SUMMARY_PATH"].parent.mkdir(parents=True, exist_ok=True)
    with open(mock_paths["INGESTION_SUMMARY_PATH"], "w", encoding="utf-8") as f:
        json.dump({"status": "ERROR", "reason": "Missing data"}, f)
        
    with patch("agents.risk_assessment.pre_processing.get_run_paths", return_value=mock_paths):
        processor = RiskPreProcessor(ticker, run_id)
        result = processor.process()
        
        assert result is False
        assert mock_paths["RISK_SCORECARD_PATH"].exists()
        
        with open(mock_paths["RISK_SCORECARD_PATH"], "r", encoding="utf-8") as f:
            scorecard = json.load(f)
            assert scorecard["status"] == "ERROR"
            assert "Missing data" in scorecard["reason"]

def test_analysis_failure_halts_agent(mock_paths, ticker, run_id):
    mock_paths["INGESTION_SUMMARY_PATH"].parent.mkdir(parents=True, exist_ok=True)
    with open(mock_paths["INGESTION_SUMMARY_PATH"], "w", encoding="utf-8") as f:
        json.dump({"status": "COMPLETE"}, f)
        
    mock_paths["QOE_SUMMARY_PATH"].parent.mkdir(parents=True, exist_ok=True)
    with open(mock_paths["QOE_SUMMARY_PATH"], "w", encoding="utf-8") as f:
        json.dump({"status": "ERROR", "reason": "No ratios computed"}, f)

    with patch("agents.risk_assessment.pre_processing.get_run_paths", return_value=mock_paths):
        processor = RiskPreProcessor(ticker, run_id)
        result = processor.process()
        
        assert result is False
        assert mock_paths["RISK_SCORECARD_PATH"].exists()
        
        with open(mock_paths["RISK_SCORECARD_PATH"], "r", encoding="utf-8") as f:
            scorecard = json.load(f)
            assert scorecard["status"] == "ERROR"
            assert "No ratios computed" in scorecard["reason"]

@patch("agents.risk_assessment.pre_processing.DatabaseManager")
def test_market_intel_failure_degrades_gracefully(mock_db, mock_paths, ticker, run_id):
    mock_paths["INGESTION_SUMMARY_PATH"].parent.mkdir(parents=True, exist_ok=True)
    with open(mock_paths["INGESTION_SUMMARY_PATH"], "w", encoding="utf-8") as f:
        json.dump({"status": "COMPLETE"}, f)
        
    mock_paths["QOE_SUMMARY_PATH"].parent.mkdir(parents=True, exist_ok=True)
    with open(mock_paths["QOE_SUMMARY_PATH"], "w", encoding="utf-8") as f:
        json.dump({"status": "COMPLETE"}, f)
        
    mock_paths["MI_SUMMARY_PATH"].parent.mkdir(parents=True, exist_ok=True)
    with open(mock_paths["MI_SUMMARY_PATH"], "w", encoding="utf-8") as f:
        json.dump({"status": "ERROR"}, f)

    rulebook_path = Path("config/risk_scoring_config.json").resolve()
    rulebook_path.parent.mkdir(parents=True, exist_ok=True)
    if not rulebook_path.exists():
        with open(rulebook_path, "w", encoding="utf-8") as f:
            json.dump({}, f)
            
    with patch("agents.risk_assessment.pre_processing.get_run_paths", return_value=mock_paths):
        processor = RiskPreProcessor(ticker, run_id)
        with patch("chromadb.PersistentClient"):
            result = processor.process()
            
            assert result is True
            assert processor.market_intel_available is False
            assert processor.news_sentiment_available is False
            assert processor.moat_width == "UNKNOWN"
            assert "FINANCIAL" in processor.risk_scorecard
            
            for dim in ["FINANCIAL", "MARKET", "OPERATIONAL", "LEGAL", "MANAGEMENT", "ESG"]:
                assert processor.risk_scorecard[dim]["data_completeness"] == "FULL"
