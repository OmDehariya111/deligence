"""
Tests for Module 8 - Composite Risk Scoring
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from agents.risk_assessment.module8_composite_score import CompositeRiskScorer

@pytest.fixture
def mock_processor():
    proc = MagicMock()
    proc.ticker = "TEST"
    proc.paths = {
        "SQLITE_DB_PATH": ":memory:",
    }
    proc.investment_stance_override = None
    proc.deal_breaker_status = False
    return proc

def test_weight_redistribution_math(mock_processor):
    scorer = CompositeRiskScorer(mock_processor)
    
    with patch("agents.risk_assessment.module8_composite_score.DatabaseManager") as mock_db_class:
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        def mock_execute(query, params=None):
            m = MagicMock()
            q = str(query)
            if "SELECT dimension" in q:
                m.fetchall.return_value = [
                    ("FINANCIAL", 22, "FULL"),
                    ("MARKET", 8, "INSUFFICIENT_DATA"),
                    ("OPERATIONAL", 35, "FULL"),
                    ("LEGAL", 55, "PARTIAL"),
                    ("MANAGEMENT", 20, "PARTIAL"),
                    ("ESG", 28, "FULL")
                ]
            return m
            
        mock_db.execute.side_effect = mock_execute
        
        scorer.run()
        
        heat_map = mock_processor.risk_heat_map
        weights = heat_map["weights_used"]
        
        assert weights["Financial"] == pytest.approx(0.375)
        assert weights["Market"] == 0.0
        
        insert_call = next(c for c in mock_db.execute.call_args_list if "INSERT INTO composite_risk_output" in str(c[0][0]))
        params = insert_call[0][1]
        assert params["cs"] == 32
        assert params["rl"] == "MEDIUM RISK"
        assert "CAUTION" in params["is"]
        assert "redistributed" in params["is"]

def test_deal_breaker_override(mock_processor):
    mock_processor.investment_stance_override = "AVOID"
    mock_processor.deal_breaker_status = True
    
    scorer = CompositeRiskScorer(mock_processor)
    
    with patch("agents.risk_assessment.module8_composite_score.DatabaseManager") as mock_db_class:
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        def mock_execute(query, params=None):
            m = MagicMock()
            q = str(query)
            if "SELECT dimension" in q:
                m.fetchall.return_value = [
                    ("FINANCIAL", 10, "FULL"),
                    ("MARKET", 10, "FULL"),
                    ("OPERATIONAL", 10, "FULL"),
                    ("LEGAL", 10, "FULL"),
                    ("MANAGEMENT", 10, "FULL"),
                    ("ESG", 10, "FULL")
                ]
            return m
            
        mock_db.execute.side_effect = mock_execute
        
        scorer.run()
        
        insert_call = next(c for c in mock_db.execute.call_args_list if "INSERT INTO composite_risk_output" in str(c[0][0]))
        params = insert_call[0][1]
        
        assert params["cs"] == 10
        assert params["rl"] == "LOW RISK"
        assert params["is"] == "AVOID"
