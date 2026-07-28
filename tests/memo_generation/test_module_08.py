"""
Module:  test_module_08.py
Agent:   Memo Generation Agent
Purpose: Test the ActionItemsModule logic and graceful degradation.
Inputs:  None
Outputs: None
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from agents.memo_generation.module_08_action_items import ActionItemsModule
from schemas.pydantic_models import (
    MemoDataConfidence,
    MemoDocumentPlan,
    MemoModule1Result,
    SectionPlanEntry,
)

@pytest.fixture
def mock_run_id_m08():
    return "AAPL_20260703_190501"

@pytest.fixture
def mock_m1_result_success(mock_run_id_m08):
    return MemoModule1Result(
        run_id=mock_run_id_m08,
        status="COMPLETE",
        template_variant="STANDARD",
        template_sub_flags=[],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", risk_assessment="HIGH", # ENABLES MODULE 8
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
def mock_m1_result_unavailable(mock_run_id_m08):
    return MemoModule1Result(
        run_id=mock_run_id_m08,
        status="COMPLETE",
        template_variant="LIMITED_DATA",
        template_sub_flags=["RISK_ASSESSMENT_UNAVAILABLE"],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", risk_assessment="UNAVAILABLE", # DEGRADES MODULE 8
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
def mock_data_m08():
    return {
        "memo_data": {
            "ingestion": {"company_identity": {"company_name": "Apple Inc."}},
            "risk": {
                "COMPOSITE_RISK": {
                    "deal_breaker": False
                }
            }
        },
        "db_tables": {
            "mitigation_recs": pd.DataFrame([
                {"company_ticker": "AAPL", "dimension": "Legal", "sub_dimension": "Litigation", "finding_text": "DOJ Suit", "severity": "CRITICAL", "priority": "IMMEDIATE", "condition_type": "PRE_LOI", "recommendation_text": "Hire outside counsel.", "generated_at": "2026-07-03T19:05:01Z"},
                {"company_ticker": "AAPL", "dimension": "Financial", "sub_dimension": "Leverage", "finding_text": "Debt load", "severity": "HIGH", "priority": "NEAR_TERM", "condition_type": "PRE_CLOSE", "recommendation_text": "Refinance.", "generated_at": "2026-07-03T19:05:01Z"}
            ])
        }
    }

@patch("agents.memo_generation.module_08_action_items.get_run_paths")
@patch("agents.memo_generation.module_08_action_items.litellm.completion")
def test_action_items_success(mock_llm, mock_get_paths, tmp_path, mock_m1_result_success, mock_data_m08):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl"
    }
    
    m = MagicMock()
    m.message.content = "There are significant action items to resolve. One immediate task and one near term task. Please monitor closely." # > 30 chars
    c = MagicMock()
    c.message = m.message
    ret = MagicMock()
    ret.choices = [c]
    mock_llm.return_value = ret
    
    module = ActionItemsModule("AAPL", mock_m1_result_success, **mock_data_m08)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.fallback_used is False
    assert result.data_unavailable_disclosure is None
    assert "Hire outside counsel." in result.action_items_tables
    assert "Total: 1 Immediate | 1 Near-Term | 0 Monitor" in result.action_items_tables
    assert "significant action items" in result.intro_narrative
    assert mock_llm.call_count == 1

@patch("agents.memo_generation.module_08_action_items.get_run_paths")
@patch("agents.memo_generation.module_08_action_items.litellm.completion")
def test_action_items_unavailable(mock_llm, mock_get_paths, tmp_path, mock_m1_result_unavailable, mock_data_m08):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl"
    }
    
    module = ActionItemsModule("AAPL", mock_m1_result_unavailable, **mock_data_m08)
    result = module.run()
    
    assert result.status == "SKIPPED_UNAVAILABLE"
    assert result.action_items_tables is None
    assert result.intro_narrative is None
    assert "Commission a full six-dimension risk assessment" in result.data_unavailable_disclosure
    assert mock_llm.call_count == 0  # Should short-circuit completely!
