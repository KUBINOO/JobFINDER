from enum import Enum
from typing import List, Optional
from datetime import datetime, timezone
from sqlmodel import Field, Relationship, SQLModel


class ApplicationStatus(str, Enum):
    PENDING = "PENDING"
    SCRAPING = "SCRAPING"
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    SENDING = "SENDING"
    SENT = "SENT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERVIEW = "INTERVIEW"
    REJECTED = "REJECTED"
    OFFER = "OFFER"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    first_name: str
    last_name: str
    email: str
    cv_summary: Optional[str] = Field(default=None)
    # These should be encrypted in a real production environment
    smtp_username: Optional[str] = Field(default=None)
    smtp_password: Optional[str] = Field(default=None)

    applications: List["Application"] = Relationship(back_populates="user")


class JobPosting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_url: str = Field(unique=True)
    title: str
    company_name: str
    description: Optional[str] = Field(default=None)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    applications: List["Application"] = Relationship(back_populates="job_posting")


class Application(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    job_id: int = Field(foreign_key="jobposting.id")
    status: ApplicationStatus = Field(default=ApplicationStatus.PENDING)
    generated_subject: Optional[str] = Field(default=None)
    generated_body: Optional[str] = Field(default=None)
    error_logs: Optional[str] = Field(default=None)
    match_score: Optional[int] = Field(default=None)
    match_reason: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    user: User = Relationship(back_populates="applications")
    job_posting: JobPosting = Relationship(back_populates="applications")

class UserPreferences(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)
    age: Optional[int] = Field(default=None)
    education: Optional[str] = Field(default=None)
    industry: Optional[str] = Field(default=None)
    cv_file_path: Optional[str] = Field(default=None)
    linkedin_url: Optional[str] = Field(default=None)
    llm_provider: str
    llm_model: str
    llm_api_key: Optional[str] = Field(default=None)
    ollama_host: Optional[str] = Field(default=None)
    smtp_email: str
    smtp_password: str
    smtp_port: int
