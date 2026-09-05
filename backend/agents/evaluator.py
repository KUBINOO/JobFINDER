import os
import logging
import asyncio
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from litellm import acompletion
from pydantic import ValidationError

from schemas_v2 import JobListing, CandidateFitEvaluation

logger = logging.getLogger(__name__)

_eval_semaphore = asyncio.Semaphore(2)


class CandidateFitAgent:
    """
    Agent 4: Candidate Fit & Scoring Agent
    Provádí kritické porovnání profilu uchazeče s inzerátem a vyhodnocuje:
    - Match score (0 - 100 %)
    - PROs a CONs
    - Chybějící technologie
    - Proveditelnost part-time úvazku a překryv časových pásem (CET / Evropa)
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        self.model = model or os.getenv("LLM_MODEL", "gemini/gemini-2.5-flash")
        self.api_key = api_key
        self.api_base = api_base

        self.system_prompt = (
            "You are a strict, objective, and expert Technical Recruiter & Career Advisor for Remote Engineering roles.\n"
            "Your task is to critically analyze a candidate's background against a job listing and return a detailed, realistic evaluation.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. REALISTIC MATCH SCORE (0-100):\n"
            "   - Be completely realistic. If the candidate lacks key required technologies or years of experience, score MUST drop to 30-50%.\n"
            "   - Do NOT flatter the candidate.\n"
            "2. PROS & CONS:\n"
            "   - pros: 2-3 specific bullet points where the candidate excels.\n"
            "   - cons: 2-3 specific risks or gaps.\n"
            "   - missing_skills: Exact tech stack or tool names required by the job that are absent in the candidate's CV.\n"
            "3. PART-TIME VIABILITY:\n"
            "   - Specifically assess whether this role can realistically be worked as Part-time / Working Student / Contractor (15-25 hours/week).\n"
            "4. TIMEZONE COMPATIBILITY:\n"
            "   - Assess compatibility with candidate's location in Central Europe (CET / UTC+1).\n"
            "5. TAILORED OUTREACH PITCH:\n"
            "   - A short, punchy 3-sentence outreach pitch highlighting why the candidate is worth interviewing despite any gaps.\n"
            "6. LANGUAGE:\n"
            "   - All text fields in your evaluation JSON should be in English (or Czech if the job ad itself is in Czech).\n\n"
            "Output must strictly follow the CandidateFitEvaluation JSON schema."
        )

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1.0, min=1, max=3),
        reraise=True
    )
    async def evaluate_fit(
        self, 
        job: JobListing, 
        user_cv: str,
        user_preferences_summary: str = ""
    ) -> CandidateFitEvaluation:
        user_prompt = (
            f"=== JOB TITLE ===\n{job.title} at {job.company_name} ({job.source_portal})\n\n"
            f"=== JOB DESCRIPTION ===\n{job.description_raw[:3500]}\n\n"
            f"=== CANDIDATE CV / PROFILE ===\n{user_cv}\n\n"
            f"=== CANDIDATE TARGETS ===\n"
            f"Looking for Part-time / Contractor / Student friendly remote role in Central Europe (CET timezone).\n"
            f"{user_preferences_summary}\n\n"
            "Critically evaluate this match and return the JSON object."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        async with _eval_semaphore:
            await asyncio.sleep(0.2)
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "response_format": CandidateFitEvaluation,
                    "timeout": 45
                }
                if self.api_key:
                    kwargs["api_key"] = self.api_key
                if self.api_base:
                    kwargs["api_base"] = self.api_base

                response = await acompletion(**kwargs)
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("LLM returned empty response")

                return CandidateFitEvaluation.model_validate_json(content)

            except Exception as e:
                logger.error(f"Fit evaluation failed for {job.title}: {e}")
                # Fallback heurisika pokud LLM selže
                return CandidateFitEvaluation(
                    match_score=50,
                    fit_summary=f"Automatická heuristika (LLM nedostupné: {str(e)[:50]})",
                    pros=["Pozice odpovídá základnímu hledání."],
                    cons=["Detailní AI analýza selhala."],
                    missing_skills=[],
                    part_time_viability="K ověření manuálně u inzerenta.",
                    timezone_compatibility=f"Detekovaný region: {job.timezone_region.value}",
                    tailored_outreach_pitch=f"Mám zájem o pozici {job.title}."
                )
