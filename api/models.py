from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from api.database import Base

class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Tier(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Integer, default=1)
    is_admin = Column(Boolean, default=False)
    tier = Column(Enum(Tier), default=Tier.FREE)
    credits = Column(Integer, default=5)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    jobs = relationship("Job", back_populates="owner")

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True) # Run ID like MSFT_2026...
    ticker = Column(String, index=True, nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Memo Output Paths
    memo_html_path = Column(String, nullable=True)
    memo_pdf_path = Column(String, nullable=True)
    memo_docx_path = Column(String, nullable=True)
    
    # Optional User link
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner = relationship("User", back_populates="jobs")

class PaymentEvent(Base):
    __tablename__ = "payment_events"

    stripe_event_id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
