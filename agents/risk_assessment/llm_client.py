"""
Module:  llm_client.py
Agent:   Risk Assessment Agent
Purpose: Two-tier LLM client using litellm with robust NVIDIA key rotation.
         - Disables litellm/openai internal retries so OUR retry logic is in full control
         - True round-robin across BOTH NVIDIA keys from attempt 0
         - Fast-fail timeout (45s) so failures are detected quickly
         - Exponential backoff with jitter between retries
         NOTE: Chunks are NEVER truncated — full content is always preserved.
         
# Hinglish Summary:
# Ye file Risk Assessment ka "Dimag" (Brain) connect karti hai. Ye Google Cloud Vertex AI
# (Gemini 2.5 Flash & Pro) ke API calls karti hai. Isme retry logic aur exponential backoff
# hai taaki agar kabhi API fail ho, toh ye auto-retry kar sake.
"""

import os
import time
import random
import logging
import re
from typing import Any
import litellm
from dotenv import load_dotenv

load_dotenv()

# -----------------------------------------------------------------------
# CRITICAL: Disable litellm's own internal retry so openai._base_client
# does NOT retry on its own. Our retry loop in _call_llm handles everything.
# Without this, each "attempt" actually takes ~2.5 minutes instead of 45s.
# -----------------------------------------------------------------------
litellm.num_retries = 0

from utils.llm_utils import parse_llm_json_response

logger = logging.getLogger(__name__)

# Default models - Vertex AI Gemini endpoint
DEFAULT_TIER1_MODEL = "vertex_ai/gemini-2.5-flash"
DEFAULT_TIER2_MODEL = "vertex_ai/gemini-2.5-pro"


def _get_nvidia_keys() -> list:
    """Return all configured NVIDIA API keys, stripping whitespace."""
    k1 = os.environ.get("NVIDIA_API_KEY", "").strip()
    k2 = os.environ.get("NVIDIA_API_KEY_2", "").strip()
    return [k for k in [k1, k2] if k]


def _call_llm(model: str, system_prompt: str, user_prompt: str,
              log_callback=None, tier_name: str = "TIER_1_EXTRACTION") -> Any:
    """
    # Internal function: Ye function asli me LiteLLM library ke through LLM ko call karta hai.
    # Isme 'litellm' ki internal retries disabled hain taaki hum apni custom retry loop use kar sakein.
    # Agar error aaye (like timeout ya rate limit), toh ye thoda wait (sleep) karke wapas retry karta hai.
    """
    nvidia_keys = _get_nvidia_keys()
    is_nvidia = (
        model.startswith("openai/meta/")
        or "nvidia" in model
        or "integrate.api.nvidia" in os.getenv("OPENAI_API_BASE", "")
    )

    # Determine expected return type before any call attempt
    is_list_expected = any(p in user_prompt for p in
                           ["Return JSON: [", "Return JSON: [{", "Return JSON:  ["])

    # At least 4 attempts; 2 full cycles across all available keys
    max_attempts = max(4, len(nvidia_keys) * 2)
    response = None

    for attempt in range(max_attempts):
        kwargs = {
            "num_retries": 0,  # also pass per-call to ensure it is applied
        }
        if is_nvidia and nvidia_keys:
            # True round-robin: key_0 -> key_1 -> key_0 -> key_1 ...
            key_idx = attempt % len(nvidia_keys)
            kwargs["api_base"] = "https://integrate.api.nvidia.com/v1"
            kwargs["api_key"] = nvidia_keys[key_idx]
            key_label = f"key_{key_idx + 1}"
        elif model.startswith("groq/") or "groq" in model.lower():
            kwargs["api_key"] = os.environ.get("GROQ_API_KEY", "")
            key_label = "groq"
        else:
            key_label = "default"

        try:
            response = litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt}
                ],
                temperature=0.0,
                timeout=120,  # 120s timeout to allow large contexts to complete
                **kwargs
            )
            break  # success — exit retry loop

        except Exception as e:
            err_str = str(e).lower()
            is_retryable = any(x in err_str for x in [
                "timeout", "429", "rate_limit", "throttled",
                "resource", "internal server error", "500", "503",
                "502", "connection", "timed out", "read timeout"
            ])

            if is_retryable and attempt < max_attempts - 1:
                # Exponential backoff with jitter: 8s, 16s, 32s, 64s (max 90s)
                sleep_sec = min(8 * (2 ** attempt) + random.uniform(0, 3), 90)
                logger.warning(
                    f"LiteLLM call failed ({key_label}, attempt {attempt + 1}/{max_attempts}): "
                    f"{type(e).__name__}. Switching key and retrying in {sleep_sec:.1f}s..."
                )
                time.sleep(sleep_sec)
                continue

            # Non-retryable error or exhausted all retries
            logger.error(f"LLM call permanently failed after {attempt + 1} attempts: {e}")
            if log_callback:
                log_callback({
                    "status": "LLM_CALL_FAILED",
                    "llm_tier": tier_name,
                    "model": model,
                    "error": str(e)
                })
            return [] if is_list_expected else {}

    if response is None:
        return [] if is_list_expected else {}

    # -----------------------------------------------------------------------
    # Increment LLM usage stats on the processor (via frame inspection)
    # -----------------------------------------------------------------------
    try:
        import inspect
        for frame_info in inspect.stack():
            frame = frame_info.frame
            if "self" in frame.f_locals:
                scorer = frame.f_locals["self"]
                if hasattr(scorer, "processor") and scorer.processor:
                    proc = scorer.processor
                    if hasattr(proc, "llm_usage_stats") and proc.llm_usage_stats is not None:
                        proc.llm_usage_stats[tier_name] = proc.llm_usage_stats.get(tier_name, 0) + 1
                        break
    except Exception:
        pass

    content = response.choices[0].message.content

    # Log token usage and cost
    usage = getattr(response, "usage", None)
    input_tokens  = usage.prompt_tokens     if usage else 0
    output_tokens = usage.completion_tokens if usage else 0
    try:
        cost = litellm.completion_cost(completion_response=response)
    except Exception:
        cost = 0.0

    if log_callback:
        log_callback({
            "status": "LLM_CALL",
            "llm_tier": tier_name,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": cost,
        })

    # -----------------------------------------------------------------------
    # Parse JSON from response
    # -----------------------------------------------------------------------
    text_to_parse = content.strip()
    code_block = re.search(r"```(?:json)?\s*(.*?)\s*```", text_to_parse, re.DOTALL)
    if code_block:
        text_to_parse = code_block.group(1).strip()

    # Extract first valid brace/bracket structure by matching balanced brackets
    first_brace = text_to_parse.find("{")
    first_bracket = text_to_parse.find("[")
    if first_brace != -1 or first_bracket != -1:
        start_idx = -1
        start_char = ""
        end_char = ""
        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            start_idx = first_brace
            start_char = "{"
            end_char = "}"
        else:
            start_idx = first_bracket
            start_char = "["
            end_char = "]"
            
        depth = 0
        in_string = False
        escape = False
        json_extracted = ""
        for i in range(start_idx, len(text_to_parse)):
            c = text_to_parse[i]
            if in_string:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    in_string = False
            else:
                if c == '"':
                    in_string = True
                elif c == start_char:
                    depth += 1
                elif c == end_char:
                    depth -= 1
                    if depth == 0:
                        json_extracted = text_to_parse[start_idx:i+1]
                        break
        if json_extracted:
            text_to_parse = json_extracted

    parsed = parse_llm_json_response(text_to_parse, default=None)
    if parsed is None:
        return [] if is_list_expected else {}

    # Normalize types
    if is_list_expected and isinstance(parsed, dict):
        return [parsed]
    elif not is_list_expected and isinstance(parsed, list):
        return parsed[0] if parsed and isinstance(parsed[0], dict) else {}

    return parsed


def tier1_extract_tool(chunks: list, instruction: str, log_callback=None) -> Any:
    """
    # Tier 1 Call: Ye chote/fast model (Flash) ka use karta hai sirf text se data nikalne ke liye.
    """
    model = os.getenv("LLM_MODEL_NAME_TIER1", DEFAULT_TIER1_MODEL)
    context = "\n\n---\n\n".join(chunks)
    system_prompt = (
        "You are an Elite Institutional Financial Data Extraction Algorithm. "
        "Your sole purpose is to parse complex SEC filings and corporate documents with 100% accuracy. "
        "You must NEVER hallucinate or assume data. Extract strictly based on the provided text. "
        "Follow the instructions flawlessly and return ONLY valid JSON. "
        "Do not include any pleasantries or conversational text outside the JSON."
    )
    user_prompt = f"Context:\n{context}\n\nInstruction:\n{instruction}"
    return _call_llm(model, system_prompt, user_prompt, log_callback,
                     tier_name="TIER_1_EXTRACTION")


def tier2_reason_tool(context: str, instruction: str, log_callback=None) -> Any:
    """
    # Tier 2 Call: Ye bade/smart model (Pro) ka use karta hai deep reasoning aur risk analyze karne ke liye.
    """
    model = os.getenv("LLM_MODEL_NAME_TIER2", DEFAULT_TIER2_MODEL)
    system_prompt = (
        "You are the Chief Risk Officer (CRO) at a Top-Tier Wall Street Hedge Fund. "
        "You are responsible for analyzing corporate context to identify high-severity, deal-breaking risks. "
        "Your judgment is institutional-grade, highly nuanced, and extremely conservative. "
        "Read the provided context deeply, apply stringent risk scoring rules, and provide your assessment. "
        "You must output your findings EXACTLY as valid JSON. Do not include markdown codeblocks or conversational text."
    )
    user_prompt = f"Context:\n{context}\n\nInstruction:\n{instruction}"
    return _call_llm(model, system_prompt, user_prompt, log_callback,
                     tier_name="TIER_2_REASONING")
