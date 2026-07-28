import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List

from api.database import get_db, engine
from api.models import Job, JobStatus, Base, User
from api.auth_routes import get_current_user
from api.schemas import JobResponse
from api.celery_app import run_pipeline_task
from config.paths import OUTPUT_DIR

# Optional: Ensure tables are created (for dev purposes)
Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/v1")

MAX_CONTEXT_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_CONTEXT_SUFFIXES = {".pdf", ".txt"}
TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")


async def save_context_file(job_id: str, context_file: UploadFile) -> str:
    filename = Path(context_file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if not filename or suffix not in ALLOWED_CONTEXT_SUFFIXES:
        raise HTTPException(status_code=400, detail="Context file must be a PDF or TXT file.")

    upload_dir = OUTPUT_DIR / job_id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"context{suffix}"
    bytes_written = 0

    try:
        with destination.open("wb") as output:
            while chunk := await context_file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > MAX_CONTEXT_FILE_SIZE:
                    output.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail="Context file must be 10 MB or smaller.",
                    )
                output.write(chunk)
    finally:
        await context_file.close()

    if bytes_written == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Context file is empty.")

    return str(destination)


@router.post("/jobs", response_model=JobResponse, status_code=202)
async def start_generation_job(
    ticker: str = Form(...),
    agents: str = Form("full"),
    context_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start a new background job to generate an Investment Memo."""
    from datetime import timedelta

    normalized_ticker = ticker.upper().strip()
    if not TICKER_PATTERN.fullmatch(normalized_ticker):
        raise HTTPException(status_code=400, detail="Enter a valid stock ticker, such as AAPL or BRK.B.")
    if agents not in {"one", "three", "four", "full"}:
        raise HTTPException(status_code=400, detail="Invalid pipeline selection.")

    # Check for recent completed job for the same ticker (within 24 hours)
    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_job = db.query(Job).filter(
        Job.ticker == normalized_ticker,
        Job.status == JobStatus.COMPLETED,
        Job.user_id == current_user.id,
        Job.created_at >= twenty_four_hours_ago
    ).first()

    if recent_job:
        # Return the existing job to bypass deduction and celery task
        return recent_job

    # Create a unique Job ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_id = f"{normalized_ticker}_{timestamp}"

    # Atomic Credit Check & Deduction
    result = db.execute(
        User.__table__.update()
        .where((User.id == current_user.id) & (User.credits >= 1))
        .values(credits=User.credits - 1)
    )
    
    if result.rowcount == 0:
        raise HTTPException(status_code=403, detail="Insufficient credits. Please upgrade your plan.")

    # Create DB Record
    new_job = Job(
        id=job_id,
        ticker=normalized_ticker,
        status=JobStatus.PENDING,
        user_id=current_user.id
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    try:
        user_file_path = await save_context_file(job_id, context_file) if context_file else None
    except Exception:
        db.delete(new_job)
        current_user.credits += 1
        db.commit()
        raise

    # Dispatch task to Celery instead of FastAPI BackgroundTasks
    run_pipeline_task.delay(
        job_id=job_id, 
        ticker=normalized_ticker,
        agents_mode=agents,
        user_file_path=user_file_path,
    )

    return new_job


from fastapi_cache.decorator import cache

@router.get("/jobs", response_model=List[JobResponse])
def get_all_jobs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetch all historical jobs."""
    jobs = db.query(Job).filter(Job.user_id == current_user.id).order_by(Job.created_at.desc()).all()
    return jobs

@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Check the status of an ongoing or completed job."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
    return job

@router.get("/jobs/{job_id}/logs")
def get_job_logs(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Read the audit JSONL file and return the logs for the UI console."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
        
    import os
    import json
    log_path = f"logs/audit_{job_id}.jsonl"
    
    if not os.path.exists(log_path):
        return {"logs": [], "progress": 0, "total_stages": 48}
        
    logs = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        logs.append(json.loads(line))
                    except:
                        pass
    except Exception as e:
        print(f"Error reading logs: {e}")
        
    completed_modules = {
        f"{entry.get('agent', '')}:{entry.get('module', '')}"
        for entry in logs
        if entry.get("status") == "COMPLETED"
    }
    return {
        "logs": logs,
        "progress": min(round((len(completed_modules) / 48) * 100), 99),
        "total_stages": 48,
    }

@router.get("/jobs/{job_id}/memo")
def get_job_memo(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return the final HTML memo and JSON certificate."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
        
    import os
    import json
    
    # We look for the folder output/{job_id}/memo/
    # And grab the HTML file inside
    memo_dir = f"output/{job_id}/memo"
    
    if not os.path.exists(memo_dir):
        raise HTTPException(status_code=404, detail="Memo not ready yet")
        
    html_content = ""
    cert_content = None
    
    for filename in os.listdir(memo_dir):
        if filename.endswith(".html"):
            with open(os.path.join(memo_dir, filename), "r", encoding="utf-8") as f:
                html_content = f.read()
        elif filename.endswith(".json"):
            with open(os.path.join(memo_dir, filename), "r", encoding="utf-8") as f:
                cert_content = json.load(f)
                
    if not html_content:
        raise HTTPException(status_code=404, detail="HTML Memo not found")
        
    return {
        "html": html_content,
        "certificate": cert_content
    }

@router.get("/jobs/{job_id}/pdf")
def get_job_memo_pdf(job_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return the final HTML memo rendered as a true PDF via Playwright."""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
        
    try:
        import os
        import sys
        import subprocess
        import traceback
        
        memo_dir = f"output/{job_id}/memo"
        
        if not os.path.exists(memo_dir):
            raise HTTPException(status_code=404, detail="Memo not ready yet")
            
        html_path = None
        for filename in os.listdir(memo_dir):
            if filename.endswith(".html"):
                html_path = os.path.abspath(os.path.join(memo_dir, filename))
                break
                
        if not html_path:
            raise HTTPException(status_code=404, detail="HTML Memo not found")
            
        pdf_path = os.path.abspath(os.path.join(memo_dir, f"{job_id}_Investment_Memo.pdf"))
        
        # Generate PDF using a separate subprocess to avoid Windows/Uvicorn asyncio loop conflicts (NotImplementedError)
        script = f"""
from playwright.sync_api import sync_playwright
import os
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(r'file:///{html_path.replace(os.sep, "/")}')
    page.wait_for_timeout(1500)
    page.pdf(path=r'{pdf_path.replace(chr(92), "/")}', print_background=True, format="A4")
    browser.close()
"""
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Playwright subprocess failed:\n{result.stderr}")
            
        return FileResponse(pdf_path, media_type="application/pdf", filename=f"{job_id}_Investment_Memo.pdf")
    except Exception as e:
        import traceback
        # Return a 500 error instead of a 200 OK with JSON, so the frontend handles it properly
        raise HTTPException(status_code=500, detail=f"PDF Generation Failed: {str(e)}\\n\\n{traceback.format_exc()}")
