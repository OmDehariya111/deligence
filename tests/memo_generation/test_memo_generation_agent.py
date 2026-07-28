"""
Module:  test_memo_generation_agent.py
Agent:   Memo Generation Agent
Purpose: Integration test for the main orchestrator file.
"""

from unittest.mock import patch, MagicMock
import pytest

from agents.memo_generation.memo_generation_agent import MemoGenerationAgent
from schemas.pydantic_models import MemoPreProcessingResult

@pytest.fixture
def mock_run_id():
    return "AAPL_20260703_190501"

@patch("agents.memo_generation.memo_generation_agent.MemoPreProcessor")
@patch("agents.memo_generation.memo_generation_agent.DocumentPlanModule")
@patch("agents.memo_generation.memo_generation_agent.ExecutiveSummaryModule")
@patch("agents.memo_generation.memo_generation_agent.CompanyOverviewModule")
@patch("agents.memo_generation.memo_generation_agent.FinancialAnalysisModule")
@patch("agents.memo_generation.memo_generation_agent.SectorBenchmarkingModule")
@patch("agents.memo_generation.memo_generation_agent.MarketIndustryModule")
@patch("agents.memo_generation.memo_generation_agent.RiskAssessmentModule")
@patch("agents.memo_generation.memo_generation_agent.ActionItemsModule")
@patch("agents.memo_generation.memo_generation_agent.RecommendationModule")
@patch("agents.memo_generation.memo_generation_agent.AppendixModule")
@patch("agents.memo_generation.memo_generation_agent.AntiHallucinationModule")
@patch("agents.memo_generation.memo_generation_agent.DocumentAssemblyModule")
@patch("agents.memo_generation.memo_generation_agent.ExportModule")
def test_agent_success(
    mock_export, mock_assembly, mock_validation, mock_appendix, mock_recommendation,
    mock_action_items, mock_risk, mock_market, mock_sector, mock_financial,
    mock_company, mock_exec, mock_plan, mock_preproc, mock_run_id
):
    
    # Mock preprocessor success
    preproc_result = MemoPreProcessingResult(
        run_id=mock_run_id,
        status="COMPLETE",
        market_intel_available=True,
        risk_assessment_available=True,
        libreoffice_available=True
    )
    mock_preproc_inst = MagicMock()
    mock_preproc_inst.run.return_value = (preproc_result, {}, {}, {}, {})
    mock_preproc.return_value = mock_preproc_inst
    
    # Mock module results with the attributes that draft_sections building needs
    m2_mock = MagicMock()
    m2_mock.executive_summary_text = "Mock exec summary"
    mock_exec.return_value.run.return_value = m2_mock
    
    m3_mock = MagicMock()
    m3_mock.company_overview_narrative_text = "Mock company overview"
    mock_company.return_value.run.return_value = m3_mock
    
    m4_mock = MagicMock()
    m4_mock.profitability_narrative = "Profitability is strong."
    m4_mock.leverage_narrative = "Leverage is moderate."
    m4_mock.liquidity_narrative = "Liquidity is adequate."
    m4_mock.cash_flow_narrative = "Cash flow is healthy."
    mock_financial.return_value.run.return_value = m4_mock
    
    m5_mock = MagicMock()
    m5_mock.competitive_narrative = "Competitive position is solid."
    mock_sector.return_value.run.return_value = m5_mock
    
    m6_mock = MagicMock()
    m6_mock.news_sentiment_narrative = "Sentiment is positive."
    m6_mock.industry_overview_narrative = "Industry is growing."
    mock_market.return_value.run.return_value = m6_mock
    
    m7_mock = MagicMock()
    m7_mock.dimension_narratives = "Risks are manageable."
    mock_risk.return_value.run.return_value = m7_mock
    
    m8_mock = MagicMock()
    m8_mock.intro_narrative = "Action items listed."
    mock_action_items.return_value.run.return_value = m8_mock
    
    m9_mock = MagicMock()
    m9_mock.recommendation_narrative = "Proceed with caution."
    mock_recommendation.return_value.run.return_value = m9_mock
    
    # Mock validation result with final_validated_sections
    m11_mock = MagicMock()
    m11_mock.final_validated_sections = {
        "exec_summary": "Mock exec summary",
        "company_overview": "Mock company overview",
    }
    mock_validation.return_value.run.return_value = m11_mock
    
    # Mock export result
    mock_export_inst = MagicMock()
    mock_export_inst.run.return_value = MagicMock(
        docx_path="/path/to/memo.docx",
        pdf_path="/path/to/memo.pdf",
        json_cert_path="/path/to/cert.json"
    )
    mock_export.return_value = mock_export_inst
    
    # Run Agent
    agent = MemoGenerationAgent("AAPL", mock_run_id)
    result = agent.run()
    
    assert result is not None
    assert result["docx"] == "/path/to/memo.docx"
    assert result["pdf"] == "/path/to/memo.pdf"
    assert result["json_cert"] == "/path/to/cert.json"
    
    # Ensure all modules were called
    mock_plan.return_value.run.assert_called_once()
    mock_exec.return_value.run.assert_called_once()
    mock_export.return_value.run.assert_called_once()

@patch("agents.memo_generation.memo_generation_agent.MemoPreProcessor")
def test_agent_halt_on_error(mock_preproc, mock_run_id):
    # Mock preprocessor ERROR
    preproc_result = MemoPreProcessingResult(
        run_id=mock_run_id,
        status="ERROR",
        reason="Upstream Ingestion Agent failed.",
        market_intel_available=False,
        risk_assessment_available=False,
        libreoffice_available=False
    )
    mock_preproc_inst = MagicMock()
    mock_preproc_inst.run.return_value = (preproc_result, {}, {}, {}, {})
    mock_preproc.return_value = mock_preproc_inst
    
    agent = MemoGenerationAgent("AAPL", mock_run_id)
    result = agent.run()
    
    # Should halt immediately and return None, without exception
    assert result is None
