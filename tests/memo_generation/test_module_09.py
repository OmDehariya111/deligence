"""
Module:  test_module_09.py
Agent:   Memo Generation Agent
Purpose: Test the RecommendationModule logic, including Python-forced stance overrides.
Inputs:  None
Outputs: None
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from agents.memo_generation.module_09_recommendation import RecommendationModule
from schemas.pydantic_models import (
    MemoDataConfidence,
    MemoDocumentPlan,
    MemoModule1Result,
    SectionPlanEntry,
)

@pytest.fixture
def mock_run_id_m09():
    return "AAPL_20260703_190501"

@pytest.fixture
def mock_m1_result_success(mock_run_id_m09):
    return MemoModule1Result(
        run_id=mock_run_id_m09,
        status="COMPLETE",
        template_variant="STANDARD",
        template_sub_flags=[],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", risk_assessment="HIGH", # ENABLES MODULE 9 NORMAL
            recommendation="HIGH"
        ),
        section_plan=MemoDocumentPlan(
            executive_summary=SectionPlanEntry(target_words=500, depth="STANDARD"),
            company_overview=SectionPlanEntry(target_words=450, depth="STANDARD"),
            financial_analysis=SectionPlanEntry(target_words=1000, depth="STANDARD"),
            sector_benchmarking=SectionPlanEntry(target_words=500, depth="STANDARD"),
            market_context=SectionPlanEntry(target_words=550, depth="STANDARD"),
            risk_assessment=SectionPlanEntry(target_words=1100, depth="STANDARD"),
            action_items=SectionPlanEntry(target_words=300, depth="STANDARD"),
            recommendation=SectionPlanEntry(target_words=600, depth="STANDARD")
        )
    )

@pytest.fixture
def mock_m1_result_unavailable(mock_run_id_m09):
    return MemoModule1Result(
        run_id=mock_run_id_m09,
        status="COMPLETE",
        template_variant="LIMITED_DATA",
        template_sub_flags=["RISK_ASSESSMENT_UNAVAILABLE"],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", risk_assessment="UNAVAILABLE", # ALTERS MODULE 9 STANCE
            recommendation="HIGH"
        ),
        section_plan=MemoDocumentPlan(
            executive_summary=SectionPlanEntry(target_words=500, depth="STANDARD"),
            company_overview=SectionPlanEntry(target_words=450, depth="STANDARD"),
            financial_analysis=SectionPlanEntry(target_words=1000, depth="STANDARD"),
            sector_benchmarking=SectionPlanEntry(target_words=500, depth="STANDARD"),
            market_context=SectionPlanEntry(target_words=550, depth="STANDARD"),
            risk_assessment=SectionPlanEntry(target_words=1100, depth="STANDARD"),
            action_items=SectionPlanEntry(target_words=300, depth="STANDARD"),
            recommendation=SectionPlanEntry(target_words=600, depth="STANDARD")
        )
    )

@pytest.fixture
def mock_data_m09():
    return {
        "memo_data": {
            "ingestion": {"company_name": "Apple Inc."},
            "analysis": {
                "top_strengths": ["High cash flow"],
                "top_concerns": ["Slowing growth"],
                "earnings_quality_label": "HIGH",
                "data_limitations": {"missing_fields": []}
            },
            "market_intel": {
                "COMPETITIVE_MOAT": {"moat_width": "WIDE"},
                "OVERALL_COMPETITIVE_POSITION": {"verdict": "STRONG"},
                "IMPLIED_VALUATION": {"valuation_verdict": "UNDERVALUED"}
            },
            "risk": {
                "COMPOSITE_RISK": {
                    "deal_breaker": False,
                    "investment_stance": "PROCEED",
                    "headline": "Proceed with standard conditions.",
                    "composite_score": 25,
                    "composite_risk_level": "LOW"
                }
            }
        },
        "db_tables": {
            "risk_evidence": pd.DataFrame(),
            "top_risks": pd.DataFrame(),
            "risk_mitigation_recommendations": pd.DataFrame()
        },
        "number_lookup": {"fake_key": "123"},
        "number_lookup_metadata": {}
    }

@patch("agents.memo_generation.module_09_recommendation.DatabaseManager")
@patch("agents.memo_generation.module_09_recommendation.get_run_paths")
@patch("agents.memo_generation.module_09_recommendation.litellm.completion")
def test_recommendation_success(mock_llm, mock_get_paths, mock_db, tmp_path, mock_m1_result_success, mock_data_m09):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db"
    }
    
    def make_mock(content):
        m = MagicMock()
        m.message.content = content
        c = MagicMock()
        c.message = m.message
        ret = MagicMock()
        ret.choices = [c]
        return ret
        
    mock_llm.side_effect = [
        make_mock("Based on a comprehensive analysis of Apple Inc.'s financial position, competitive dynamics, and risk profile, our investment stance is: PROCEED.\n\nData Integrity Disclosure..."), # > 100 chars
        make_mock(json.dumps([])) # Validation
    ]
    
    module = RecommendationModule("AAPL", mock_m1_result_success, **mock_data_m09)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.fallback_used is False
    assert result.facts_block_payload["investment_stance"] == "PROCEED"
    assert "PROCEED" in result.recommendation_narrative
    assert mock_llm.call_count == 2 # 1 narrative, 1 validation

@patch("agents.memo_generation.module_09_recommendation.DatabaseManager")
@patch("agents.memo_generation.module_09_recommendation.get_run_paths")
@patch("agents.memo_generation.module_09_recommendation.litellm.completion")
def test_recommendation_unavailable(mock_llm, mock_get_paths, mock_db, tmp_path, mock_m1_result_unavailable, mock_data_m09):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db"
    }
    
    def make_mock(content):
        m = MagicMock()
        m.message.content = content
        c = MagicMock()
        c.message = m.message
        ret = MagicMock()
        ret.choices = [c]
        return ret
        
    mock_llm.side_effect = [
        make_mock("Based on a comprehensive analysis... our investment stance is: ENHANCED_DD.\n\nRisk Assessment Agent data was unavailable for this run... Data Integrity Disclosure..."), # > 100 chars
        make_mock(json.dumps([])) # Validation
    ]
    
    module = RecommendationModule("AAPL", mock_m1_result_unavailable, **mock_data_m09)
    result = module.run()
    
    # EVEN THOUGH DATA IS UNAVAILABLE, THIS MODULE NEVER SKIPS
    assert result.status == "COMPLETE" 
    assert result.fallback_used is False
    
    # PROVE PYTHON FORCED THE STANCE
    assert result.facts_block_payload["investment_stance"] == "ENHANCED_DD"
    assert "Risk Assessment Agent data was unavailable" in result.facts_block_payload["investment_stance_reason"]
    
    assert mock_llm.call_count == 2
