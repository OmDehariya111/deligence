"""
Tests for Module 9 - Risk Mitigation Recommendations
"""

import pytest
from unittest.mock import patch, MagicMock
from agents.risk_assessment.module9_mitigation import MitigationRecommender

@pytest.fixture
def mock_processor():
    proc = MagicMock()
    proc.ticker = "TEST"
    proc.paths = {
        "SQLITE_DB_PATH": ":memory:",
    }
    return proc

def test_zero_findings(mock_processor):
    recommender = MitigationRecommender(mock_processor)
    
    with patch("agents.risk_assessment.module9_mitigation.DatabaseManager") as mock_db_class, \
         patch("agents.risk_assessment.module9_mitigation.tier2_reason_tool") as mock_t2:
        
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        def mock_execute(query, params=None):
            m = MagicMock()
            q = str(query)
            if "SELECT dimension" in q:
                m.fetchall.return_value = []
            return m
            
        mock_db.execute.side_effect = mock_execute
        
        recommender.run()
        
        mock_t2.assert_not_called()
        
        log_call = mock_processor.log_audit.call_args_list[-1]
        assert "0 recommendations generated" in log_call[0][2]

def test_llm_error_handling(mock_processor):
    recommender = MitigationRecommender(mock_processor)
    
    with patch("agents.risk_assessment.module9_mitigation.DatabaseManager") as mock_db_class, \
         patch("agents.risk_assessment.module9_mitigation.tier2_reason_tool") as mock_t2:
        
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        def mock_execute(query, params=None):
            m = MagicMock()
            q = str(query)
            if "SELECT dimension" in q:
                m.fetchall.return_value = [
                    ("FINANCIAL", "Liquidity", "bad liquidity", "CRITICAL", 2),
                    ("OPERATIONAL", "Customers", "one customer", "HIGH", 5)
                ]
            return m
            
        mock_db.execute.side_effect = mock_execute
        
        mock_t2.side_effect = [
            Exception("LLM Timeout"),
            {"recommendation_text": "Talk to customer", "condition_type": "SITE_VISIT"}
        ]
        
        recommender.run()
        
        assert mock_t2.call_count == 2
        
        insert_calls = [c for c in mock_db.execute.call_args_list if "INSERT INTO risk_mitigation_recommendations" in str(c[0][0])]
        assert len(insert_calls) == 1
        params = insert_calls[0][0][1]
        assert params["pri"] == "NEAR_TERM"
        assert params["rt"] == "Talk to customer"
