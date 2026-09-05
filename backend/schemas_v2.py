from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class EmploymentType(str, Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACTOR_B2B = "CONTRACTOR_B2B"
    INTERNSHIP = "INTERNSHIP"
    UNKNOWN = "UNKNOWN"


class RemotePolicy(str, Enum):
    FULLY_REMOTE = "FULLY_REMOTE"
    HYBRID = "HYBRID"
    ON_SITE = "ON_SITE"


class TimezoneRegion(str, Enum):
    EMEA = "EMEA"              # Evropa, Blízký východ, Afrika (CET kompatibilní)
    AMERICAS = "AMERICAS"      # US, Kanada, LatAm
    APAC = "APAC"              # Asie a Tichomoří
    WORLDWIDE = "WORLDWIDE"    # Zcela nezávislé na lokaci / Async
    UNKNOWN = "UNKNOWN"


class Compensation(BaseModel):
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    currency: Optional[str] = Field(default=None, description="ISO kód (CZK, EUR, USD)")
    interval: Optional[str] = Field(default="monthly", description="hourly, monthly, yearly")


class RawJobPayload(BaseModel):
    """Surový nestrukturovaný záznam z workeru před normalizací a deduplikací."""
    source_portal: str
    source_url: str
    title: str
    company_name: str
    description: str
    raw_location: Optional[str] = None
    raw_tags: List[str] = Field(default_factory=list)
    raw_salary: Optional[str] = None
    apply_url: Optional[str] = None
    published_at: Optional[datetime] = None


class JobListing(BaseModel):
    """Normalizovaný inzerát po průchodu Normalization & Deduplication Agentem."""
    canonical_id: str = Field(description="Globálně unikátní fingerprint pro deduplikaci")
    source_portal: str = Field(description="Zdroj: RemoteOK, Remotive, WWR, Arbeitnow, Jobs.cz...")
    source_url: str = Field(description="Originální odkaz na inzerát")
    apply_url: Optional[str] = Field(default=None, description="Přímý odkaz na přihlášku")
    
    title: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    company_domain: Optional[str] = None
    description_raw: str = Field(description="Vyčištěný text popisu pozice")
    published_at: Optional[datetime] = None
    
    employment_type: EmploymentType = Field(default=EmploymentType.UNKNOWN)
    remote_policy: RemotePolicy = Field(default=RemotePolicy.FULLY_REMOTE)
    
    timezone_region: TimezoneRegion = Field(default=TimezoneRegion.UNKNOWN)
    allowed_countries: List[str] = Field(default_factory=list)
    min_cet_overlap_hours: Optional[int] = Field(default=None)
    
    compensation: Optional[Compensation] = None
    extracted_skills: List[str] = Field(default_factory=list)


class CandidateFitEvaluation(BaseModel):
    """Výstup Candidate Fit & Scoring Agenta."""
    match_score: int = Field(ge=0, le=100, description="Celková shoda 0 až 100 %")
    fit_summary: str = Field(description="1-2 věty shrnující shodu")
    pros: List[str] = Field(default_factory=list, description="Silné stránky kandidáta pro tuto roli")
    cons: List[str] = Field(default_factory=list, description="Rizika a nesplněné požadavky")
    missing_skills: List[str] = Field(default_factory=list, description="Technologie z inzerátu, které v CV chybí")
    part_time_viability: str = Field(description="Zhodnocení zkráceného úvazku / kontraktu")
    timezone_compatibility: str = Field(description="Zhodnocení časového pásma (ČR / CET)")
    tailored_outreach_pitch: Optional[str] = Field(default=None, description="Draft průvodního e-mailu")
