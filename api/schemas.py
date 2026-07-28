from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from api.models import JobStatus

class GenerateRequest(BaseModel):
    ticker: str = Field(..., description="The stock ticker symbol (e.g., AAPL, MSFT)")
    agents: str = Field("full", description="Which pipeline to run: 'one', 'three', 'four', or 'full'")

class JobResponse(BaseModel):
    id: str
    ticker: str
    status: JobStatus
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    memo_html_path: Optional[str] = None

    class Config:
        from_attributes = True
