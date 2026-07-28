"""
Module:  test_module_10.py
Agent:   Memo Generation Agent
Purpose: Test the AppendixModule logic. No LLMs are mocked because none are used.
Inputs:  None
Outputs: None
"""

from unittest.mock import patch

import pandas as pd
import pytest

from agents.memo_generation.module_10_appendix import AppendixModule
from schemas.pydantic_models import (
    MemoDataConfidence,
    MemoDocumentPlan,
    MemoModule1Result,
    SectionPlanEntry,
)

@pytest.fixture
def mock_run_id_m10():
    return "AAPL_20260703_190501"

@pytest.fixture
def mock_m1_result_success(mock_run_id_m10):
    return MemoModule1Result(
        run_id=mock_run_id_m10,
        status="COMPLETE",
        template_variant="STANDARD",
        template_sub_flags=[],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", risk_assessment="HIGH", # ENABLES FULL APPX
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
def mock_m1_result_unavailable(mock_run_id_m10):
    return MemoModule1Result(
        run_id=mock_run_id_m10,
        status="COMPLETE",
        template_variant="LIMITED_DATA",
        template_sub_flags=["RISK_ASSESSMENT_UNAVAILABLE", "MARKET_INTEL_UNAVAILABLE"],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="UNAVAILABLE",
            market_context="UNAVAILABLE", risk_assessment="UNAVAILABLE",
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
def mock_data_m10():
    return {
        "memo_data": {
            "ingestion": {"company_identity": {"company_name": "Apple Inc."}},
            "analysis": {
                "data_limitations": {"missing_fields": ["R&D Expense"]}
            }
        },
        "db_tables": {
            "financial_data": pd.DataFrame([
                {"fiscal_year": 2024, "revenue": 383285, "gross_profit": 170000, "operating_income": 115000, "net_income": 96995, "eps_diluted": 6.42, "total_assets": 352583, "total_liabilities": 290437, "total_equity": 62146, "operating_cash_flow": 110543, "investing_cash_flow": -8234, "financing_cash_flow": -103456}
            ]),
            "risk_evidence": pd.DataFrame([
                {"dimension": "Legal", "evidence_type": "Lawsuit", "severity": "CRITICAL", "evidence_text": "DOJ suit", "evidence_source": "WSJ"}
            ]),
            "anomaly_flags": pd.DataFrame([
                {"rule_id": "M-SCORE", "severity_level": 3, "severity": "HIGH", "description": "Manipulation risk", "fiscal_year": "2024"}
            ])
        }
    }

@patch("agents.memo_generation.module_10_appendix.get_run_paths")
def test_appendix_success(mock_get_paths, tmp_path, mock_m1_result_success, mock_data_m10):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl"
    }
    
    module = AppendixModule("AAPL", mock_m1_result_success, **mock_data_m10)
    result = module.run()
    
    assert result.status == "COMPLETE"
    
    # Appx A
    assert "Revenue" in result.appendix_a_financials
    assert "383,285" in result.appendix_a_financials
    
    # Appx B
    assert "DOJ suit" in result.appendix_b_risk_evidence
    
    # Appx C
    assert "Market Prices:" in result.appendix_c_methodology
    assert "Risk Assessment Agent output was unavailable" not in result.appendix_c_methodology
    assert "Missing Fields: R&D Expense" in result.appendix_c_methodology
    
    # Appx D
    assert "Manipulation risk" in result.appendix_d_anomalies

@patch("agents.memo_generation.module_10_appendix.get_run_paths")
def test_appendix_unavailable(mock_get_paths, tmp_path, mock_m1_result_unavailable, mock_data_m10):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl"
    }
    
    module = AppendixModule("AAPL", mock_m1_result_unavailable, **mock_data_m10)
    result = module.run()
    
    assert result.status == "COMPLETE"
    
    # Appx B should be disabled
    assert "Not applicable for this run" in result.appendix_b_risk_evidence
    assert "DOJ suit" not in result.appendix_b_risk_evidence
    
    # Appx C should have injected warnings
    assert "Not available this run — see Data Limitations below." in result.appendix_c_methodology
    assert "Market Intelligence Agent output was unavailable for this run." in result.appendix_c_methodology
    assert "Risk Assessment Agent output was unavailable for this run." in result.appendix_c_methodology
