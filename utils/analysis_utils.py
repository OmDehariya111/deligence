"""
Module:  analysis_utils.py
Agent:   Analysis Agent
Purpose: Helper functions for the Analysis Agent.
Inputs:  Varies
Outputs: Varies
"""

import json
from pathlib import Path


def write_skipped_outputs(paths: dict[str, Path], reason: str) -> None:
    """
    Write placeholder files with SKIPPED status to all downstream 
    analysis output files when pre-processing fails or is blocked.
    """
    skipped_status = {
        "status": "SKIPPED",
        "reason": reason
    }
    
    output_keys = [
        "RATIO_DB_PATH",
        "TREND_ANALYSIS_PATH",
        "FRAUD_DISTRESS_PATH",
        "ANOMALY_FLAGS_PATH",
        "SECTOR_BENCH_JSON"
    ]
    
    for key in output_keys:
        if key in paths:
            file_path = paths[key]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(skipped_status, f, indent=2)
