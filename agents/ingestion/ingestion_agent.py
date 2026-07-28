"""
Module: ingestion_agent.py
Master orchestrator for the Ingestion Agent.
Ye Ingestion Agent ka sabse bada "Boss" ya "Manager" hai. 
Iska kaam khud data process karna nahi hai, balki saare 7 phases ko line-se chalana, errors handle karna, 
aur ek phase ka output dusre phase me properly bhejna hai.
"""
import logging
import time
from pathlib import Path

from config.paths import get_run_paths, ensure_run_dirs
from utils.audit_logger import log_audit_event
from schemas.pydantic_models import IngestionSummaryError
from agents.ingestion import (
    phase1_company_identity,
    phase2_text_processing,
    phase3_user_file,
    phase4_financial_data,
    phase5_validation,
    phase6_normalization,
    phase7_final_output
)

logger = logging.getLogger(__name__)

class IngestionAgent:
    def __init__(self, ticker: str, run_id: str, user_file_path: Path | None = None):
        self.ticker = ticker
        self.run_id = run_id
        self.user_file_path = user_file_path
        self.paths = get_run_paths(ticker, run_id)
        ensure_run_dirs(self.paths)
        
        self.module_status = {
            "phase_1_company_identity": "NOT_STARTED",
            "phase_2_text_processing": "NOT_STARTED",
            "phase_3_user_file": "NOT_STARTED",
            "phase_4_financial_data": "NOT_STARTED",
            "phase_5_validation": "NOT_STARTED",
            "phase_6_normalization": "NOT_STARTED"
        }
        self.errors = []
        self.start_time = time.time()

    def _mark_failed(self, phase_key: str, error: Exception):
        self.module_status[phase_key] = "FAILED"
        self.errors.append(f"{phase_key} failed: {str(error)}")
        logger.error(f"{phase_key} failed for {self.ticker}: {error}", exc_info=True)

    def run(self):
        log_audit_event(
            self.paths["AUDIT_LOG_PATH"],
            agent="IngestionAgent",
            module="INGESTION_PIPELINE",
            status="STARTED",
            summary=f"Starting Ingestion for {self.ticker} (Run: {self.run_id})"
        )
        
        phase1_result = None
        phase4_result = None
        phase5_result = None
        
        try:
            # Phase 1: Company Identity (REQUIRED - Halts if failed)
            try:
                phase1_result = phase1_company_identity.run_phase1(self.ticker, self.run_id, self.paths)
                self.module_status["phase_1_company_identity"] = "COMPLETED"
            except Exception as e:
                self._mark_failed("phase_1_company_identity", e)
                raise
                
            # Phase 2: Text Processing (SEMI-REQUIRED - Doesn't halt if failed)
            from schemas.pydantic_models import VectorDatabaseStats
            vector_stats = VectorDatabaseStats(total_chunks=0, chunks_from_10k=0, chunks_from_8k=0, chunks_from_proxy=0, chunks_from_user_file=0, filings_processed={})
            try:
                vector_stats = phase2_text_processing.run_phase2(phase1_result, self.ticker, self.run_id, self.paths)
                self.module_status["phase_2_text_processing"] = "COMPLETED"
            except Exception as e:
                self._mark_failed("phase_2_text_processing", e)
                
            # Phase 3: User File (OPTIONAL - Doesn't halt if failed)
            try:
                if self.user_file_path:
                    user_chunks = phase3_user_file.run_phase3(self.ticker, self.run_id, self.paths, self.user_file_path)
                    if user_chunks:
                        vector_stats.chunks_from_user_file = user_chunks
                        vector_stats.total_chunks += user_chunks
                    self.module_status["phase_3_user_file"] = "COMPLETED"
                else:
                    self.module_status["phase_3_user_file"] = "SKIPPED"
            except Exception as e:
                self._mark_failed("phase_3_user_file", e)

            # Phase 4: Financial Data Collection (REQUIRED - Halts if failed)
            try:
                phase4_result = phase4_financial_data.run_phase4(phase1_result, self.ticker, self.run_id, self.paths)
                self.module_status["phase_4_financial_data"] = "COMPLETED"
            except Exception as e:
                self._mark_failed("phase_4_financial_data", e)
                raise
                
            # Phase 5: Arithmetic Validation (REQUIRED, DEPENDENT ON PHASE 4)
            try:
                phase5_result = phase5_validation.run_phase5(phase4_result, self.paths)
                self.module_status["phase_5_validation"] = "COMPLETED"
            except Exception as e:
                self._mark_failed("phase_5_validation", e)
                raise

            # Phase 6: Normalization (REQUIRED, DEPENDENT ON PHASE 5)
            try:
                phase6_normalization.run_phase6(phase5_result, self.paths)
                self.module_status["phase_6_normalization"] = "COMPLETED"
            except Exception as e:
                self._mark_failed("phase_6_normalization", e)
                raise

        except Exception as fatal_e:
            logger.error(f"Fatal error during Ingestion for {self.ticker}: {fatal_e}")
            # Bug Fix: Fatal error log hone ke saath errors list me bhi jana chahiye, 
            # taaki Phase 7 use 'Unknown error' ki jagah actual reason bata sake!
            self.errors.append(f"Fatal Pipeline Error: {fatal_e}")
            
        # Phase 7: Final Output Package (ALWAYS RUNS)
        try:
            if phase5_result is not None:
                summary = phase7_final_output.run_phase7(
                    self.run_id,
                    phase1_result.company_identity,
                    vector_stats,
                    phase5_result,
                    self.paths,
                    self.module_status,
                    self.start_time,
                    self.errors
                )
            else:
                from datetime import datetime, timezone
                now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                error_summary = IngestionSummaryError(
                    run_id=self.run_id,
                    status="ERROR",
                    reason=str(self.errors[-1]) if self.errors else "Unknown fatal error",
                    ticker_provided=self.ticker,
                    module_status=self.module_status,
                    ingestion_timestamp=now_iso
                )
                self.paths["INGESTION_SUMMARY_PATH"].parent.mkdir(parents=True, exist_ok=True)
                self.paths["INGESTION_SUMMARY_PATH"].write_text(error_summary.model_dump_json(indent=2))
                log_audit_event(
                    self.paths["AUDIT_LOG_PATH"],
                    agent="IngestionAgent",
                    module="INGESTION_PIPELINE",
                    status="FAILED",
                    summary=f"Ingestion failed early. Errors: {self.errors}"
                )
        except Exception as p7_e:
            logger.error(f"Phase 7 also failed! Could not write output package: {p7_e}", exc_info=True)
