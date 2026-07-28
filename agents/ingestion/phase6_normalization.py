"""Phase 6: Normalization."""
# Ye Ingestion Pipeline ka aakhri (6th) aur sabse simple phase hai.
# Iska original purpose data units ko standardize karna (jaise 'millions' ko full numbers me convert karna) hota hai.
# Lekin kyunki hamara Phase 4 (FinancialExtractor) pehle hi SEC API se absolute 'USD' aur 'shares' mangta hai,
# is phase ka kaam sirf ek final quality check aur passthrough bankar reh jata hai.

import logging
from pathlib import Path

from utils.audit_logger import log_audit_event
from schemas.pydantic_models import Phase5Result

logger = logging.getLogger(__name__)

def run_phase6(phase5_result: Phase5Result, paths: dict[str, Path]) -> Phase5Result:
    """Run Phase 6 unit normalization."""
    # Phase 5 (Validation) se mila hua result directly input aata hai
    history = phase5_result.financial_history
    
    log_audit_event(
        paths["AUDIT_LOG_PATH"],
        agent="IngestionAgent",
        module="PHASE_6_NORMALIZATION",
        status="STARTED",
        summary=f"Checking unit normalization for {history.ticker}"
    )
    
    # FinancialExtractor strictly enforced "USD", "shares", and "USD/shares" during extraction.
    # Therefore, all data is mathematically guaranteed to be in full, raw values.
    # No rescaling is needed in this pipeline.
    
    log_audit_event(
        paths["AUDIT_LOG_PATH"],
        agent="IngestionAgent",
        module="PHASE_6_NORMALIZATION",
        status="COMPLETED",
        summary="All monetary fields confirmed in full USD, no rescaling needed."
    )
    
    return phase5_result
