import os
import sys
import traceback
from datetime import datetime, timezone
from celery import Celery
from dotenv import load_dotenv
import resend

# Ensure the root directory is in sys.path so 'crew' and 'api' can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")

resend.api_key = RESEND_API_KEY

# Disable tqdm globally to prevent 'LoggingProxy' object has no attribute 'fileno' errors
os.environ["TQDM_DISABLE"] = "1"

# Initialize Celery app
celery_app = Celery(
    "deligenx_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Celery Configurations
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True
)

def send_completion_email(to_email: str, user_name: str, ticker: str, job_id: str):
    """Send an HTML email notification using Resend when a report is completed."""
    if not RESEND_API_KEY or RESEND_API_KEY == "re_123456789":
        print("[EMAIL] Skipping email send. RESEND_API_KEY not configured.")
        return
        
    try:
        html_content = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #000; color: #fff; border-radius: 10px;">
            <h1 style="color: #4CAF50; text-align: center;">Your Report is Ready! 🎉</h1>
            <p style="font-size: 16px;">Hello {user_name or 'there'},</p>
            <p style="font-size: 16px;">Great news! The DeligenX AI Pipeline has successfully completed analyzing <strong>{ticker.upper()}</strong>.</p>
            <p style="font-size: 16px;">You can now view your comprehensive Due Diligence Report on the platform.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="http://deligenx.ai/dashboard" style="background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">View Report</a>
            </div>
            <p style="font-size: 14px; color: #888;">Job ID: {job_id}</p>
            <p style="font-size: 14px; color: #888;">Thank you for using DeligenX - The No.1 Due Diligence Platform.</p>
        </div>
        """
        
        r = resend.Emails.send({
            "from": f"DeligenX AI <{RESEND_FROM_EMAIL}>",
            "to": to_email,
            "subject": f"✅ DeligenX Report Ready: {ticker.upper()}",
            "html": html_content
        })
        print(f"[EMAIL] Successfully sent notification to {to_email}. Resend ID: {r.get('id')}")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email to {to_email}: {e}")

@celery_app.task(name="run_pipeline_task", bind=True)
def run_pipeline_task(self, job_id: str, ticker: str, agents_mode: str, user_file_path: str | None = None):
    """
    Celery background task that runs the DeligenX AI Pipeline.
    Runs in a completely separate process from FastAPI.
    """
    # Import inside the task to avoid circular imports and heavy load on worker startup
    from api.database import SessionLocal
    from api.models import Job, JobStatus
    from crew import DeligenXCrew

    db = SessionLocal()
    
    # FIX: Celery replaces sys.stdout with LoggingProxy which lacks fileno(), crashing tqdm/ChromaDB.
    import sys
    if hasattr(sys.stdout, "__class__") and sys.stdout.__class__.__name__ == "LoggingProxy":
        sys.stdout.__class__.fileno = lambda self: 1
    if hasattr(sys.stderr, "__class__") and sys.stderr.__class__.__name__ == "LoggingProxy":
        sys.stderr.__class__.fileno = lambda self: 2
        
    try:
        # 1. Mark as RUNNING
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.RUNNING
            db.commit()

        print(f"[CELERY WORKER] Starting Pipeline for {ticker} (Job: {job_id})")
        
        # 2. Execute DeligenX pipeline
        crew = DeligenXCrew(ticker=ticker, run_id=job_id, user_file_path=user_file_path)
        
        if agents_mode == "one":
            result = crew.kickoff_one()
        elif agents_mode == "three":
            result = crew.kickoff_three()
        elif agents_mode == "four":
            result = crew.kickoff_four()
        else:
            result = crew.kickoff_full()
            
        print(f"[CELERY WORKER] Pipeline completed for {ticker}.")
        
        # 3. Mark as COMPLETED
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            
            # Send Email Notification
            from api.models import User
            user = db.query(User).filter(User.id == job.user_id).first()
            if user and user.email:
                send_completion_email(user.email, user.full_name or "", ticker, job_id)
            
        return {"status": "success", "job_id": job_id, "ticker": ticker}

    except Exception as e:
        print(f"[CELERY WORKER] Job {job_id} failed: {e}")
        traceback.print_exc()
        
        # Mark as FAILED
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            
        return {"status": "failed", "job_id": job_id, "error": str(e)}
    finally:
        db.close()
