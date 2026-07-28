"""
Module:  market_intelligence_agent.py
Agent:   Market Intelligence Agent
Purpose: Main orchestrator for the Market Intelligence Agent. Executes PRE-PROCESSING 
         and Modules 1 through 8 sequentially per new_market_intelligence_workflow.md.
Inputs:  ticker, run_id
Outputs: Coordinates all modules to output to SQLite and JSON summaries.
"""

import logging
from config.paths import get_run_paths
from agents.market_intelligence.pre_processing import MarketIntelPreProcessor, PreProcessingError
from agents.market_intelligence.module1_named_competitors import NamedCompetitorIdentifier
from agents.market_intelligence.module2_ltm_financials import LTMExtractor
from agents.market_intelligence.module3_live_market_data import LiveMarketDataExtractor
from agents.market_intelligence.module4_comps_valuation import CompsAndValuationGenerator
from agents.market_intelligence.module5_news_sentiment import NewsSentimentExtractor
from agents.market_intelligence.module6_industry_macro import IndustryMacroExtractor
from agents.market_intelligence.module7_market_risk import MarketRiskSignalGenerator
from agents.market_intelligence.module8_mi_summary import MarketIntelligenceSummarizer
from utils.audit_logger import log_audit_event

logger = logging.getLogger(__name__)

class MarketIntelligenceAgent:
    """The Market Intelligence Agent orchestrator."""

    def __init__(self, ticker: str, run_id: str):
        self.ticker = ticker.upper().strip()
        self.run_id = run_id
        self.paths = get_run_paths(ticker, run_id)

    def run(self) -> None:
        """Run the Market Intelligence Agent pipeline."""
        
        logger.info(f"Starting Market Intelligence Agent for {self.ticker} ({self.run_id})")
        
        # Log Pipeline Start with Master Pipeline Naming Rule
        log_audit_event(
            audit_log_path=self.paths["AUDIT_LOG_PATH"],
            agent="MarketIntelligenceAgent",
            module="MARKET_INTELLIGENCE_PIPELINE",
            status="STARTED",
            summary=f"Starting Market Intelligence Pipeline for {self.ticker} (Run: {self.run_id})"
        )

        try:
            # Pre-Processing
            preprocessor = MarketIntelPreProcessor(self.ticker, self.run_id)
            context = preprocessor.run()

            # Execute Modules 1 through 8
            
            # MODULE 1: Named Competitor Identification (REQUIRED)
            logger.info("Running Module 1: Named Competitors")
            m1 = NamedCompetitorIdentifier(context)
            m1.run()
            
            # MODULE 2: LTM Financial Data (SEMI-REQUIRED)
            logger.info("Running Module 2: LTM Financials")
            m2 = LTMExtractor(context)
            m2.run()
            
            # MODULE 3: Live Market Data (SEMI-REQUIRED)
            logger.info("Running Module 3: Live Market Data")
            m3 = LiveMarketDataExtractor(context)
            m3.run()
            
            # MODULE 4: IB Comps Table + Implied Valuation (REQUIRED, degradable)
            logger.info("Running Module 4: Comps & Valuation")
            m4 = CompsAndValuationGenerator(context)
            m4.run()
            
            # MODULE 5: News & Sentiment (OPTIONAL)
            logger.info("Running Module 5: News & Sentiment")
            m5 = NewsSentimentExtractor(context)
            m5.run()
            
            # MODULE 6: Industry & Macro Context (OPTIONAL)
            logger.info("Running Module 6: Industry & Macro")
            m6 = IndustryMacroExtractor(context)
            m6.run()
            
            # MODULE 7: Market Risk Signals Package (REQUIRED, degradable)
            logger.info("Running Module 7: Market Risk Signals")
            m7 = MarketRiskSignalGenerator(context)
            m7.run()
            
            # MODULE 8: Market Intelligence Summary (REQUIRED)
            logger.info("Running Module 8: MI Summary")
            m8 = MarketIntelligenceSummarizer(context)
            m8.run()
            
            # Log Pipeline End with matching Master Pipeline Naming Rule
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="MarketIntelligenceAgent",
                module="MARKET_INTELLIGENCE_PIPELINE",
                status="COMPLETED",
                summary=f"Market intelligence complete for {self.ticker}. All 8 modules compiled."
            )
            logger.info(f"Market Intelligence Agent completed successfully for {self.ticker}.")
            
        except PreProcessingError as e:
            logger.error(f"Market Intelligence aborted during Pre-Processing: {e}")
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="MarketIntelligenceAgent",
                module="MARKET_INTELLIGENCE_PIPELINE",
                status="FAILED",
                summary=f"Pipeline aborted during Pre-Processing: {e}"
            )
            return
        except Exception as e:
            logger.error(f"Fatal error during Market Intelligence execution: {e}")
            log_audit_event(
                audit_log_path=self.paths["AUDIT_LOG_PATH"],
                agent="MarketIntelligenceAgent",
                module="MARKET_INTELLIGENCE_PIPELINE",
                status="FAILED",
                summary=f"Fatal error during execution: {e}"
            )
            raise
