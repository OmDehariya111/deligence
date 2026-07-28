import pytest
from pathlib import Path
from schemas.pydantic_models import CompanyIdentity, SelectedFilings, FilingRecord
from agents.ingestion.phase1_company_identity import Phase1Result
from agents.ingestion.phase2_text_processing import run_phase2

@pytest.fixture
def mock_phase1_result():
    identity = CompanyIdentity(
        company_name="Apple Inc.",
        cik="0000320193",
        sic_code="3571",
        industry_name="Electronic Computers",
        fiscal_year_end="0930",
        fiscal_year_end_month=9
    )
    selected = SelectedFilings(
        ten_k=[],
        eight_k=[FilingRecord(form="8-K", filing_date="2024-03-15", accession_number="0000320193-24-000078")],
        def_14a=None
    )
    return Phase1Result(company_identity=identity, selected_filings=selected, cik="0000320193")

def test_run_phase2(mock_phase1_result, tmp_path, monkeypatch):
    paths = {
        "AUDIT_LOG_PATH": tmp_path / "audit.jsonl",
        "CHROMADB_DIR_PATH": tmp_path / "chroma"
    }
    
    import agents.ingestion.phase2_text_processing
    def mock_get_filing_document(cik, accession_number):
        import json
        return json.dumps({
            "success": True,
            "accession_number": accession_number,
            "main_document_filename": "test.htm",
            "html_content": "<html><body>Item 5.02 Departure of Directors. Bob left.</body></html>",
            "retrieved_from_cache": False
        })
    monkeypatch.setattr(agents.ingestion.phase2_text_processing, "get_filing_document", mock_get_filing_document)
    
    run_phase2(mock_phase1_result, "AAPL", "AAPL_RUN1", paths)
    
    import chromadb
    client = chromadb.PersistentClient(path=str(paths["CHROMADB_DIR_PATH"]))
    collection = client.get_collection("aapl-run1-filings")
    results = collection.get()
    
    assert len(results["ids"]) > 0
    assert "Bob left" in results["documents"][0]
    meta = results["metadatas"][0]
    assert meta["event_item"] == "5.02"
    assert meta["ticker"] == "AAPL"
