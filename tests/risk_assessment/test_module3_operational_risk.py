"""
Tests for Module 3 - Operational Risk
"""

import pytest
from unittest.mock import patch, MagicMock
from agents.risk_assessment.module3_operational_risk import OperationalRiskScorer

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

def test_chromadb_unavailable_zero_chunk_fallback(mock_processor):
    scorer = OperationalRiskScorer(mock_processor)
    with patch("agents.risk_assessment.module3_operational_risk.DatabaseManager"):
        scorer.run()
        
    assert scorer.total_points == 15
    assert len(scorer.evidence_list) == 5
    for ev in scorer.evidence_list:
        assert ev["points_added"] == 3
        assert ev["severity"] == "LOW"
        assert ev["llm_tier_used"] == "NONE_ZERO_CHUNK_GUARD"
        
    assert mock_processor.risk_scorecard["OPERATIONAL"]["data_completeness"] == "PARTIAL"
    assert mock_processor.risk_scorecard["OPERATIONAL"]["risk_level"] == "LOW"

def test_chromadb_available_with_findings(mock_processor):
    mock_processor.chromadb_available = True
    scorer = OperationalRiskScorer(mock_processor)
    
    # Mocking chromadb collection query and get
    scorer.sec_collection = MagicMock()
    # Mock get to return 2 documents for 8-K departures
    scorer.sec_collection.get.return_value = {"documents": ["doc1", "doc2"]}
    # Mock query to return some chunks
    scorer.sec_collection.query.return_value = {"documents": [["chunk1", "chunk2"]]}
    
    # We must patch tier1_extract_tool so it doesn't call real LLM
    with patch("agents.risk_assessment.module3_operational_risk.DatabaseManager"), \
         patch("agents.risk_assessment.module3_operational_risk.tier1_extract_tool") as mock_llm:
        
        # We need to return specific dicts for each of the 5 steps to test scoring
        # 13: kp_lang=True, sp_ment=False + 2 departures -> CRITICAL (20)
        # 14: ss=True, mitig=False -> CRITICAL (20)
        # 15: breach=False, obsol=False, severity=MEDIUM -> MEDIUM (8)
        # 16: pct=35, severity=HIGH -> HIGH (14)
        # 17: sanctions=False, pct=15, geo="Europe" -> MEDIUM (8)
        
        mock_llm.side_effect = [
            {"key_person_language": True, "succession_planning_mentioned": False},
            {"single_source_disclosed": True, "mitigation_mentioned": False, "severity": "CRITICAL"},
            {"severity": "MEDIUM"},
            {"top_customer_pct": 35.0, "severity": "HIGH"},
            {"revenue_pct": 15.0, "geography_name": "Europe", "severity": "MEDIUM"}
        ]
        
        scorer.run()
        
        # 20 + 20 + 8 + 14 + 8 = 70
        assert scorer.total_points == 70
        assert mock_processor.risk_scorecard["OPERATIONAL"]["data_completeness"] == "FULL"
        assert mock_processor.risk_scorecard["OPERATIONAL"]["risk_level"] == "HIGH"
