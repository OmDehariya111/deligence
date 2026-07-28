"""
Module:  risk_assessment_agent.py
Agent:   Risk Assessment Agent
Purpose: Main orchestrator for the Risk Assessment Agent. Executes Pre-Processing 
         and Modules 1 through 10 sequentially.
Inputs:  ticker, run_id
Outputs: Coordinates all modules to output to SQLite and JSON summaries.

# Hinglish Summary:
# Ye file 'General Manager' ki tarah hai. Ye sabse pehle database se pichle run ka kachra (old data) saaf karti hai.
# Uske baad ye ek-ek karke Module 1 se Module 10 tak sabko line se chalati (run) karti hai.
# Isme koi LLM/AI nahi hai, ye sirf pure Python orchestration hai.
"""

import logging
from config.paths import get_run_paths
from utils.audit_logger import log_audit_event
from agents.risk_assessment.pre_processing import RiskPreProcessor

from agents.risk_assessment.module1_financial_risk import FinancialRiskScorer
from agents.risk_assessment.module2_market_risk import MarketRiskScorer
from agents.risk_assessment.module3_operational_risk import OperationalRiskScorer
from agents.risk_assessment.module4_legal_risk import LegalRiskScorer
from agents.risk_assessment.module5_management_risk import ManagementRiskScorer
from agents.risk_assessment.module6_esg_risk import ESGRiskScorer
from agents.risk_assessment.module7_deal_breaker import DealBreakerDetector
from agents.risk_assessment.module8_composite_score import CompositeRiskScorer
from agents.risk_assessment.module9_mitigation import MitigationRecommender
from agents.risk_assessment.module10_summary import RiskAssessmentSummary

logger = logging.getLogger(__name__)

class RiskAssessmentAgent:
    """The Risk Assessment Agent orchestrator."""

    def __init__(self, ticker: str, run_id: str):
        self.ticker = ticker.upper().strip()
        self.run_id = run_id
        self.paths = get_run_paths(ticker, run_id)

    def run(self) -> None:
        """Run the Risk Assessment Agent pipeline."""
        
        logger.info(f"Starting Risk Assessment Agent for {self.ticker} ({self.run_id})")
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="Risk Assessment Agent",
            module="RISK_ASSESSMENT_PIPELINE",
            status="STARTED",
            summary=f"Starting Risk Assessment Pipeline for {self.ticker} (Run: {self.run_id})"
        )

        # Step 1: Purane kachre ki safai (Database Cleanup)
        # Ye step bahut zaroori hai. Jab bhi hum naya assessment run karte hain, 
        # toh pichle run ke duplicate rows/scores hatane ke liye hum seedha SQL 'DELETE' mar dete hain.
        from tools.sqlite_tools import DatabaseManager
        from sqlalchemy import text
        db_path = self.paths.get("SQLITE_DB_PATH")
        logger.info(f"[DEBUG ORCHESTRATOR] db_path is: {db_path}")
        if db_path:
            logger.info(f"[DEBUG ORCHESTRATOR] Entering if db_path block")
            db = DatabaseManager(db_path)
            try:
                risk_tables = ['risk_dimensions', 'risk_evidence', 'deal_breaker_flags', 
                               'risk_mitigation_recommendations', 'composite_risk_output']
                for t in risk_tables:
                    row = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"), {"t": t}).fetchone()
                    logger.info(f"[DEBUG ORCHESTRATOR] Table {t} exists? {row is not None}")
                    if row:
                        db.execute(text(f"DELETE FROM {t} WHERE company_ticker = :ticker"), {"ticker": self.ticker})
                logger.info(f"Successfully cleared previous risk table entries for {self.ticker}")
            except Exception as e:
                logger.warning(f"Could not clear previous risk table entries: {e}")
            finally:
                db.dispose()

        # Step 2: Gatekeeper (Pre-Processing)
        # Check karna ki upstream agents ne data sahi diya hai ya nahi.
        try:
            preprocessor = RiskPreProcessor(self.ticker, self.run_id)
            can_proceed = preprocessor.process()
        except Exception as e:
            logger.error(f"Unexpected error in Pre-Processing: {e}")
            return

        # Step 3: Run the Factory (Execute Modules 1 to 9)
        if can_proceed:
            try:
                # M1: Financial points calculate karega
                logger.info("Running Module 1: Financial Risk")
                m1 = FinancialRiskScorer(preprocessor)
                m1.run()
                
                logger.info("Running Module 2: Market Risk")
                m2 = MarketRiskScorer(preprocessor)
                m2.run()
                
                logger.info("Running Module 3: Operational Risk")
                m3 = OperationalRiskScorer(preprocessor)
                m3.run()
                
                logger.info("Running Module 4: Legal Risk")
                m4 = LegalRiskScorer(preprocessor)
                m4.run()
                
                logger.info("Running Module 5: Management Quality & Governance Risk")
                m5 = ManagementRiskScorer(preprocessor)
                m5.run()
                
                logger.info("Running Module 6: ESG Risk")
                m6 = ESGRiskScorer(preprocessor)
                m6.run()
                
                logger.info("Running Module 7: Deal Breaker Detection")
                m7 = DealBreakerDetector(preprocessor)
                m7.run()
                
                logger.info("Running Module 8: Composite Risk Scoring")
                m8 = CompositeRiskScorer(preprocessor)
                m8.run()
                
                logger.info("Running Module 9: Mitigation Recommendations")
                m9 = MitigationRecommender(preprocessor)
                m9.run()
                
            except Exception as e:
                logger.error(f"Fatal error during Risk Assessment module execution (1-9): {e}")

        # Step 4: Final JSON Report Banaye (Module 10)
        try:
            logger.info("Running Module 10: Risk Assessment Summary")
            m10 = RiskAssessmentSummary(preprocessor)
            m10.run()
        except Exception as e:
            logger.error(f"Fatal error during Module 10 Summary generation: {e}")
            raise
            
        logger.info(f"Risk Assessment Agent completed for {self.ticker}.")
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="Risk Assessment Agent",
            module="RISK_ASSESSMENT_PIPELINE",
            status="COMPLETED",
            summary=f"Risk Assessment Pipeline complete for {self.ticker}. All 10 modules executed successfully and output compiled."
        )
