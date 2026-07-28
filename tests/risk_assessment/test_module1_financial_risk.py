"""
Tests for Module 1 - Financial Risk
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from agents.risk_assessment.module1_financial_risk import FinancialRiskScorer
from agents.risk_assessment.pre_processing import RiskPreProcessor

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
    
    with open("config/risk_scoring_config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
    
    proc.scoring_rulebook = cfg
    proc.risk_scorecard = {}
    proc.chromadb_available = False
    
    return proc

def test_unified_status_check(mock_processor):
    mock_processor.analysis_summary = {
        "ratios": {
            "most_recent_year": {
                "current_ratio": {"status": "COMPUTED", "value": 0.8},
                "quick_ratio": {"status": "MISSING", "value": 0.5},
                "cash_ratio": {"status": "NOT_APPLICABLE"}
            }
        }
    }
    scorer = FinancialRiskScorer(mock_processor)
    with patch("agents.risk_assessment.module1_financial_risk.DatabaseManager"):
        scorer.step2_liquidity()
        
    assert scorer.total_points == 25
    assert len(scorer.evidence_list) == 1
    assert scorer.evidence_list[0]["severity"] == "CRITICAL"
    
    assert scorer.rules_evaluated == 1
    assert scorer.rules_skipped == 2

def test_fraud_distress_compound(mock_processor):
    mock_processor.analysis_summary = {
        "fraud_distress": {
            "beneish_m_score": {"verdict": "LIKELY_MANIPULATOR"},
            "altman_z_score": {"most_recent_year": {"verdict": "DISTRESS_ZONE"}}
        },
        "anomalies": {
            "triggered_flags": [
                {"severity": "CRITICAL", "description": "anomaly 1"},
                {"severity": "CRITICAL", "description": "anomaly 2"}
            ]
        }
    }
    scorer = FinancialRiskScorer(mock_processor)
    with patch("agents.risk_assessment.module1_financial_risk.DatabaseManager"):
        scorer.step6_fraud_distress()
        
    assert scorer.total_points == 110
    
def test_zero_chunk_guard(mock_processor):
    scorer = FinancialRiskScorer(mock_processor)
    with patch("agents.risk_assessment.module1_financial_risk.DatabaseManager"):
        scorer.step7_chromadb_rag()
        
    assert len(scorer.evidence_list) == 6
    assert scorer.total_points == 0
    for ev in scorer.evidence_list:
        assert ev["llm_tier_used"] == "NONE_ZERO_CHUNK_GUARD"
        assert ev["chunks_retrieved_count"] == 0
