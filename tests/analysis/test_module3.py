import pytest
from agents.analysis.module3_fraud_distress import FraudDistressEngine

def test_altman_sic_gate():
    # SIC 6021 is commercial banks
    data = {2024: {"total_assets": 1000}}
    engine = FraudDistressEngine(data, "6021", "STANDARD")
    output = engine.run()
    
    assert len(output.altman_scores) == 1
    assert output.altman_scores[0].verdict == "NOT_APPLICABLE"
    assert "not valid for financial-sector companies" in output.altman_scores[0].reason

def test_altman_mfg():
    # SIC 2834 is pharmaceutical (manufacturing)
    data = {2024: {
        "current_assets": 500,
        "current_liabilities": 200,
        "total_assets": 1000,
        "retained_earnings": 300,
        "operating_income": 150,
        "total_liabilities": 400,
        "market_cap": 2000,
        "revenue": 1200
    }}
    engine = FraudDistressEngine(data, "2834", "STANDARD")
    output = engine.run()
    
    assert len(output.altman_scores) == 1
    score = output.altman_scores[0]
    assert score.verdict in ["SAFE_ZONE", "GREY_ZONE", "DISTRESS_ZONE"]
    assert score.version == "Z-Score (Manufacturing)"
    assert score.variables["X5_sales_to_assets"] == 1.2
    assert "Manufacturing formula applied" in score.note

def test_altman_non_mfg():
    # SIC 7372 is software (non-manufacturing)
    data = {2024: {
        "current_assets": 500,
        "current_liabilities": 200,
        "total_assets": 1000,
        "retained_earnings": 300,
        "operating_income": 150,
        "total_liabilities": 400,
        "market_cap": 2000,
        "revenue": 1200
    }}
    engine = FraudDistressEngine(data, "7372", "STANDARD")
    output = engine.run()
    
    assert len(output.altman_scores) == 1
    score = output.altman_scores[0]
    assert score.version == "Z-Prime (Non-manufacturing)"
    assert "X5_sales_to_assets" not in score.variables
    assert "Non-manufacturing formula applied" in score.note

def test_beneish_minimal_depth():
    data = {2024: {"revenue": 1000}}
    engine = FraudDistressEngine(data, "7372", "MINIMAL")
    output = engine.run()
    
    assert len(output.beneish_scores) == 1
    assert output.beneish_scores[0].verdict == "NOT_COMPUTABLE"
    assert "At least 2 consecutive fiscal years required" in output.beneish_scores[0].reason

def test_beneish_computation_with_missing_var():
    # Provide data for 2 years, but leave some variables out to test defaults (1.0 for indices, 0.0 for TATA)
    data = {
        2023: {
            "revenue": 1000,
            "accounts_receivable": 200,
            "total_assets": 5000
        },
        2024: {
            "revenue": 1200,
            "accounts_receivable": 250,
            "total_assets": 5500
        }
    }
    engine = FraudDistressEngine(data, "7372", "STANDARD")
    output = engine.run()
    
    assert len(output.beneish_scores) == 1
    score = output.beneish_scores[0]
    # Missing variables should trigger the note
    assert "Missing variables substituted with research means" in score.note
    assert "GMI" in score.missing_variables
    assert "TATA" in score.missing_variables
    
    # DSRI should be computed
    # 2023 AR/Rev = 200/1000 = 0.2
    # 2024 AR/Rev = 250/1200 = 0.2083
    # DSRI = 0.2083 / 0.2 = 1.0415
    dsri = score.variables["DSRI"].value
    assert round(dsri, 4) == 1.0417

    # Since it substitutes 1.0 for indices and 0.0 for TATA, the score should still compute
    assert score.m_score is not None
    assert score.verdict in ["LIKELY_MANIPULATOR", "GREY_ZONE", "UNLIKELY_MANIPULATOR"]
