"""
Module:  test_module_11.py
Agent:   Memo Generation Agent
Purpose: Test the two-pass extraction and validation logic in Module 11.
Inputs:  None
Outputs: None
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.memo_generation.module_11_validation import AntiHallucinationModule

@pytest.fixture
def mock_run_id_m11():
    return "AAPL_20260703_190501"

@pytest.fixture
def mock_draft_sections():
    return {
        "exec_summary": "Apple generated $383.3B in revenue. Growth was nearly twenty percent.",
        "failed_section": "[Section could not be generated]"
    }

@patch("agents.memo_generation.module_11_validation.DatabaseManager")
@patch("agents.memo_generation.module_11_validation.get_run_paths")
@patch("agents.memo_generation.module_11_validation.litellm.completion")
def test_validation_success(mock_llm, mock_get_paths, mock_db, tmp_path, mock_run_id_m11, mock_draft_sections):
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
        
    # Pass 2 LLM Extraction
    pass_2_output = json.dumps([
        {
            "as_written": "nearly twenty percent", 
            "standardized_number": "~20%", 
            "surrounding_sentence": "Growth was nearly twenty percent."
        }
    ])
    
    def llm_side_effect(*args, **kwargs):
        messages = kwargs.get("messages", [])
        prompt = messages[1]["content"] if len(messages) > 1 else messages[0]["content"]
        
        if "Read this section of a financial memo. List every specific numerical claim" in prompt:
            return make_mock(pass_2_output)
        elif "You will be given a list of numerical claims" in prompt:
            # Determine order of claims in the formatted prompt list
            idx_383 = 0 if prompt.find("$383.3B") < prompt.find("nearly twenty percent") else 1
            idx_20 = 1 - idx_383
            results = [
                {
                    "claim_index": idx_383,
                    "number_in_sentence": "$383.3B",
                    "source_lookup_key_found": "rev_key",
                    "source_value": "383,285,000,000",
                    "match_status": "VERIFIED",
                    "corrected_sentence": None
                },
                {
                    "claim_index": idx_20,
                    "number_in_sentence": "nearly twenty percent",
                    "source_lookup_key_found": "growth_key",
                    "source_value": "15%",
                    "match_status": "MISMATCH_CORRECTED",
                    "corrected_sentence": "Growth was fifteen percent."
                }
            ]
            return make_mock(json.dumps({"results": results}))
        return make_mock("{}")
        
    mock_llm.side_effect = llm_side_effect
    
    module = AntiHallucinationModule("AAPL", mock_run_id_m11, mock_draft_sections, {}, {})
    result = module.run()
    
    assert result.status == "COMPLETE"
    assert result.total_claims_checked == 2
    assert result.regex_pass_claims == 1  # $383.3B
    assert result.llm_supplemental_claims == 1  # twenty percent
    assert result.verified == 1
    assert result.mismatch_corrected == 1
    assert "failed_section" in result.sections_excluded_placeholder
    assert result.validation_passed == "PASSED_WITH_CORRECTIONS"
    
    # Check that correction was NOT applied (per user instruction to log only)
    assert "Growth was nearly twenty percent." in result.final_validated_sections["exec_summary"]
