"""
Module:  llm_utils.py
Agent:   Shared (all agents)
Purpose: Utilities for interacting with LLM outputs reliably.
"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

def parse_llm_json_response(response_text: str, default: Any = None) -> Any:
    """
    Safely parse JSON from an LLM response, stripping markdown fences.
    
    Args:
        response_text: The raw string from the LLM.
        default: The fallback value if parsing fails.
        
    Returns:
        The parsed Python object (dict, list, etc.) or the default value.
    """
    if not response_text:
        return default
        
    text = response_text.strip()
    
    # Strip markdown code blocks
    if text.startswith("```json"):
        text = text[len("```json"):]
    elif text.startswith("```"):
        text = text[len("```"):]
        
    if text.endswith("```"):
        text = text[:-len("```")]
        
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}. Raw text snippet: {text[:100]}...")
        return default
