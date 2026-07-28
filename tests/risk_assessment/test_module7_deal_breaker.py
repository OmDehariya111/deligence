"""
Tests for Module 7 - Deal Breaker Detection
"""

import pytest
from unittest.mock import patch, MagicMock
from agents.risk_assessment.module7_deal_breaker import DealBreakerDetector

@pytest.fixture
def mock_processor():
    proc = MagicMock()
    proc.run_id = "test_run"
    proc.ticker = "TEST"
    proc.paths = {
        "SQLITE_DB_PATH": ":memory:",
        "CHROMADB_DIR_PATH": "dummy_path"
    }
    proc.fiscal_year_end_date = "2023-12-31"
    proc.chromadb_available = False
    proc.news_sentiment_available = False
    proc.analysis_data = {}
    return proc

def test_db3_degradation(mock_processor):
    mock_processor.chromadb_available = True
    detector = DealBreakerDetector(mock_processor)
    detector.sec_collection = MagicMock()
    
    detector.sec_collection.query.return_value = {"documents": [["fraud chunk"]]}
    
    with patch("agents.risk_assessment.module7_deal_breaker.DatabaseManager") as mock_db_class:
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        detector.run()
        
    db3 = next(f for f in detector.flags if f["flag_type"] == "ACTIVE_SEC_FRAUD")
    assert db3["triggered"] == 1
    assert db3["data_completeness"] == "PARTIAL_NEWS_UNAVAILABLE"
    assert "triggered on filing-disclosure evidence alone" in db3["evidence_text"]

def test_db5_not_applicable(mock_processor):
    mock_processor.analysis_data = {
        "altman_z_score": {"status": "NOT_APPLICABLE"}
    }
    detector = DealBreakerDetector(mock_processor)
    with patch("agents.risk_assessment.module7_deal_breaker.DatabaseManager") as mock_db_class:
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        detector.run()
        
    db5 = next(f for f in detector.flags if f["flag_type"] == "BANKRUPTCY_IMMINENT")
    assert db5["triggered"] == 0
    assert "NOT_APPLICABLE" in db5["evidence_text"]

def test_override_logic(mock_processor):
    mock_processor.chromadb_available = True
    detector = DealBreakerDetector(mock_processor)
    detector.sec_collection = MagicMock()
    
    def mock_query(**kwargs):
        query_text = kwargs.get("query_texts", [""])[0]
        if "restated OR restatement" in query_text:
            return {"documents": [["restatement chunk"]]}
        return {"documents": []}
    detector.sec_collection.query.side_effect = mock_query
    
    with patch("agents.risk_assessment.module7_deal_breaker.DatabaseManager") as mock_db_class:
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        detector.run()
        
    assert mock_processor.deal_breaker_status is True
    assert mock_processor.investment_stance_override == "AVOID"
