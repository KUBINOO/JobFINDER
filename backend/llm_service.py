import os
import logging
import asyncio
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from litellm import acompletion
from pydantic import ValidationError

from schemas import JobAnalysisResult, JobMatchingResult

import litellm
from litellm.exceptions import AuthenticationError, BadRequestError

logger = logging.getLogger(__name__)

# Globální semafor pro řízení souběžných volání LLM (ochrana před 429 Rate Limit)
_llm_semaphore = asyncio.Semaphore(2)

class LLMGenerationError(Exception):
    """Vlastní výjimka pro chyby při generování přes LLM."""
    pass

def _should_retry(exception: Exception) -> bool:
    err_str = str(exception).lower()
    # Do not retry on permanent errors like invalid API key, auth failure, bad requests or schema errors
    if isinstance(exception, (AuthenticationError, BadRequestError, ValidationError)):
        return False
    if any(keyword in err_str for keyword in ["api_key_invalid", "invalid_api_key", "invalid api key", "400", "401", "403", "permission_denied", "not_found", "unauthenticated"]):
        return False
    return True

class CoverLetterGenerator:
    def __init__(
        self, 
        model: Optional[str] = None, 
        api_key: Optional[str] = None, 
        api_base: Optional[str] = None,
        tone_of_voice: Optional[str] = "formal"
    ):
        # Inicializace modelu z proměnných prostředí, výchozí je gpt-4o
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        self.api_key = api_key
        self.api_base = api_base
        self.tone_of_voice = (tone_of_voice or "formal").lower()
        
        tone_instructions = {
            "formal": "Tvůj tón v e-mailu musí být formální, uctivý, profesionální, zdvořilý a strukturovaný.",
            "friendly": "Tvůj tón v e-mailu musí být přátelský, lidský, otevřený a pozitivní, ale stále vysoce kompetentní.",
            "dynamic": "Tvůj tón v e-mailu musí být energický, dynamický, sebevědomý a přímočarý se zaměřením na přínos a tah na branku."
        }
        chosen_tone = tone_instructions.get(self.tone_of_voice, tone_instructions["formal"])

        # Systémový prompt v češtině pro striktní dodržování formátu a jazyka
        self.system_prompt = (
            f"Jsi striktní HR hodnotitel a expert na kariérní poradenství. Nejprve kriticky zhodnoť shodu uživatele s pozicí a poté pro něj napiš vysoce personalizovaný průvodní e-mail. "
            f"{chosen_tone} Vyhni se klišé a zbytečné vatě. Zni jako skutečný a velmi schopný člověk.\n\n"
            "KRITICKÉ INSTRUKCE:\n"
            "1. HR HODNOCENÍ: Kriticky porovnej CV uživatele a popis pozice. Bodování (match_score) musí být realistické. "
            "Pokud uživateli chybí klíčová technologie nebo roky praxe, skóre MUSÍ výrazně klesnout (např. na 30-40%). Žádné umělé navyšování. "
            "Důvody pro skóre shrň maximálně do 1 věty (match_reason).\n"
            "2. JAZYK: Celý výstup MUSÍ BÝT striktně v češtině (včetně inline komentářů nebo hodnot v JSON).\n"
            "3. ANTI-HALUCINACE: Hodnocení i e-mail musí vycházet POUZE z explicitně uvedených faktů v CV a popisu pozice. "
            "Můžeš propojit dovednosti uživatele s požadavky na pozici, ale ABSOLUTNĚ NESMÍŠ vymýšlet žádné dovednosti, tituly, "
            "technologie ani roky praxe. Pokud uživateli chybí požadovaná dovednost, zaměř se v e-mailu na jeho schopnost "
            "se rychle učit nebo zdůrazni přenositelné zkušenosti.\n"
            "4. ŽÁDNÉ ZÁSTUPNÉ TEXTY: Nepoužívej zástupné texty jako [Tvé jméno], [Název firmy]. "
            "Vytvoř dynamický a přirozený podpis pomocí informací z poskytnutého CV.\n\n"
            "Výstup musí být striktně ve formátu JSON, který odpovídá požadovanému schématu."
        )

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1.0, min=1, max=4),
        retry=retry_if_exception(_should_retry),
        reraise=True
    )
    async def _call_llm(self, user_cv: str, job_desc: str, job_title: str) -> JobAnalysisResult:
        user_prompt = (
            f"NÁZEV POZICE: {job_title}\n\n"
            f"POPIS POZICE:\n{job_desc}\n\n"
            f"CV UŽIVATELE:\n{user_cv}\n\n"
            "Vytvoř návrh průvodního e-mailu na základě výše uvedených informací."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        async with _llm_semaphore:
            await asyncio.sleep(0.3)
            try:
                logger.info(f"Volání LLM ({self.model}) pro vygenerování e-mailu pro pozici {job_title}")
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "response_format": JobAnalysisResult,
                    "timeout": 60
                }
                if self.api_key:
                    kwargs["api_key"] = self.api_key
                if self.api_base:
                    kwargs["api_base"] = self.api_base
                    
                response = await acompletion(**kwargs)
                
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("LLM vrátilo prázdný obsah odpovědi.")
                    
                return JobAnalysisResult.model_validate_json(content)
            
            except ValidationError as ve:
                logger.error(f"Nepodařilo se naparsovat odpověď z LLM jako JobAnalysisResult: {ve}")
                raise LLMGenerationError("LLM vrátilo neplatné schéma") from ve
            except Exception as e:
                logger.error(f"Volání LLM API selhalo: {e}")
                raise LLMGenerationError(f"Generování přes LLM selhalo: {e}") from e

    async def generate_email(self, user_cv: str, job_desc: str, job_title: str) -> JobAnalysisResult:
        try:
            return await self._call_llm(user_cv, job_desc, job_title)
        except Exception as e:
            logger.error(f"Konečné selhání při generování e-mailu pro pozici {job_title}: {e}")
            raise LLMGenerationError(f"Nepodařilo se vygenerovat e-mail: {e}") from e

class JobMatcher:
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None, api_base: Optional[str] = None):
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        self.api_key = api_key
        self.api_base = api_base
        self.system_prompt = (
            "Jsi striktní a objektivní HR hodnotitel a kariérní poradce. Tvým jediným úkolem je kriticky a realisticky porovnat životopis kandidáta s požadavky pracovní pozice a spočítat shodu.\n\n"
            "KRITICKÉ INSTRUKCE:\n"
            "1. HODNOCENÍ (match_score): Celé číslo v rozsahu 0 až 100 vyjadřující realistickou shodu. Pokud kandidátovi chybí klíčové technologie, praxe nebo oborové vzdělání, skóre MUSÍ znatelně klesnout (např. na 25-45%). Žádné umělé lichocení.\n"
            "2. ZDŮVODNĚNÍ (match_reason): Maximálně 1 až 2 věty v češtině shrnující hlavní silné stránky a chybějící požadavky.\n"
            "3. Výstup musí být striktně ve formátu JSON odpovídajícím schématu."
        )

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1.0, min=1, max=4),
        retry=retry_if_exception(_should_retry),
        reraise=True
    )
    async def evaluate_match(self, user_cv: str, job_desc: str, job_title: str) -> JobMatchingResult:
        user_prompt = (
            f"NÁZEV POZICE: {job_title}\n\n"
            f"POPIS POZICE:\n{job_desc}\n\n"
            f"CV A PROFIL KANDIDÁTA:\n{user_cv}\n\n"
            "Vyhodnoť shodu kandidáta s touto pozicí a vrať JSON s match_score a match_reason."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        async with _llm_semaphore:
            await asyncio.sleep(0.3)
            try:
                logger.info(f"Volání LLM ({self.model}) pro rychlé vyhodnocení shody pro pozici: {job_title}")
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "response_format": JobMatchingResult,
                    "timeout": 30
                }
                if self.api_key:
                    kwargs["api_key"] = self.api_key
                if self.api_base:
                    kwargs["api_base"] = self.api_base
                    
                response = await acompletion(**kwargs)
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("LLM vrátilo prázdný obsah odpovědi.")
                    
                return JobMatchingResult.model_validate_json(content)
            except ValidationError as ve:
                logger.error(f"Nepodařilo se naparsovat shodu z LLM: {ve}")
                raise LLMGenerationError("LLM vrátilo neplatné schéma shody") from ve
            except Exception as e:
                logger.error(f"Volání LLM API pro shodu selhalo: {e}")
                raise LLMGenerationError(f"Vyhodnocení shody selhalo: {e}") from e
