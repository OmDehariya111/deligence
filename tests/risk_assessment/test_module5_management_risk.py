"""
Tests for Module 5 - Management Quality and Governance Risk
"""

import pytest
from unittest.mock import patch, MagicMock
from agents.risk_assessment.module5_management_risk import ManagementRiskScorer

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

def test_management_risk_degraded(mock_processor):
    scorer = ManagementRiskScorer(mock_processor)
    with patch("agents.risk_assessment.module5_management_risk.DatabaseManager") as mock_db_class:
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = []
        mock_db_class.return_value = mock_db
        scorer.run()
        
    assert scorer.total_points == 8
    assert mock_processor.risk_scorecard["MANAGEMENT"]["data_completeness"] == "PARTIAL"
    assert mock_processor.risk_scorecard["MANAGEMENT"]["risk_level"] == "LOW"

def test_mda_credibility_check(mock_processor):
    mock_processor.chromadb_available = True
    scorer = ManagementRiskScorer(mock_processor)
    scorer.sec_collection = MagicMock()
    
    def mock_sec_get(*args, **kwargs):
        where_str = str(kwargs.get("where", {}))
        if "proxy_directors" in where_str:
            return {"documents": ["proxy_doc"]}
        return None
        
    scorer.sec_collection.get.side_effect = mock_sec_get
    scorer.sec_collection.query.return_value = {"documents": [["mda_chunk"]]}
    
    with patch("agents.risk_assessment.module5_management_risk.DatabaseManager") as mock_db_class, \
         patch("agents.risk_assessment.module5_management_risk.tier2_reason_tool") as mock_t2, \
         patch("agents.risk_assessment.module5_management_risk.tier1_extract_tool") as mock_t1:
        
        mock_db = MagicMock()
        mock_y1 = MagicMock(); mock_y1._mapping = {"fiscal_year": "2023", "period_end_date": "2023-12-31"}
        mock_y2 = MagicMock(); mock_y2._mapping = {"fiscal_year": "2022", "period_end_date": "2022-12-31"}
        mock_y3 = MagicMock(); mock_y3._mapping = {"fiscal_year": "2021", "period_end_date": "2021-12-31"}
        mock_y4 = MagicMock(); mock_y4._mapping = {"fiscal_year": "2020", "period_end_date": "2020-12-31"}
        
        def mock_execute(query, params=None):
            m = MagicMock()
            q = str(query)
            if "SELECT fiscal_year" in q:
                m.fetchall.return_value = [mock_y1, mock_y2, mock_y3, mock_y4]
            elif "SELECT *" in q:
                m.fetchone.return_value = mock_y1 
            else:
                m.fetchall.return_value = []
                m.fetchone.return_value = None
            return m
            
        mock_db.execute.side_effect = mock_execute
        mock_db_class.return_value = mock_db
        
        mock_t2.side_effect = [
            [{"claim_text": "C1"}], {"status": "SEVERELY_MISSED"},
            [{"claim_text": "C2"}], {"status": "SEVERELY_MISSED"},
            [{"claim_text": "C3"}], {"status": "MISSED"}
        ]
        
        mock_t1.return_value = {}
        
        scorer.run()
        
        assert scorer.total_points == 20
        assert mock_processor.risk_scorecard["MANAGEMENT"]["data_completeness"] == "PARTIAL"
