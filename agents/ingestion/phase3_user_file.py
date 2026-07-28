"""Phase 3: Optional User File Processing."""
# Ye file Ingestion Agent ka 3rd phase hai jiska primary goal user dwara provide ki gayi 
# koi private/custom file (jaise PDF, TXT) ko ingest karna hai. Ye completely OPTIONAL phase hai.
# Agar user file deta hai toh ye use padh kar high priority vector chunks me tod kar ChromaDB me daal deta hai.

import logging
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from utils.text_processing import extract_text_from_file, chunk_text
from utils.audit_logger import log_audit_event
from schemas.pydantic_models import ChromaChunkMetadata

logger = logging.getLogger(__name__)

# BUG FIX: Return type ko `None` se badal kar `int` kar diya gaya hai, taaki ye count 
# return kare ki user file me se kitne chunks bane, aur wo count aage JSON summary me dikhe.
def run_phase3(ticker: str, run_id: str, paths: dict[str, Path], user_file_path: Path | None) -> int:
    """Run Phase 3 optional user file processing."""
    ticker = ticker.upper().strip()
    
    log_audit_event(
        paths["AUDIT_LOG_PATH"],
        agent="IngestionAgent",
        module="PHASE_3_USER_FILE",
        status="STARTED",
        summary=f"Beginning user file processing for {ticker}"
    )

    # 1. OPTIONAL CHECK: Agar user ne koi file upload nahi ki (None hai) ya file physically exist nahi karti,
    # Toh system simply "SKIPPED" bol kar aage badh jayega, bina kisi error ke. Ye ensure karta hai
    # ki bina user file ke bhi baaki ka agent pipeline flawlessly chalega!
    if user_file_path is None or not user_file_path.exists():
        log_audit_event(
            paths["AUDIT_LOG_PATH"],
            agent="IngestionAgent",
            module="PHASE_3_USER_FILE",
            status="COMPLETED",
            summary="No user file provided. Skipped."
        )
        return 0
        
    try:
        # 2. Extract Text: utils.text_processing ki madad se hum file (.pdf ya .txt) ke andar se raw text nikalte hain.
        raw_text = extract_text_from_file(user_file_path)
        if not raw_text:
            raise ValueError(f"Extracted empty text from {user_file_path}")
            
        # 3. Chunking: Lamba PDF poora ek baar me AI nahi padh sakta, toh ise 400-word chunks me todte hain (100 word overlap ke sath).
        chunks = chunk_text(raw_text, chunk_size=400, overlap=100)
        
        # 4. Vector Database Setup: Phase 2 me banayi hui same ChromaDB directory aur collection me hi add karna hai.
        chroma_dir = paths["CHROMADB_DIR_PATH"]
        chroma_dir.mkdir(parents=True, exist_ok=True)
        
        client = chromadb.PersistentClient(path=str(chroma_dir))
        emb_fn = DefaultEmbeddingFunction()
        
        collection_name = f"{run_id.lower().replace('_', '-')}-filings"
        collection_name = collection_name[:63]
        
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=emb_fn
        )
        
        ids = []
        metadatas = []
        documents = []
        
        upload_date = datetime.now(timezone.utc).isoformat()
        
        # 5. Adding Metadata & Embedding: Har chunk pe special label lagaya jaa raha hai (jaise priority="HIGH").
        # Ye priority tag analysis agent ko ye indicate karta hai ki agar uske query ka answer SEC reports (normal) me aur
        # User ki PDF (HIGH) dono me hai, toh User file wale data ko zyada importance deni hai.
        for idx, c_text in enumerate(chunks):
            doc_id = f"{ticker}_USER_{user_file_path.name}_chunk_{idx}"
            meta = ChromaChunkMetadata(
                ticker=ticker,
                company_name="UNKNOWN",
                filing_type="USER_PROVIDED",
                chunk_index=idx,
                total_chunks=len(chunks),
                word_count=len(c_text.split()),
                source="user_upload",
                filename=user_file_path.name,
                priority="HIGH",
                upload_date=upload_date
            ).model_dump(exclude_none=True)
            
            ids.append(doc_id)
            metadatas.append(meta)
            documents.append(c_text)
            
        if chunks:
            collection.add(documents=documents, metadatas=metadatas, ids=ids)
            
        log_audit_event(
            paths["AUDIT_LOG_PATH"],
            agent="IngestionAgent",
            module="PHASE_3_USER_FILE",
            status="COMPLETED",
            summary=f"Processed user file '{user_file_path.name}': {len(chunks)} chunks with HIGH priority."
        )
        
        # BUG FIX: Ab ye successfully return kar raha hai kitne chunks bane, taaki ingestion_summary json report sahi update ho.
        return len(chunks)
        
    except Exception as e:
        log_audit_event(
            paths["AUDIT_LOG_PATH"],
            agent="IngestionAgent",
            module="PHASE_3_USER_FILE",
            status="FAILED",
            summary=f"Error processing user file: {e}"
        )
        raise e
