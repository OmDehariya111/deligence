"""
Module:  test_module_07.py
Agent:   Memo Generation Agent
Purpose: Test the RiskAssessmentModule logic, graceful degradation, and dynamic dimension LLM generation.
Inputs:  None
Outputs: None
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from agents.memo_generation.module_07_risk_assessment import RiskAssessmentModule
from schemas.pydantic_models import (
    MemoDataConfidence,
    MemoDocumentPlan,
    MemoModule1Result,
    SectionPlanEntry,
)

@pytest.fixture
def mock_run_id_m07():
    return "AAPL_20260703_190501"

@pytest.fixture
def mock_m1_result_success(mock_run_id_m07):
    return MemoModule1Result(
        run_id=mock_run_id_m07,
        status="COMPLETE",
        template_variant="STANDARD",
        template_sub_flags=[],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", risk_assessment="HIGH", # ENABLES MODULE 7
            recommendation="HIGH"
        ),
        section_plan=MemoDocumentPlan(
            executive_summary=SectionPlanEntry(target_words=500, depth="STANDARD"),
            company_overview=SectionPlanEntry(target_words=450, depth="STANDARD"),
            financial_analysis=SectionPlanEntry(target_words=1000, depth="STANDARD"),
            sector_benchmarking=SectionPlanEntry(target_words=500, depth="STANDARD"),
            market_context=SectionPlanEntry(target_words=550, depth="STANDARD"),
            risk_assessment=SectionPlanEntry(target_words=1100, depth="STANDARD"), # STANDARD depth
            action_items=SectionPlanEntry(target_words=300, depth="STANDARD"),
            recommendation=SectionPlanEntry(target_words=600, depth="STANDARD")
        )
    )

@pytest.fixture
def mock_m1_result_unavailable(mock_run_id_m07):
    return MemoModule1Result(
        run_id=mock_run_id_m07,
        status="COMPLETE",
        template_variant="LIMITED_DATA",
        template_sub_flags=["RISK_ASSESSMENT_UNAVAILABLE"],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", risk_assessment="UNAVAILABLE", # DEGRADES MODULE 7
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
def mock_data_m07():
    return {
        "memo_data": {
            "ingestion": {"company_identity": {"company_name": "Apple Inc."}},
            "risk": {
                "COMPOSITE_RISK": {
                    "deal_breaker": True,
                    "composite_score": 68,
                    "final_risk_level": "HIGH",
                    "investment_stance": "REJECT"
                },
                "DEAL_BREAKER_STATUS": {
                    "triggered": ["LITIGATION"],
                    "details": {
                        "LITIGATION": "DOJ sued Apple"
                    },
                    "all_checked": True,
                    "not_triggered": ["GOING_CONCERN", "FRAUD", "INSOLVENCY", "REGULATORY_BAN", "DELISTING", "SANCTIONS", "CRIMINAL"]
                }
            }
        },
        "db_tables": {
            "risk_dimensions": pd.DataFrame([
                {"dimension": "Financial", "risk_level": "LOW", "raw_score": 20, "weight": 20, "top_finding": "Strong balance sheet", "data_completeness": "FULL"},
                {"dimension": "Legal", "risk_level": "CRITICAL", "raw_score": 90, "weight": 20, "top_finding": "Major DOJ suit", "data_completeness": "PARTIAL"}
            ]),
            "risk_evidence": pd.DataFrame([
                {"dimension": "Legal", "severity": "CRITICAL", "evidence_text": "DOJ suit filed.", "evidence_source": "WSJ"}
            ]),
            "top_risks": pd.DataFrame([
                {"dimension": "Legal", "risk_description": "DOJ Lawsuit", "severity": "CRITICAL", "evidence_source": "WSJ"}
            ])
        },
        "number_lookup": {"fake_key": "123"},
        "number_lookup_metadata": {}
    }

@patch("agents.memo_generation.module_07_risk_assessment.DatabaseManager")
@patch("agents.memo_generation.module_07_risk_assessment.get_run_paths")
@patch("agents.memo_generation.module_07_risk_assessment.litellm.completion")
def test_risk_assessment_success(mock_llm, mock_get_paths, mock_db, tmp_path, mock_m1_result_success, mock_data_m07):
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
    
    # Financial is LOW -> LLM generates narrative.
    # Legal is CRITICAL -> LLM generates narrative.
    # Validation runs for both.
    mock_llm.side_effect = [
        make_mock("The financial risk of Apple is low because it maintains a strong balance sheet and has robust liquid cash reserves."), # Financial narrative
        make_mock("The legal risk is very high due to the DOJ lawsuit, which could result in massive fines and structurally alter the company's app store revenue model."), # Legal narrative
        make_mock(json.dumps([])), # Validation for Financial
        make_mock(json.dumps([])) # Validation for Legal
    ]
    
    module = RiskAssessmentModule("AAPL", mock_m1_result_success, **mock_data_m07)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert "DEAL BREAKER IDENTIFIED" in result.deal_breaker_box
    assert "DOJ sued Apple" in result.deal_breaker_box
    assert "◑" in result.scorecard_table # Legal completeness is PARTIAL
    
    assert "Financial" in result.dimension_narratives
    assert "strong balance sheet" in result.dimension_narratives["Financial"]
    
    assert "Legal" in result.dimension_narratives
    assert "DOJ lawsuit" in result.dimension_narratives["Legal"]
    
    assert "DATA_GAP" not in result.top_risks_table
    assert mock_llm.call_count == 4 # 2 narratives, 2 validations

@patch("agents.memo_generation.module_07_risk_assessment.DatabaseManager")
@patch("agents.memo_generation.module_07_risk_assessment.get_run_paths")
@patch("agents.memo_generation.module_07_risk_assessment.litellm.completion")
def test_risk_assessment_unavailable(mock_llm, mock_get_paths, mock_db, tmp_path, mock_m1_result_unavailable, mock_data_m07):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db"
    }
    
    module = RiskAssessmentModule("AAPL", mock_m1_result_unavailable, **mock_data_m07)
    result = module.run()
    
    assert result.status == "SKIPPED_UNAVAILABLE"
    assert result.scorecard_table is None
    assert result.dimension_narratives is None
    assert "RISK ASSESSMENT DATA UNAVAILABLE" in result.data_unavailable_disclosure
    assert mock_llm.call_count == 0  # Should short-circuit completely!
