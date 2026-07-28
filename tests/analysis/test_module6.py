import pytest
from agents.analysis.module6_qoe_summary import QOESummaryEngine
from schemas.pydantic_models import (
    RatioRecord, RatioTrend, FraudDistressOutput, AnomalyOutput, BenchmarkOutput,
    BeneishScore, AltmanScore, AnomalyFlag, BenchmarkMetric
)

def test_qoe_score_deductions():
    # Setup mock inputs
    ratios = []
    trends = [
        RatioTrend(
            ratio_name="Revenue Growth YoY",
            trend_direction="DECLINING",
            trend_confidence="HIGH",
            momentum="DECELERATING",
            sudden_changes=[],
            average_value=1.0,
            std_deviation=0.1,
            year_values={"2023": 2.0, "2024": 1.0},
            linear_slope=-1.0,
            data_years=2
        ),
        RatioTrend(
            ratio_name="FCF/Net Income",
            trend_direction="STABLE",
            trend_confidence="HIGH",
            momentum="STABLE",
            sudden_changes=[],
            average_value=0.5,
            std_deviation=0.1,
            year_values={"2022": 0.5, "2023": 0.5, "2024": 0.5},
            linear_slope=0.0,
            data_years=3
        )
    ]
    
    fraud = FraudDistressOutput(
        beneish_scores=[BeneishScore(verdict="LIKELY_MANIPULATOR", individual_flags=[], missing_variables=[])],
        altman_scores=[AltmanScore(verdict="DISTRESS_ZONE")]
    )
    
    anomaly = AnomalyOutput(
        total_flags=2,
        critical=1, high=0, medium=1, low=0,
        rules_skipped_missing_data=[],
        flags=[
            AnomalyFlag(flag_id="AF-001", severity="CRITICAL", category="A", title="Crit", description="desc", supporting_data={}),
            AnomalyFlag(flag_id="AF-002", severity="MEDIUM", category="A", title="Med", description="desc", supporting_data={})
        ]
    )
    
    ingestion = {
        "missing_critical_fields": [{"field": "interest_expense"}, {"field": "unknown_field"}]
    }
    
    module_statuses = {
        "MODULE_2_TREND_ANALYSIS": "COMPLETE"
    }

    engine = QOESummaryEngine(
        ticker="TEST",
        company_name="Test Corp",
        run_id="test_run",
        n_years=5,
        data_depth_mode="FULL",
        ingestion_summary=ingestion,
        ratios=ratios,
        trends=trends,
        fraud=fraud,
        anomaly=anomaly,
        benchmark=None,
        module_statuses=module_statuses
    )
    
    output = engine.run()
    
    # Score calculation:
    # Base: 100
    # Beneish LIKELY_MANIPULATOR: -25
    # Altman DISTRESS_ZONE: -20
    # Anomaly CRITICAL: -15
    # Anomaly MEDIUM: -5
    # Trend Rev DECLINING: -5
    # Trend FCF < 0.8 for 3+ years: -5
    # Missing interest_expense: -3
    # Missing unknown_field: -1
    # Total deductions: 25+20+15+5+5+5+3+1 = 79
    # Final Score: 100 - 79 = 21
    
    assert output.earnings_quality_score == 21
    assert output.earnings_quality_label == "VERY POOR"
    
    # Check top concerns sorting
    assert len(output.top_concerns) <= 5
    # The CRITICAL anomaly (100) and DISTRESS Altman (100) and MANIPULATOR Beneish (100) should be at the top.

def test_qoe_altman_not_applicable():
    fraud = FraudDistressOutput(
        beneish_scores=[],
        altman_scores=[AltmanScore(verdict="NOT_APPLICABLE")]
    )
    engine = QOESummaryEngine(
        ticker="TEST", company_name="Test Corp", run_id="test_run", n_years=5, data_depth_mode="FULL",
        ingestion_summary={}, ratios=[], trends=[], fraud=fraud, anomaly=None, benchmark=None, module_statuses={}
    )
    output = engine.run()
    # No deductions for NOT_APPLICABLE
    assert output.earnings_quality_score == 100

def test_qoe_missing_module_skipped():
    # If module 2 is skipped, trend deductions should not apply
    trends = [
        RatioTrend(
            ratio_name="Revenue Growth YoY",
            trend_direction="DECLINING",
            trend_confidence="HIGH",
            momentum="DECELERATING",
            sudden_changes=[],
            average_value=1.0,
            std_deviation=0.1,
            year_values={"2023": 2.0, "2024": 1.0},
            linear_slope=-1.0,
            data_years=2
        )
    ]
    module_statuses = {
        "MODULE_2_TREND_ANALYSIS": "SKIPPED"
    }
    engine = QOESummaryEngine(
        ticker="TEST", company_name="Test Corp", run_id="test_run", n_years=2, data_depth_mode="MINIMAL",
        ingestion_summary={}, ratios=[], trends=trends, fraud=None, anomaly=None, benchmark=None, module_statuses=module_statuses
    )
    output = engine.run()
    assert output.earnings_quality_score == 100
