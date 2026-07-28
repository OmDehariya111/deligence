"""
Module:  test_module_12.py
Agent:   Memo Generation Agent
Purpose: Test the in-memory python-docx assembly logic.
Inputs:  None
Outputs: None
"""

from unittest.mock import patch

import pytest

from agents.memo_generation.module_12_assembly import DocumentAssemblyModule
from schemas.pydantic_models import (
    MemoDataConfidence,
    MemoDocumentPlan,
    MemoModule1Result,
    MemoModule10Result,
    SectionPlanEntry,
)

@pytest.fixture
def mock_run_id_m12():
    return "AAPL_20260703_190501"

@pytest.fixture
def mock_m1_result_success(mock_run_id_m12):
    return MemoModule1Result(
        run_id=mock_run_id_m12,
        status="COMPLETE",
        template_variant="STANDARD",
        template_sub_flags=[],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", risk_assessment="HIGH", # ALL AVAILABLE
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
def mock_m1_result_unavailable(mock_run_id_m12):
    return MemoModule1Result(
        run_id=mock_run_id_m12,
        status="COMPLETE",
        template_variant="LIMITED_DATA",
        template_sub_flags=["RISK_ASSESSMENT_UNAVAILABLE"],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", risk_assessment="UNAVAILABLE", # UNAVAILABLE
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
def mock_validated_sections():
    return {
        "exec_summary": "Exec summary text.",
        "risk_assessment": "Full risk assessment text.",
        "action_items": "Action items text."
    }

@pytest.fixture
def mock_m10_result(mock_run_id_m12):
    return MemoModule10Result(
        run_id=mock_run_id_m12,
        status="COMPLETE",
        appendix_a_financials="Appx A",
        appendix_b_risk_evidence="Appx B",
        appendix_c_methodology="Appx C",
        appendix_d_anomalies="Appx D"
    )

@patch("agents.memo_generation.module_12_assembly.get_run_paths")
def test_assembly_success(mock_get_paths, tmp_path, mock_m1_result_success, mock_validated_sections, mock_m10_result):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl",
    }
    
    module = DocumentAssemblyModule("AAPL", mock_m1_result_success, {}, {}, mock_validated_sections, mock_m10_result)
    result = module.run()
    
    assert result.status == "COMPLETE"
    doc = result.docx_document
    
    # Check styles got added
    assert "MemoHeading1" in doc.styles
    assert "DisclosureNotice" in doc.styles
    
    # Check content injection
    paragraphs_text = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    paragraphs_text.append(p.text)
    
    assert "Exec summary text." in paragraphs_text
    assert "Full risk assessment text." in paragraphs_text
    assert "Appx A" in paragraphs_text
    assert "Appx D" in paragraphs_text
    
    # Check no disclosure notice for risk
    assert "Not available for this run — Risk Assessment Agent output was unavailable." not in paragraphs_text


@patch("agents.memo_generation.module_12_assembly.get_run_paths")
def test_assembly_unavailable(mock_get_paths, tmp_path, mock_m1_result_unavailable, mock_validated_sections, mock_m10_result):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl",
    }
    
    module = DocumentAssemblyModule("AAPL", mock_m1_result_unavailable, {}, {}, mock_validated_sections, mock_m10_result)
    result = module.run()
    
    assert result.status == "COMPLETE"
    doc = result.docx_document
    
    paragraphs_text = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    paragraphs_text.append(p.text)
    
    # The actual text shouldn't be there
    assert "Full risk assessment text." not in paragraphs_text
    
    # The disclosure notice SHOULD be there
    assert "Not available for this run — Risk Assessment Agent output was unavailable." in paragraphs_text
    assert "IMMEDIATE: Conduct manual risk assessment. Data was unavailable for programmatic assessment." in paragraphs_text
