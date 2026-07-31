"""
Module: crew.py
CrewAI definition for DeligenX project.
"""
from typing import Optional
from pathlib import Path
import litellm

# Monkey patch LiteLLM to strip 'cache_breakpoint' for Groq compatibility
import litellm
original_completion = litellm.completion
def patched_completion(*args, **kwargs):
    if "messages" in kwargs:
        new_msgs = []
        for msg in kwargs["messages"]:
            if isinstance(msg, dict):
                msg_copy = dict(msg)
                msg_copy.pop("cache_breakpoint", None)
                new_msgs.append(msg_copy)
            else:
                new_msgs.append(msg)
        kwargs["messages"] = new_msgs
    return original_completion(*args, **kwargs)
litellm.completion = patched_completion

from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

from agents.ingestion.ingestion_agent import IngestionAgent
from agents.analysis.analysis_agent import AnalysisAgent
from agents.market_intelligence.market_intelligence_agent import MarketIntelligenceAgent
from agents.risk_assessment.risk_assessment_agent import RiskAssessmentAgent
from agents.memo_generation.memo_generation_agent import MemoGenerationAgent
from config.paths import generate_run_id

from crewai import LLM
import os

if os.environ.get("NVIDIA_API_KEY"):
    nvidia_llm = LLM(
        model="openai/meta/llama-3.1-70b-instruct",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.environ.get("NVIDIA_API_KEY", "")
    )
else:
    nvidia_llm = LLM(
        model="groq/llama-3.3-70b-versatile",
        api_key=os.environ.get("GROQ_API_KEY", "")
    )

@tool("run_full_ingestion_pipeline")
def run_full_ingestion_pipeline_tool(ticker: str, run_id: str, user_file_path: Optional[str] = None) -> str:
    """
    Executes the deterministic 7-phase ingestion workflow.
    Must be called exactly once per ticker to populate SQLite and generate IngestionSummary.
    """
    path_obj = Path(user_file_path) if user_file_path else None
    agent = IngestionAgent(ticker=ticker, run_id=run_id, user_file_path=path_obj)
    agent.run()
    
    # We return the JSON status of Phase 1 to see if we crashed immediately
    status = agent.module_status.get("phase_1_company_identity", "FAILED")
    if status == "FAILED":
        return f'{{"status": "ERROR", "reason": "Ingestion Pipeline failed for {ticker}. Check audit logs."}}'
    return f'{{"status": "COMPLETE", "summary": "Ingestion fully successfully for {ticker}."}}'

@tool("run_analysis_pipeline")
def run_analysis_pipeline_tool(ticker: str, run_id: str, ingestion_summary_json: Optional[str] = None) -> str:
    """
    Executes the analysis workflow.
    Expects the JSON output from the ingestion pipeline to be passed into ingestion_summary_json.
    """
    agent = AnalysisAgent(ticker=ticker, run_id=run_id)
    agent.run()
    return f'{{"status": "COMPLETE", "summary": "Analysis completed for {ticker}."}}'

@tool("run_market_intelligence_pipeline")
def run_market_intelligence_pipeline_tool(ticker: str, run_id: str, analysis_summary_json: Optional[str] = None) -> str:
    """Executes the market intelligence workflow.
    Expects the JSON output from the analysis pipeline to be passed into analysis_summary_json.
    """
    agent = MarketIntelligenceAgent(ticker=ticker, run_id=run_id)
    agent.run()
    return f'{{"status": "COMPLETE", "summary": "Market Intelligence completed for {ticker}."}}'

@tool("run_risk_assessment_pipeline")
def run_risk_assessment_pipeline_tool(ticker: str, run_id: str, mi_summary_json: Optional[str] = None) -> str:
    """Executes the risk assessment workflow.
    Expects the JSON output from market intelligence to be passed into mi_summary_json.
    """
    agent = RiskAssessmentAgent(ticker=ticker, run_id=run_id)
    agent.run()
    return f'{{"status": "COMPLETE", "summary": "Risk Assessment completed for {ticker}."}}'

@tool("run_memo_generation_pipeline")
def run_memo_generation_pipeline_tool(ticker: str, run_id: str, risk_summary_json: Optional[str] = None) -> str:
    """Executes the memo generation workflow.
    Expects the JSON output from risk assessment to be passed into risk_summary_json.
    """
    agent = MemoGenerationAgent(ticker=ticker, run_id=run_id)
    agent.run()
    return f'{{"status": "COMPLETE", "summary": "Memo Generation completed for {ticker}."}}'


def on_ingestion_complete(task_output):
    """Callback for when Ingestion task finishes."""
    print("\n--- Ingestion Task Complete ---")

class DeligenXCrew:
    def __init__(self, ticker: str, user_file_path: Optional[str] = None, run_id: Optional[str] = None):
        self.ticker = ticker.upper().strip()
        self.run_id = run_id if run_id else generate_run_id(self.ticker)
        self.user_file_path = user_file_path

    def setup_crew(self) -> Crew:
        user_file_argument = (
            f" and user_file_path='{self.user_file_path}'"
            if self.user_file_path else ""
        )
        # 1. Ingestion Agent
        ingestion_agent = Agent(
            role="Financial Data Ingestion Specialist",
            goal="Given a ticker and run_id, resolve the company's SEC identity, collect 5 years of structured financial data, and build a filing-text vector store.",
            backstory="A meticulous SEC-data specialist who never guesses a number and never silently drops a filing â€” every gap is logged, every source is cited.",
            tools=[run_full_ingestion_pipeline_tool],
            llm=nvidia_llm,
            verbose=False,
            allow_delegation=False,
            max_iter=1
        )
        ingestion_task = Task(
            description=f"For the company '{self.ticker}' with run_id '{self.run_id}', use your ONLY tool passing ticker='{self.ticker}' and run_id='{self.run_id}'{user_file_argument}. Do not omit user_file_path when it is provided.",
            expected_output="A JSON-formatted string returning the final status of the pipeline (e.g. COMPLETE or ERROR).",
            agent=ingestion_agent,
            context=[],
            callback=on_ingestion_complete
        )
        
        # 2. Analysis Agent
        analysis_agent = Agent(
            role="Financial Analysis Engine",
            goal="Process the raw financial data and generate key ratios and anomaly reports.",
            backstory="A specialized financial analysis engine.",
            tools=[run_analysis_pipeline_tool],
            llm=nvidia_llm,
            verbose=False,
            allow_delegation=False,
            max_iter=1
        )
        analysis_task = Task(
            description=f"Execute the analysis pipeline for {self.ticker} with run_id {self.run_id}. The output of the Ingestion Agent is provided in your context. You MUST pass that exact JSON string into the 'ingestion_summary_json' argument of the run_analysis_pipeline tool.",
            expected_output="A JSON-formatted string indicating analysis completion.",
            agent=analysis_agent,
            context=[ingestion_task]
        )
        
        # 3. Market Intelligence Agent
        mi_agent = Agent(
            role="Market Intelligence Specialist",
            goal="Gather and process live market intelligence and competitor analysis.",
            backstory="An expert in market trends and live financial intelligence.",
            tools=[run_market_intelligence_pipeline_tool],
            llm=nvidia_llm,
            verbose=False,
            allow_delegation=False,
            max_iter=1
        )
        mi_task = Task(
            description=f"Execute the market intelligence pipeline for {self.ticker} with run_id {self.run_id}. The output of the Analysis Agent is provided in your context. You MUST pass that exact JSON string into the 'analysis_summary_json' argument of your tool.",
            expected_output="A JSON-formatted string indicating market intelligence completion.",
            agent=mi_agent,
            context=[analysis_task]
        )
        
        # 4. Risk Assessment Agent
        risk_agent = Agent(
            role="Risk Assessment Specialist",
            goal="Identify and quantify potential risks across multiple dimensions.",
            backstory="A conservative risk assessor who looks for any deal-breaking liabilities.",
            tools=[run_risk_assessment_pipeline_tool],
            llm=nvidia_llm,
            verbose=False,
            allow_delegation=False,
            max_iter=1
        )
        risk_task = Task(
            description=f"Execute the risk assessment pipeline for {self.ticker} with run_id {self.run_id}. The output of the Market Intelligence Agent is provided in your context. You MUST pass that exact JSON string into the 'mi_summary_json' argument of your tool.",
            expected_output="A JSON-formatted string indicating risk assessment completion.",
            agent=risk_agent,
            context=[mi_task]
        )
        
        # 5. Memo Generation Agent
        memo_agent = Agent(
            role="Investment Memo Writer",
            goal="Synthesize all previous analyses into a comprehensive investment memo.",
            backstory="A highly articulate financial writer who synthesizes complex data into clear, actionable memos.",
            tools=[run_memo_generation_pipeline_tool],
            llm=nvidia_llm,
            verbose=False,
            allow_delegation=False,
            max_iter=1
        )
        memo_task = Task(
            description=f"Execute the memo generation pipeline for {self.ticker} with run_id {self.run_id}. The output of the Risk Assessment Agent is provided in your context. You MUST pass that exact JSON string into the 'risk_summary_json' argument of your tool.",
            expected_output="A JSON-formatted string indicating memo generation completion.",
            agent=memo_agent,
            context=[risk_task]
        )

        return Crew(
            agents=[ingestion_agent, analysis_agent, mi_agent, risk_agent, memo_agent],
            tasks=[ingestion_task, analysis_task, mi_task, risk_task, memo_task],
            process=Process.sequential,
            verbose=False,
            cache=False
        )

    def kickoff_one(self):
        """Used by the error gate to run only the first task to check its status."""
        crew = self.setup_crew()
        # We can extract the ingestion task and agent
        ingestion_agent = crew.agents[0]
        ingestion_task = crew.tasks[0]
        
        temp_crew = Crew(
            agents=[ingestion_agent],
            tasks=[ingestion_task],
            process=Process.sequential,
            verbose=False,
            cache=False
        )
        return temp_crew.kickoff()
        
    def kickoff_three(self):
        crew = self.setup_crew()
        temp_crew = Crew(
            agents=crew.agents[0:3],
            tasks=crew.tasks[0:3],
            process=Process.sequential,
            verbose=False,
            cache=False
        )
        return temp_crew.kickoff()

    def kickoff_four(self):
        crew = self.setup_crew()
        temp_crew = Crew(
            agents=crew.agents[0:4],
            tasks=crew.tasks[0:4],
            process=Process.sequential,
            verbose=False,
            cache=False
        )
        return temp_crew.kickoff()

    def kickoff_full(self):
        crew = self.setup_crew()
        crew.cache = False
        return crew.kickoff()
