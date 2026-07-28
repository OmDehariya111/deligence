import pytest
from pathlib import Path
from agents.ingestion.phase3_user_file import run_phase3

def test_run_phase3_no_file(tmp_path):
    paths = {
        "AUDIT_LOG_PATH": tmp_path / "audit.jsonl",
        "CHROMADB_DIR_PATH": tmp_path / "chroma"
    }
    # Should skip
    run_phase3("AAPL", "AAPL_RUN1", paths, None)
    
    audit_text = paths["AUDIT_LOG_PATH"].read_text()
    assert "No user file provided. Skipped." in audit_text

def test_run_phase3_with_txt(tmp_path):
    paths = {
        "AUDIT_LOG_PATH": tmp_path / "audit.jsonl",
        "CHROMADB_DIR_PATH": tmp_path / "chroma"
    }
    
    txt_file = tmp_path / "research.txt"
    txt_file.write_text("AAPL is a great company with strong iPhone sales. We rate it a BUY.", encoding="utf-8")
    
    run_phase3("AAPL", "AAPL_RUN1", paths, txt_file)
    
    import chromadb
    client = chromadb.PersistentClient(path=str(paths["CHROMADB_DIR_PATH"]))
    collection = client.get_collection("aapl-run1-filings")
    results = collection.get()
    
    assert len(results["ids"]) > 0
    meta = results["metadatas"][0]
    assert meta["ticker"] == "AAPL"
    assert meta["priority"] == "HIGH"
    assert meta["source"] == "user_upload"
    assert meta["filename"] == "research.txt"
    assert meta["filing_type"] == "USER_PROVIDED"
