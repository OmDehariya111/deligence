import pytest
import json
from unittest.mock import patch
from schemas.pydantic_models import RatioRecord
from agents.analysis.module5_sector_benchmark import SectorBenchmarkEngine

def get_mock_tickers():
    return json.dumps({
        "mapping": {
            "0000000001": "3571",
            "0000000002": "3571",
            "0000000003": "3571",
            "0000000004": "1111", # Wrong SIC
        }
    })

def get_mock_frames(tag, unit, period):
    if tag == "Revenues":
        return json.dumps({
            "status": "OK",
            "data": [
                {"cik": 1, "entity_name": "Peer A", "value": 1000},
                {"cik": 2, "entity_name": "Peer B", "value": 2000},
                {"cik": 3, "entity_name": "Peer C", "value": 3000},
                {"cik": 4, "entity_name": "Wrong SIC Peer", "value": 5000},
                {"cik": 999, "entity_name": "AAPL", "value": 10000}, # Target
            ]
        })
    elif tag == "GrossProfit":
        return json.dumps({
            "status": "OK",
            "data": [
                {"cik": 1, "entity_name": "Peer A", "value": 400},  # 40%
                {"cik": 2, "entity_name": "Peer B", "value": 1000}, # 50%
                {"cik": 3, "entity_name": "Peer C", "value": 1800}, # 60%
            ]
        })
    elif tag == "NetIncomeLoss":
        return json.dumps({
            "status": "OK",
            "data": [
                {"cik": 1, "entity_name": "Peer A", "value": 100},  # 10% ROA
                {"cik": 2, "entity_name": "Peer B", "value": 400},  # 20% ROA
                {"cik": 3, "entity_name": "Peer C", "value": 900},  # 30% ROA
            ]
        })
    elif tag == "Assets":
        return json.dumps({
            "status": "OK",
            "data": [
                {"cik": 1, "entity_name": "Peer A", "value": 1000},
                {"cik": 2, "entity_name": "Peer B", "value": 2000},
                {"cik": 3, "entity_name": "Peer C", "value": 3000},
            ]
        })
    return json.dumps({"status": "NO_DATA", "data": []})

def mock_call_mcp_tool_sync(server_script, tool_name, arguments):
    if tool_name == "get_company_tickers" or tool_name == "get_sic_mapping":
        return get_mock_tickers()
    elif tool_name == "get_frames_data":
        return get_mock_frames(arguments.get("tag"), arguments.get("unit"), arguments.get("period"))
    return {}

@patch("agents.analysis.module5_sector_benchmark.call_mcp_tool_sync", side_effect=mock_call_mcp_tool_sync)
def test_sector_benchmark_basic(mock_call_mcp):
    target_ratios = [
        RatioRecord(
            ratio_name="gross_margin",
            fiscal_year=2024,
            value=45.0, # Target GM = 45% (lower than 50% and 60%, higher than 40%. Percentile = 33%)
            unit="%",
            formula="GM",
            inputs_used={},
            status="COMPUTED"
        ),
        RatioRecord(
            ratio_name="roa",
            fiscal_year=2024,
            value=15.0, # Target ROA = 15% (lower than 20% and 30%, higher than 10%. Percentile = 33%)
            unit="%",
            formula="ROA",
            inputs_used={},
            status="COMPUTED"
        )
    ]
    
    engine = SectorBenchmarkEngine(
        ticker="AAPL",
        sic_code="3571",
        industry="Electronic Computers",
        benchmark_year=2024,
        target_ratios=target_ratios
    )
    
    output = engine.run()
    
    # 3 valid peers: CIK 1, 2, 3
    assert output["peer_count"] == 3
    assert len(output["top_peers"]) == 3
    # Top peers should be sorted by revenue descending
    assert output["top_peers"][0]["revenue"] == 3000
    assert output["top_peers"][1]["revenue"] == 2000
    
    # Gross Margin (higher is better)
    # Peers: 40, 50, 60. Median: 50. Mean: 50. Target: 45.
    gm = output["metrics"]["Gross Margin"]
    assert gm["sector_median"] == 50.0
    assert gm["company_percentile"] == 33 # 1 out of 3 peers has < 45%
    assert gm["relative_position"] == "BELOW_AVERAGE"
    
    # ROA (higher is better)
    roa = output["metrics"]["ROA"]
    assert roa["sector_median"] == 20.0
    assert roa["company_percentile"] == 33

@patch("agents.analysis.module5_sector_benchmark.call_mcp_tool_sync")
def test_sector_benchmark_no_data(mock_call_mcp):
    def mock_no_data(server_script, tool_name, arguments):
        if tool_name == "get_company_tickers": return get_mock_tickers()
        return json.dumps({"status": "NO_DATA"})
    mock_call_mcp.side_effect = mock_no_data
    engine = SectorBenchmarkEngine(
        ticker="AAPL", sic_code="3571", industry="Electronic Computers",
        benchmark_year=2024, target_ratios=[]
    )
    output = engine.run()
    assert output["status"] == "FAILED"

@patch("agents.analysis.module5_sector_benchmark.call_mcp_tool_sync")
def test_sector_benchmark_no_peers(mock_call_mcp):
    def mock_no_peers(server_script, tool_name, arguments):
        if tool_name == "get_company_tickers": return get_mock_tickers()
        return json.dumps({"status": "OK", "data": [{"cik": 999, "entity_name": "AAPL", "value": 1000}]})
    mock_call_mcp.side_effect = mock_no_peers
    engine = SectorBenchmarkEngine(
        ticker="AAPL", sic_code="3571", industry="Electronic Computers",
        benchmark_year=2024, target_ratios=[]
    )
    output = engine.run()
    assert output["status"] == "PARTIAL"
    assert output["peer_count"] == 0
