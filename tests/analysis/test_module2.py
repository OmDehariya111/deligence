import pytest
from agents.analysis.module2_trend_analysis import TrendEngine
from schemas.pydantic_models import RatioRecord

def test_insufficient_data():
    ratios = [
        RatioRecord(ratio_name="gross_margin", fiscal_year=2023, value=40.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="gross_margin", fiscal_year=2024, value=42.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
    ]
    engine = TrendEngine(ratios)
    trends = engine.run()
    
    assert len(trends) == 1
    assert trends[0].trend_direction == "INSUFFICIENT_DATA"
    assert trends[0].trend_confidence == "NONE"
    assert trends[0].data_years == 2


def test_trend_direction_improving_up():
    ratios = [
        RatioRecord(ratio_name="gross_margin", fiscal_year=2020, value=30.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="gross_margin", fiscal_year=2021, value=35.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="gross_margin", fiscal_year=2022, value=40.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="gross_margin", fiscal_year=2023, value=45.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
    ]
    engine = TrendEngine(ratios)
    trends = engine.run()
    
    # gross_margin UP is good -> IMPROVING
    assert trends[0].trend_direction == "IMPROVING"


def test_trend_direction_improving_down():
    ratios = [
        RatioRecord(ratio_name="debt_to_equity", fiscal_year=2020, value=2.5, unit="multiple", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="debt_to_equity", fiscal_year=2021, value=2.0, unit="multiple", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="debt_to_equity", fiscal_year=2022, value=1.5, unit="multiple", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="debt_to_equity", fiscal_year=2023, value=1.0, unit="multiple", formula="", inputs_used={}, status="COMPUTED"),
    ]
    engine = TrendEngine(ratios)
    trends = engine.run()
    
    # debt_to_equity DOWN is good -> IMPROVING
    assert trends[0].trend_direction == "IMPROVING"
    assert trends[0].momentum == "NONE"


def test_trend_stable():
    ratios = [
        RatioRecord(ratio_name="current_ratio", fiscal_year=2020, value=1.5, unit="multiple", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="current_ratio", fiscal_year=2021, value=1.5, unit="multiple", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="current_ratio", fiscal_year=2022, value=1.45, unit="multiple", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="current_ratio", fiscal_year=2023, value=1.55, unit="multiple", formula="", inputs_used={}, status="COMPUTED"),
    ]
    engine = TrendEngine(ratios)
    trends = engine.run()
    
    assert trends[0].trend_direction == "STABLE"


def test_sudden_deterioration_margin():
    ratios = [
        RatioRecord(ratio_name="net_profit_margin", fiscal_year=2022, value=20.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="net_profit_margin", fiscal_year=2023, value=21.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="net_profit_margin", fiscal_year=2024, value=14.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
    ]
    engine = TrendEngine(ratios)
    trends = engine.run()
    
    assert len(trends[0].sudden_changes) == 1
    sc = trends[0].sudden_changes[0]
    assert sc.classification == "SUDDEN_DETERIORATION"
    assert sc.year == 2024
    assert sc.magnitude == 7.0


def test_momentum_accelerating():
    ratios = [
        RatioRecord(ratio_name="revenue_yoy", fiscal_year=2021, value=5.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="revenue_yoy", fiscal_year=2022, value=7.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="revenue_yoy", fiscal_year=2023, value=10.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="revenue_yoy", fiscal_year=2024, value=15.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
    ]
    engine = TrendEngine(ratios)
    trends = engine.run()
    
    assert trends[0].momentum == "ACCELERATING"


def test_sudden_improvement_growth():
    ratios = [
        RatioRecord(ratio_name="net_income_yoy", fiscal_year=2022, value=-5.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="net_income_yoy", fiscal_year=2023, value=2.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
        RatioRecord(ratio_name="net_income_yoy", fiscal_year=2024, value=8.0, unit="percent", formula="", inputs_used={}, status="COMPUTED"),
    ]
    engine = TrendEngine(ratios)
    trends = engine.run()
    
    assert len(trends[0].sudden_changes) == 1
    sc = trends[0].sudden_changes[0]
    assert sc.classification == "SUDDEN_IMPROVEMENT"
    assert sc.year == 2023
