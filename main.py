"""
Module: main.py
Entry point for DeligenX project execution.
"""
import argparse
from dotenv import load_dotenv
load_dotenv()

import litellm
import time
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
    retries = 5
    for attempt in range(retries):
        try:
            return original_completion(*args, **kwargs)
        except Exception as e:
            if "rate_limit_exceeded" in str(e) or "RateLimitError" in str(e) or "429" in str(e):
                if attempt < retries - 1:
                    print(f"Rate limit exceeded, retrying in 3 seconds... (Attempt {attempt+1}/{retries})")
                    time.sleep(3)
                    continue
            raise e
litellm.completion = patched_completion

from crew import DeligenXCrew

def main():
    parser = argparse.ArgumentParser(description="Run DeligenX Financial Analysis")
    parser.add_argument("ticker", type=str, help="Ticker symbol of the company (e.g. AAPL)")
    parser.add_argument("--file", type=str, default=None, help="Optional user file path (PDF/TXT) to include in knowledge base.")
    parser.add_argument(
        "--agents", type=str, default="full",
        choices=["one", "three", "four", "full"],
        help="How many agents to run: one (ingestion only), three (ingestion+analysis+MI), "
             "four (ingestion+analysis+MI+risk), full (all 5 including memo generation). Default: full"
    )
    
    args = parser.parse_args()
    
    print("=============================================")
    print(f"DELIGENX ANALYSIS KICKOFF: {args.ticker.upper()}")
    agent_desc = {'one': '1 agent', 'three': '3 agents', 'four': '4 agents', 'full': 'All 5 agents'}.get(args.agents, args.agents)
    print(f"Pipeline Mode: {args.agents.upper()} ({agent_desc})")
    print("=============================================")
    
    deligenx = DeligenXCrew(ticker=args.ticker, user_file_path=args.file)
    
    if args.agents == "one":
        result = deligenx.kickoff_one()
    elif args.agents == "three":
        result = deligenx.kickoff_three()
    elif args.agents == "four":
        result = deligenx.kickoff_four()
    else:
        result = deligenx.kickoff_full()

    print("\n=============================================")
    print(f"DELIGENX PIPELINE COMPLETE: {args.ticker.upper()}")
    print(f"Result: {result}")
    print("=============================================")

if __name__ == "__main__":
    main()

