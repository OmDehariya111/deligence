"""
Tests for Module 2 - Market Risk
"""

import pytest
from unittest.mock import patch, MagicMock
from agents.risk_assessment.module2_market_risk import MarketRiskScorer

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
    
    proc.market_intel_available = True
    proc.moat_width = "NARROW"
    proc.risk_scorecard = {}
    proc.chromadb_available = False
    
    return proc

def test_market_intel_unavailable_degrades_gracefully(mock_processor):
    # Set market intel available to false
    mock_processor.market_intel_available = False
    mock_processor.moat_width = "UNKNOWN"
    
    scorer = MarketRiskScorer(mock_processor)
    with patch("agents.risk_assessment.module2_market_risk.DatabaseManager"):
        scorer.step9_market_signals()
        scorer.step10_moat_adjustment()
        scorer.step11_chromadb_rag()
        scorer.step12_score_aggregation()
        
    # Steps 9 and 10 skipped, Step 11 zero chunk guard runs (4 times)
    assert scorer.total_points == 0
    # 4 evidence entries from zero-chunk guard in step 11
    assert len(scorer.evidence_list) == 4
    for ev in scorer.evidence_list:
        assert ev["llm_tier_used"] == "NONE_ZERO_CHUNK_GUARD"
        
    assert mock_processor.risk_scorecard["MARKET"]["data_completeness"] == "INSUFFICIENT_DATA"

def test_market_intel_available(mock_processor):
    scorer = MarketRiskScorer(mock_processor)
    
    # Mock DatabaseManager for step 9
    mock_db = MagicMock()
    # Mocking rows returned from market_risk_signals
    mock_row = MagicMock()
    mock_row._mapping = {
        "signal_category": "COMPETITOR",
        "evidence_text": "Rival growing faster",
        "risk_level": "HIGH",
        "points_contribution": 15,
        "signal_id": 1
    }
    mock_db.execute.return_value.fetchall.return_value = [mock_row]
    
    with patch("agents.risk_assessment.module2_market_risk.DatabaseManager", return_value=mock_db):
        scorer.step9_market_signals()
        scorer.step10_moat_adjustment()
        scorer.step11_chromadb_rag()
        scorer.step12_score_aggregation()
        
    # Step 9: 15 points
    # Step 10: Moat NARROW = 20 points
    # Step 11: Zero chunk = 0 points
    assert scorer.total_points == 35
    assert mock_processor.risk_scorecard["MARKET"]["data_completeness"] == "FULL"
    assert mock_processor.risk_scorecard["MARKET"]["risk_level"] == "MEDIUM" # 35 falls into 31-55
