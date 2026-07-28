"""
Module:  test_module_04.py
Agent:   Memo Generation Agent
Purpose: Test the FinancialAnalysisModule logic, tables, and independent fallback pattern.
Inputs:  None
Outputs: None
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from agents.memo_generation.module_04_financial_analysis import FinancialAnalysisModule
from schemas.pydantic_models import (
    MemoDataConfidence,
    MemoDocumentPlan,
    MemoModule1Result,
    SectionPlanEntry,
)

@pytest.fixture
def mock_run_id_m04():
    return "AAPL_20260703_190501"

@pytest.fixture
def mock_m1_result_m04(mock_run_id_m04):
    return MemoModule1Result(
        run_id=mock_run_id_m04,
        status="COMPLETE",
        template_variant="STANDARD",
        template_sub_flags=[],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", risk_assessment="HIGH", recommendation="HIGH"
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
def mock_data_m04():
    return {
        "memo_data": {
            "ingestion": {"company_identity": {"company_name": "Apple Inc.", "cik": "0000320193"}},
            "analysis": {
                "earnings_quality_score": 85,
                "beneish_m_score_latest": {"m_score": -2.5, "verdict": "UNLIKELY_MANIPULATOR"},
                "altman_z_score_latest": {"z_score": 5.1, "verdict": "SAFE_ZONE"},
                "anomaly_flags": {"flags": [{"id": "AF1", "severity": "HIGH", "desc": "Big swing"}]}
            }
        },
        "db_tables": {
            "financial_data": pd.DataFrame([
                {"fiscal_year": 2022, "revenue": 300000, "gross_profit": 150000},
                {"fiscal_year": 2023, "revenue": 383285, "gross_profit": 180000}
            ]),
            "financial_ratios": pd.DataFrame([
                {"fiscal_year": 2023, "ratio_name": "gross_margin", "value": 46.9}
            ])
        },
        "number_lookup": {"revenue_fy2023": 383285},
        "number_lookup_metadata": {}
    }

@patch("agents.memo_generation.module_04_financial_analysis.DatabaseManager")
@patch("agents.memo_generation.module_04_financial_analysis.get_run_paths")
@patch("agents.memo_generation.module_04_financial_analysis.litellm.completion")
def test_financial_analysis_success(mock_llm, mock_get_paths, mock_db, tmp_path, mock_run_id_m04, mock_m1_result_m04, mock_data_m04):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{mock_run_id_m04}.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db"
    }
    
    # 4 narrative calls, 1 validation call
    def make_mock(content):
        m = MagicMock()
        m.message.content = content
        c = MagicMock()
        c.message = m.message
        ret = MagicMock()
        ret.choices = [c]
        return ret
    
    # Needs to be > 50 chars for the narratives
    mock_llm.side_effect = [
        make_mock("Profitability narrative goes here, explaining margins and revenue scale in depth."),
        make_mock("Leverage narrative goes here, explaining debt and solvency risk factors clearly."),
        make_mock("Liquidity narrative goes here, explaining working capital and quick ratio trends."),
        make_mock("Cash flow narrative goes here, explaining free cash flow margins and capex data."),
        make_mock(json.dumps([])) # Validation
    ]
    
    module = FinancialAnalysisModule("AAPL", mock_m1_result_m04, **mock_data_m04)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert len(result.sections_failed_list) == 0
    assert result.validation_mismatches_found == 0
    
    assert "300,000.0" in result.income_statement_table
    assert "383,285.0" in result.income_statement_table
    assert "46.9%" in result.income_statement_table
    assert "BENEISH M-SCORE" in result.fraud_distress_box
    assert "-2.5" in result.fraud_distress_box
    assert "ANOMALY FLAGS DETECTED" in result.anomaly_flags_summary
    assert "1 flags" in result.anomaly_flags_summary

@patch("agents.memo_generation.module_04_financial_analysis.DatabaseManager")
@patch("agents.memo_generation.module_04_financial_analysis.get_run_paths")
@patch("agents.memo_generation.module_04_financial_analysis.litellm.completion")
def test_financial_analysis_partial_failure(mock_llm, mock_get_paths, mock_db, tmp_path, mock_run_id_m04, mock_m1_result_m04, mock_data_m04):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / f"audit_{mock_run_id_m04}.jsonl",
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
        
    # The second call (Leverage) fails 3 times, others succeed
    mock_llm.side_effect = [
        make_mock("Profitability narrative goes here, explaining margins and revenue scale in depth."),
        Exception("API Error"), Exception("API Error"), Exception("API Error"), # Leverage fails
        make_mock("Liquidity narrative goes here, explaining working capital and quick ratio trends."),
        make_mock("Cash flow narrative goes here, explaining free cash flow margins and capex data."),
        make_mock(json.dumps([])) # Validation
    ]
    
    module = FinancialAnalysisModule("AAPL", mock_m1_result_m04, **mock_data_m04)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert len(result.sections_failed_list) == 1
    assert "leverage_narrative" in result.sections_failed_list
    assert "[Leverage narrative could not be generated" in result.leverage_narrative
    # The others should still be generated!
    assert "Profitability narrative" in result.profitability_narrative
    assert "Liquidity narrative" in result.liquidity_narrative
