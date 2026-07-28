"""Phase 2: Filing Discovery and Text Processing."""
# Ye file Ingestion Agent ka doosra phase hai jiska primary goal SEC filings ka raw data lana,
# use HTML se saaf (clean) karna, chhote-chhote parts (chunks) me todna, 
# aur aage chal kar semantic search karne ke liye ChromaDB (Vector Database) mein save karna hai.

import json
import logging
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from utils.mcp_client import call_mcp_tool_sync
from utils.text_processing import (
    clean_sec_text,
    chunk_text,
    parse_10k_sections,
    parse_proxy_sections,
    parse_10q_sections
)
from utils.audit_logger import log_audit_event
from schemas.pydantic_models import ChromaChunkMetadata, EIGHT_K_EVENT_TYPES, VectorDatabaseStats
from agents.ingestion.phase1_company_identity import Phase1Result

logger = logging.getLogger(__name__)

def run_phase2(phase1_result: Phase1Result, ticker: str, run_id: str, paths: dict[str, Path]) -> VectorDatabaseStats:
    """Run Phase 2 text processing: fetch filings, parse, chunk, embed, store."""
    ticker = ticker.upper().strip()
    
    # Audit log entry - process start
    log_audit_event(
        paths["AUDIT_LOG_PATH"],
        agent="IngestionAgent",
        module="PHASE_2_TEXT_PROCESSING",
        status="STARTED",
        summary=f"Beginning text processing for {ticker}"
    )

    chroma_dir = paths["CHROMADB_DIR_PATH"]
    chroma_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # ChromaDB ek vector database hai jahan hum texts ko AI embeddings me convert karke save karte hain
        # DefaultEmbeddingFunction automatic sentence transformers ka use karta hai text ko numbers (vectors) me badalne ke liye
        client = chromadb.PersistentClient(path=str(chroma_dir))
        emb_fn = DefaultEmbeddingFunction()
        
        # Har naye run ke liye ek unique collection banti hai taki purana data over-mix na ho jaye
        collection_name = f"{run_id.lower().replace('_', '-')}-filings"
        collection_name = collection_name[:63] # ChromaDB naming limits enforce karna
        
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=emb_fn
        )
        
        identity = phase1_result.company_identity
        selected = phase1_result.selected_filings
        cik = identity.cik
        
        # Trackers (Metrics) taaki baad me pta chal sake kitne documents fetch hue, aur unke kitne tukde (chunks) hue
        stats = {"10-K": 0, "10-Q": 0, "8-K": 0, "DEF_14A": 0, "failed": 0}
        chunk_stats = {"10-K": 0, "10-Q": 0, "8-K": 0, "DEF_14A": 0}
        
        # 1. Process 10-K filings (Annual Reports)
        for f_rec in selected.ten_k:
            # MCP server ko call karke actual document fetch karte hain
            doc_json = call_mcp_tool_sync("mcp_servers/sec_edgar_server.py", "get_filing_document", {"cik": cik, "accession_number": f_rec.accession_number})
            if isinstance(doc_json, str):
                doc_data = json.loads(doc_json)
            else:
                doc_data = doc_json
            
            # Agar network failure wagera hua to report karke next doc pe chalte hain
            if not doc_data.get("success"):
                logger.warning(f"Failed to fetch 10-K {f_rec.accession_number}: {doc_data.get('error_reason')}")
                stats["failed"] += 1
                continue
                
            # Document process successful
            stats["10-K"] += 1
                
            # HTML me se specific sections (jaise Item 1A Risk Factors) nikalne ke liye
            sections = parse_10k_sections(doc_data["html_content"])
            fy_str = f_rec.filing_date[:4]
            
            for sec_code, sec_html in sections.items():
                clean_txt = clean_sec_text(sec_html)
                if not clean_txt:
                    continue
                    
                # Text ko bade chunks me todte hain overlap ke saath taki sequence break hone par context waste na ho
                chunks = chunk_text(clean_txt, chunk_size=400, overlap=100)
                if not chunks:
                    continue
                
                ids = []
                metadatas = []
                documents = []
                
                # Chroma DB metadata banane ka process
                for idx, c_text in enumerate(chunks):
                    doc_id = f"{ticker}_10K_{f_rec.accession_number}_{sec_code}_chunk_{idx}"
                    meta = ChromaChunkMetadata(
                        ticker=ticker,
                        company_name=identity.company_name,
                        fiscal_year=fy_str,
                        filing_type="10-K",
                        filing_date=f_rec.filing_date,
                        section_code=sec_code,
                        chunk_index=idx,
                        total_chunks=len(chunks),
                        word_count=len(c_text.split())
                    ).model_dump(exclude_none=True)
                    
                    ids.append(doc_id)
                    metadatas.append(meta)
                    documents.append(c_text)
                    
                # Ek saath saare chunks ko vector DB me push karna (Optimised for speed)
                collection.add(documents=documents, metadatas=metadatas, ids=ids)
                chunk_stats["10-K"] += len(chunks)

        # 1.5. Process 10-Q filings (Quarterly Reports)
        for f_rec in getattr(selected, "ten_q", []):
            doc_json = call_mcp_tool_sync("mcp_servers/sec_edgar_server.py", "get_filing_document", {"cik": cik, "accession_number": f_rec.accession_number})
            if isinstance(doc_json, str):
                doc_data = json.loads(doc_json)
            else:
                doc_data = doc_json
            
            if not doc_data.get("success"):
                logger.warning(f"Failed to fetch 10-Q {f_rec.accession_number}: {doc_data.get('error_reason')}")
                stats["failed"] += 1
                continue
                
            stats["10-Q"] += 1
                
            sections = parse_10q_sections(doc_data["html_content"])
            fy_str = f_rec.filing_date[:4]
            
            for sec_code, sec_html in sections.items():
                clean_txt = clean_sec_text(sec_html)
                if not clean_txt:
                    continue
                    
                chunks = chunk_text(clean_txt, chunk_size=400, overlap=100)
                if not chunks:
                    continue
                
                ids = []
                metadatas = []
                documents = []
                
                for idx, c_text in enumerate(chunks):
                    doc_id = f"{ticker}_10Q_{f_rec.accession_number}_{sec_code}_chunk_{idx}"
                    meta = ChromaChunkMetadata(
                        ticker=ticker,
                        company_name=identity.company_name,
                        fiscal_year=fy_str,
                        filing_type="10-Q",
                        filing_date=f_rec.filing_date,
                        section_code=sec_code,
                        chunk_index=idx,
                        total_chunks=len(chunks),
                        word_count=len(c_text.split())
                    ).model_dump(exclude_none=True)
                    
                    ids.append(doc_id)
                    metadatas.append(meta)
                    documents.append(c_text)
                    
                collection.add(documents=documents, metadatas=metadatas, ids=ids)
                chunk_stats["10-Q"] += len(chunks)

        # 2. Process DEF 14A (Proxy Statements - for board and executive info)
        if selected.def_14a:
            doc_json = call_mcp_tool_sync("mcp_servers/sec_edgar_server.py", "get_proxy_statement", {"cik": cik})
            if isinstance(doc_json, str):
                doc_data = json.loads(doc_json)
            else:
                doc_data = doc_json
            
            if not doc_data.get("found"):
                logger.info("No proxy statement found to parse.")
            else:
                stats["DEF_14A"] += 1
                sections = parse_proxy_sections(doc_data["html_content"])
                for sec_code, sec_html in sections.items():
                    clean_txt = clean_sec_text(sec_html)
                    if not clean_txt:
                        continue
                    chunks = chunk_text(clean_txt, chunk_size=400, overlap=100)
                    
                    ids = []
                    metadatas = []
                    documents = []
                    
                    for idx, c_text in enumerate(chunks):
                        doc_id = f"{ticker}_DEF14A_{doc_data['accession_number']}_{sec_code}_chunk_{idx}"
                        meta = ChromaChunkMetadata(
                            ticker=ticker,
                            company_name=identity.company_name,
                            filing_type="DEF 14A",
                            section_code=sec_code,
                            chunk_index=idx,
                            total_chunks=len(chunks),
                            word_count=len(c_text.split())
                        ).model_dump(exclude_none=True)
                        
                        ids.append(doc_id)
                        metadatas.append(meta)
                        documents.append(c_text)
                            
                    if chunks:
                        collection.add(documents=documents, metadatas=metadatas, ids=ids)
                        chunk_stats["DEF_14A"] += len(chunks)
                            
        # 3. Process 8-K filings (Current/Emergency Events)
        for f_rec in selected.eight_k:
            doc_json = call_mcp_tool_sync("mcp_servers/sec_edgar_server.py", "get_filing_document", {"cik": cik, "accession_number": f_rec.accession_number})
            if isinstance(doc_json, str):
                doc_data = json.loads(doc_json)
            else:
                doc_data = doc_json
            
            if not doc_data.get("success"):
                logger.warning(f"Failed to fetch 8-K {f_rec.accession_number}: {doc_data.get('error_reason')}")
                stats["failed"] += 1
                continue
                
            # BUG FIX: Yahan stats["8-K"] += 1 lagaya gaya hai. Iska matlab hai ki doc fetch hone ke
            # immediately baad humne ek document count kar liya hai. Agar neeche document skip 
            # bhi ho jaye toh process to hua hai. Isse correct 'processed' count maintain hota hai.
            stats["8-K"] += 1
                
            clean_txt = clean_sec_text(doc_data["html_content"])
            if not clean_txt:
                continue
                
            item_match = None
            for key, val in EIGHT_K_EVENT_TYPES.items():
                if f"Item {key}" in clean_txt or f"ITEM {key}" in clean_txt:
                    item_match = (key, val)
                    break
                    
            event_item = item_match[0] if item_match else "8.01"
            event_type = item_match[1] if item_match else "Other Events"
            
            # Risk-relevant 8-K Items filter to prevent db bloat from earnings releases or administrative filings
            if event_item not in ["1.03", "1.05", "2.03", "2.04", "4.01", "4.02", "5.02", "8.01"]:
                logger.info(f"Skipping 8-K {f_rec.accession_number} Item {event_item} ({event_type}) as it is not risk-relevant.")
                continue
            chunks = chunk_text(clean_txt, chunk_size=400, overlap=100)
            if not chunks:
                continue
            
            ids = []
            metadatas = []
            documents = []
            
            for idx, c_text in enumerate(chunks):
                doc_id = f"{ticker}_8K_{f_rec.accession_number}_chunk_{idx}"
                meta = ChromaChunkMetadata(
                    ticker=ticker,
                    company_name=identity.company_name,
                    filing_type="8-K",
                    fiscal_year=f_rec.filing_date[:4],
                    filing_date=f_rec.filing_date,
                    event_item=event_item,
                    event_type=event_type,
                    chunk_index=idx,
                    total_chunks=len(chunks),
                    word_count=len(c_text.split())
                ).model_dump(exclude_none=True)
                
                ids.append(doc_id)
                metadatas.append(meta)
                documents.append(c_text)
                
            collection.add(documents=documents, metadatas=metadatas, ids=ids)
            chunk_stats["8-K"] += len(chunks)
            
        summary_str = f"10-K: {chunk_stats['10-K']} chunks. 10-Q: {chunk_stats['10-Q']} chunks. 8-K: {chunk_stats['8-K']} chunks. DEF-14A: {chunk_stats['DEF_14A']} chunks. {stats['failed']} filing(s) failed and skipped."
        
        # End audit log
        log_audit_event(
            paths["AUDIT_LOG_PATH"],
            agent="IngestionAgent",
            module="PHASE_2_TEXT_PROCESSING",
            status="COMPLETED",
            summary=summary_str
        )
        
        from schemas.pydantic_models import VectorDatabaseStats
        return VectorDatabaseStats(
            total_chunks=chunk_stats['10-K'] + chunk_stats['10-Q'] + chunk_stats['8-K'] + chunk_stats['DEF_14A'],
            chunks_from_10k=chunk_stats['10-K'],
            chunks_from_10q=chunk_stats['10-Q'],
            chunks_from_8k=chunk_stats['8-K'],
            chunks_from_proxy=chunk_stats['DEF_14A'],
            chunks_from_user_file=0,
            filings_processed=stats
        )
        
    except Exception as e:
        log_audit_event(
            paths["AUDIT_LOG_PATH"],
            agent="IngestionAgent",
            module="PHASE_2_TEXT_PROCESSING",
            status="FAILED",
            summary=f"Error in vector storage pipeline: {e}"
        )
        raise e
