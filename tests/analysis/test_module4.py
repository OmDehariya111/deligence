import pytest
from agents.analysis.module4_anomaly_detection import AnomalyEngine
from schemas.pydantic_models import RatioRecord, RatioTrend, FraudDistressOutput, BeneishScore, BeneishVariable

def test_anomaly_missing_data_skipped():
    # Provide empty inputs
    engine = AnomalyEngine([], [], None, {2024: {}})
    output = engine.run()
    
    assert output.total_flags == 0
    assert len(output.rules_skipped_missing_data) > 0
    # AF-005 should be skipped
    assert any("AF-005" in skip for skip in output.rules_skipped_missing_data)

def test_af005_interest_coverage():
    # IC < 1.0 -> CRITICAL
    ratios = [
        RatioRecord(ratio_name="interest_coverage", fiscal_year=2024, value=0.8, unit="multiple", formula="", inputs_used={}, status="COMPUTED")
    ]
    engine = AnomalyEngine(ratios, [], None, {2024: {}})
    output = engine.run()
    
    assert output.total_flags == 1
    assert output.critical == 1
    assert output.flags[0].flag_id == "AF-005"
    assert output.flags[0].severity == "CRITICAL"

def test_af006_current_ratio():
    # CR < 1.0 -> HIGH
    ratios = [
        RatioRecord(ratio_name="current_ratio", fiscal_year=2024, value=0.9, unit="multiple", formula="", inputs_used={}, status="COMPUTED")
    ]
    engine = AnomalyEngine(ratios, [], None, {2024: {}})
    output = engine.run()
    
    assert output.total_flags == 1
    assert output.high == 1
    assert output.flags[0].flag_id == "AF-006"

def test_af013_receivables_growth():
    # AF-013 triggers if DSRI > 1.31
    beneish_scores = [
        BeneishScore(
            fiscal_year_pair="2023 to 2024",
            verdict="LIKELY_MANIPULATOR",
            variables={
                "DSRI": BeneishVariable(value=1.5, threshold=1.31, flag=True)
            }
        )
    ]
    fraud_output = FraudDistressOutput(beneish_scores=beneish_scores, altman_scores=[])
    
    engine = AnomalyEngine([], [], fraud_output, {2024: {}})
    output = engine.run()
    
    assert output.total_flags == 1
    assert output.medium == 1
    assert output.flags[0].flag_id == "AF-013"

def test_severity_sorting():
    # Trigger AF-005 (CRITICAL), AF-006 (HIGH), AF-007 (MEDIUM)
    ratios = [
        RatioRecord(ratio_name="interest_coverage", fiscal_year=2024, value=0.5, unit="multiple", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="current_ratio", fiscal_year=2024, value=0.5, unit="multiple", formula="", inputs_used={}, status="COMPUTED")
    ]
    raw_data = {
        2024: {
            "goodwill": 400,
            "total_assets": 1000
        }
    }
    
    engine = AnomalyEngine(ratios, [], None, raw_data)
    output = engine.run()
    
    assert output.total_flags == 3
    assert output.critical == 1
    assert output.high == 1
    assert output.medium == 1
    
    # Check sorting CRITICAL -> HIGH -> MEDIUM
    assert output.flags[0].severity == "CRITICAL"
    assert output.flags[1].severity == "HIGH"
    assert output.flags[2].severity == "MEDIUM"
