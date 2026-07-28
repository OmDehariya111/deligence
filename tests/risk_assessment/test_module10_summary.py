"""
Tests for Module 10 - Final Summary
"""

import pytest
import json
import os
from unittest.mock import patch, MagicMock
from agents.risk_assessment.module10_summary import RiskAssessmentSummary

@pytest.fixture
def mock_processor(tmp_path):
    proc = MagicMock()
    proc.ticker = "TEST"
    proc.run_id = "run123"
    proc.company_name = "Test Co."
    proc.paths = {
        "SQLITE_DB_PATH": ":memory:",
        "RISK_SCORECARD_PATH": str(tmp_path / "output.json")
    }
    proc.chromadb_available = False
    proc.market_intel_available = False
    proc.news_sentiment_available = False
    proc.llm_usage_stats = {}
    proc.deal_breaker_status = False
    proc.investment_stance_override = None
    return proc

def test_json_structure(mock_processor):
    summary = RiskAssessmentSummary(mock_processor)
    
    with patch("agents.risk_assessment.module10_summary.DatabaseManager") as mock_db_class:
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        summary.run()
        
        assert os.path.exists(mock_processor.paths["RISK_SCORECARD_PATH"])
        with open(mock_processor.paths["RISK_SCORECARD_PATH"], "r") as f:
            data = json.load(f)
            
        assert data["ticker"] == "TEST"
        assert "modules_status" in data
        assert "COMPOSITE_RISK" in data
        assert "DIMENSION_SCORES" in data
        assert "DEAL_BREAKER_STATUS" in data

def test_degradation_transparency(mock_processor):
    mock_processor.chromadb_available = False
    
    summary = RiskAssessmentSummary(mock_processor)
    with patch("agents.risk_assessment.module10_summary.DatabaseManager") as mock_db_class:
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        def mock_execute(query, params=None):
            m = MagicMock()
            q = str(query)
            if "SELECT data_completeness FROM risk_dimensions" in q:
                if params and params.get("d") == "MARKET":
                    m.fetchone.return_value = ("INSUFFICIENT_DATA",)
                else:
                    m.fetchone.return_value = ("FULL",)
            return m
            
        mock_db.execute.side_effect = mock_execute
        
        summary.run()
        
        with open(mock_processor.paths["RISK_SCORECARD_PATH"], "r") as f:
            data = json.load(f)
            
        assert data["modules_status"]["chromadb_available"] is False
        assert data["modules_status"]["module_2_market_risk"] == "PARTIAL"
        assert data["status"] == "COMPLETE_WITH_DEGRADATION"
