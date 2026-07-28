"""
Tests for Module 6 - ESG Risk Scoring
"""

import pytest
from unittest.mock import patch, MagicMock
from agents.risk_assessment.module6_esg_risk import ESGRiskScorer

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
    
    return proc

def test_esg_risk_degraded(mock_processor):
    scorer = ESGRiskScorer(mock_processor)
    with patch("agents.risk_assessment.module6_esg_risk.DatabaseManager") as mock_db_class:
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = []
        mock_db_class.return_value = mock_db
        scorer.run()
        
    assert scorer.total_points == 6
    assert mock_processor.risk_scorecard["ESG"]["data_completeness"] == "PARTIAL"
    assert mock_processor.risk_scorecard["ESG"]["risk_level"] == "LOW"

def test_esg_momentum_improving(mock_processor):
    mock_processor.chromadb_available = True
    scorer = ESGRiskScorer(mock_processor)
    scorer.sec_collection = MagicMock()
    
    with patch("agents.risk_assessment.module6_esg_risk.DatabaseManager") as mock_db_class, \
         patch("agents.risk_assessment.module6_esg_risk.tier1_extract_tool") as mock_t1:
        
        mock_db = MagicMock()
        def mock_execute(query, params=None):
            m = MagicMock()
            q = str(query)
            if "SELECT fiscal_year" in q:
                m.fetchall.return_value = [("2020",), ("2021",), ("2022",), ("2023",)]
            return m
        mock_db.execute.side_effect = mock_execute
        mock_db_class.return_value = mock_db
        
        def mock_query(**kwargs):
            where = kwargs.get("where", {})
            fy = None
            if "$and" in where:
                for cond in where["$and"]:
                    if "fiscal_year" in cond:
                        fy = cond["fiscal_year"]
            
            if fy in ["2022", "2023"]:
                return {"documents": [["esg_chunk"]]}
            elif fy in ["2020", "2021"]:
                return {"documents": []}
            return {"documents": [["random_chunk"]]}
            
        scorer.sec_collection.query.side_effect = mock_query
        
        mock_t1.side_effect = [
            {"severity": "MEDIUM", "description": "Env"},
            {"severity": "HIGH", "description": "Soc"},
            {"no_code_of_conduct": False, "fcpa_risk": False, "data_privacy_gap": True, "strong_framework": False}
        ]
        
        scorer.run()
        
        assert scorer.total_points == 30
        assert mock_processor.risk_scorecard["ESG"]["data_completeness"] == "FULL"
        assert mock_processor.risk_scorecard["ESG"]["risk_level"] == "LOW"
