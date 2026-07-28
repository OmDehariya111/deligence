"""
Module:  test_module_06.py
Agent:   Memo Generation Agent
Purpose: Test the MarketIndustryModule logic, graceful degradation, and independent fallbacks.
Inputs:  None
Outputs: None
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from agents.memo_generation.module_06_market_industry import MarketIndustryModule
from schemas.pydantic_models import (
    MemoDataConfidence,
    MemoDocumentPlan,
    MemoModule1Result,
    SectionPlanEntry,
)

@pytest.fixture
def mock_run_id_m06():
    return "AAPL_20260703_190501"

@pytest.fixture
def mock_m1_result_success(mock_run_id_m06):
    return MemoModule1Result(
        run_id=mock_run_id_m06,
        status="COMPLETE",
        template_variant="STANDARD",
        template_sub_flags=[],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="HIGH", # THIS ENABLES MODULE 6
            risk_assessment="HIGH", recommendation="HIGH"
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
def mock_m1_result_unavailable(mock_run_id_m06):
    return MemoModule1Result(
        run_id=mock_run_id_m06,
        status="COMPLETE",
        template_variant="LIMITED_DATA",
        template_sub_flags=["MARKET_INTEL_UNAVAILABLE"],
        tone_profile="CAUTION",
        data_confidence=MemoDataConfidence(
            executive_summary="HIGH", company_overview="HIGH",
            financial_analysis="HIGH", sector_benchmarking="HIGH",
            market_context="UNAVAILABLE", # THIS DEGRADES MODULE 6
            risk_assessment="HIGH", recommendation="HIGH"
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
def mock_data_m06():
    return {
        "memo_data": {
            "ingestion": {"company_identity": {"company_name": "Apple Inc.", "cik": "0000320193"}},
            "market_intel": {
                "NEWS_SENTIMENT": {
                    "article_count": 100,
                    "compound_score": 0.85,
                    "label": "POSITIVE",
                    "sentiment_trend": "IMPROVING",
                    "crisis_flags": [{"type": "LAWSUIT", "headline": "Apple sued", "source": "WSJ", "date": "2026-07-01"}],
                    "key_themes": ["AI Growth", "China Sales"],
                    "llm_narrative": "Overall positive sentiment driven by AI growth."
                }
            }
        },
        "db_tables": {
            "industry_macro": pd.DataFrame([
                {"indicator_name": "US GDP Growth", "current_value": 2.1, "value_1y_ago": 1.9, "value_3y_ago": 2.5, "trend_direction": "UP", "relevance_note": "Drives consumer spending"}
            ])
        },
        "number_lookup": {"gdp_growth": 2.1},
        "number_lookup_metadata": {}
    }

@patch("agents.memo_generation.module_06_market_industry.DatabaseManager")
@patch("agents.memo_generation.module_06_market_industry.get_run_paths")
@patch("agents.memo_generation.module_06_market_industry.litellm.completion")
def test_market_industry_success(mock_llm, mock_get_paths, mock_db, tmp_path, mock_m1_result_success, mock_data_m06):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db"
    }
    
    # 2 narrative calls, 1 validation call
    def make_mock(content):
        m = MagicMock()
        m.message.content = content
        c = MagicMock()
        c.message = m.message
        ret = MagicMock()
        ret.choices = [c]
        return ret
    
    mock_llm.side_effect = [
        make_mock("News sentiment is very positive right now, showing a strong upward trend in all metrics."),
        make_mock("The macro environment is a tailwind due to GDP growth, providing a favorable backdrop for expansion."),
        make_mock(json.dumps([])) # Validation
    ]
    
    module = MarketIndustryModule("AAPL", mock_m1_result_success, **mock_data_m06)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert len(result.sections_failed_list) == 0
    assert result.data_unavailable_disclosure is None
    assert "US GDP Growth" in result.macro_indicators_table
    assert "Apple sued" in result.news_sentiment_summary
    assert "News sentiment is very positive" in result.news_sentiment_narrative
    assert "macro environment is a tailwind" in result.industry_overview_narrative

@patch("agents.memo_generation.module_06_market_industry.DatabaseManager")
@patch("agents.memo_generation.module_06_market_industry.get_run_paths")
@patch("agents.memo_generation.module_06_market_industry.litellm.completion")
def test_market_industry_partial_failure(mock_llm, mock_get_paths, mock_db, tmp_path, mock_m1_result_success, mock_data_m06):
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
        
    # The first call (News) fails 3 times, Industry succeeds, Validation succeeds
    mock_llm.side_effect = [
        Exception("API Error"), Exception("API Error"), Exception("API Error"), # News fails
        make_mock("The macro environment is a tailwind due to GDP growth, providing a favorable backdrop for expansion."),
        make_mock(json.dumps([])) # Validation
    ]
    
    module = MarketIndustryModule("AAPL", mock_m1_result_success, **mock_data_m06)
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert len(result.sections_failed_list) == 1
    assert "news_sentiment_narrative" in result.sections_failed_list
    assert "[News Sentiment narrative could not be generated" in result.news_sentiment_narrative
    assert "macro environment is a tailwind" in result.industry_overview_narrative

@patch("agents.memo_generation.module_06_market_industry.DatabaseManager")
@patch("agents.memo_generation.module_06_market_industry.get_run_paths")
@patch("agents.memo_generation.module_06_market_industry.litellm.completion")
def test_market_industry_unavailable(mock_llm, mock_get_paths, mock_db, tmp_path, mock_m1_result_unavailable, mock_data_m06):
    mock_get_paths.return_value = {
        "AUDIT_LOG_PATH": tmp_path / "logs" / "audit.jsonl",
        "SQLITE_DB_PATH": tmp_path / "deligenx.db"
    }
    
    module = MarketIndustryModule("AAPL", mock_m1_result_unavailable, **mock_data_m06)
    result = module.run()
    
    assert result.status == "SKIPPED_UNAVAILABLE"
    assert result.macro_indicators_table is None
    assert result.news_sentiment_summary is None
    assert result.news_sentiment_narrative is None
    assert "Due to limited data availability" in result.data_unavailable_disclosure
    assert mock_llm.call_count == 0  # Should short-circuit completely!
