"""
Tests for Module 4 - Legal and Regulatory Risk
"""

import pytest
from unittest.mock import patch, MagicMock
from agents.risk_assessment.module4_legal_risk import LegalRiskScorer

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
    proc.risk_scorecard = {}
    proc.chromadb_available = False
    proc.news_sentiment_available = False
    
    return proc

def test_legal_risk_degraded(mock_processor):
    scorer = LegalRiskScorer(mock_processor)
    with patch("agents.risk_assessment.module4_legal_risk.DatabaseManager"):
        scorer.run()
        
    assert scorer.total_points == 0
    assert mock_processor.risk_scorecard["LEGAL"]["data_completeness"] == "PARTIAL"
    assert mock_processor.risk_scorecard["LEGAL"]["risk_level"] == "LOW"

def test_legal_risk_news_deduplication(mock_processor):
    mock_processor.chromadb_available = True
    mock_processor.news_sentiment_available = True
    
    scorer = LegalRiskScorer(mock_processor)
    scorer.sec_collection = MagicMock()
    
    def mock_get(*args, **kwargs):
        where = kwargs.get("where", {})
        where_str = str(where)
        if "1.03" in where_str:
            return {"documents": ["bankruptcy doc"]}
        return None
        
    scorer.sec_collection.get.side_effect = mock_get
    scorer.sec_collection.query.return_value = {"documents": [["dummy chunk"]]}
    
    with patch("agents.risk_assessment.module4_legal_risk.DatabaseManager") as mock_db_class, \
         patch("agents.risk_assessment.module4_legal_risk.tier1_extract_tool") as mock_llm:
        
        mock_llm.side_effect = [
            [{"type": "SECURITIES_LITIGATION", "severity": "CRITICAL"}],
            [],
            {},
            {},
            {}
        ]
        
        mock_db = MagicMock()
        mock_row_1 = MagicMock(); mock_row_1._mapping = {"crisis_type": "MAJOR_LAWSUIT"}
        mock_row_2 = MagicMock(); mock_row_2._mapping = {"crisis_type": "SEC_INVESTIGATION"}
        mock_row_3 = MagicMock(); mock_row_3._mapping = {"crisis_type": "BANKRUPTCY_SIGNAL"}
        
        def mock_db_execute(query, params=None):
            mock_res = MagicMock()
            q = str(query)
            rows = []
            if "MAJOR_LAWSUIT" in q: rows.append(mock_row_1)
            if "SEC_INVESTIGATION" in q: rows.append(mock_row_2)
            if "BANKRUPTCY_SIGNAL" in q: rows.append(mock_row_3)
            mock_res.fetchall.return_value = rows
            return mock_res
            
        mock_db = MagicMock()
        mock_db.execute.side_effect = mock_db_execute
        mock_db_class.return_value = mock_db
        
        scorer.run()
        
        # Step 19: 30 pts. Deduplicates major lawsuit & sec investigation news flag.
        # Step 24: 1.03 -> 25 pts. Deduplicates bankruptcy news flag.
        # Total points = 55
        assert scorer.total_points == 55
        assert mock_processor.risk_scorecard["LEGAL"]["data_completeness"] == "FULL"
