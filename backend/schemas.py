from pydantic import BaseModel, HttpUrl

class ScrapedJob(BaseModel):
    source_url: HttpUrl
    title: str
    company_name: str
    description: str

class JobAnalysisResult(BaseModel):
    match_score: int
    match_reason: str
    osloveni: str
    uvod: str
    moje_zkusenosti: str
    tech_stack_shoda: str
    zaver_cta: str
    podpis: str

from typing import Optional

class PreferencesUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    age: Optional[int] = None
    education: Optional[str] = None
    industry: Optional[str] = None
    linkedin_url: Optional[str] = None
    llm_provider: str
    llm_model: str
    llm_api_key: Optional[str] = None
    ollama_host: Optional[str] = None
    tone_of_voice: Optional[str] = "formal"
    custom_prompt: Optional[str] = None
    smtp_email: str
    smtp_password: str
    smtp_port: int
    scraper_delay_min: Optional[float] = 2.0
    scraper_delay_max: Optional[float] = 5.0
