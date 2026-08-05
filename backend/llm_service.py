import os
import logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from litellm import acompletion
from pydantic import ValidationError

from schemas import JobAnalysisResult

logger = logging.getLogger(__name__)

class LLMGenerationError(Exception):
    """Vlastní výjimka pro chyby při generování přes LLM."""
    pass

class CoverLetterGenerator:
    def __init__(self, model: Optional[str] = None):
        # Inicializace modelu z proměnných prostředí, výchozí je gpt-4o
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        
        # Systémový prompt v češtině pro striktní dodržování formátu a jazyka
        self.system_prompt = (
            "Jsi striktní HR hodnotitel a expert na kariérní poradenství. Nejprve kriticky zhodnoť shodu uživatele s pozicí a poté pro něj napiš vysoce personalizovaný průvodní e-mail. "
            "Tvůj tón v e-mailu musí být profesionální, zdvořilý, sebevědomý a stručný. Vyhni se klišé a zbytečné vatě. "
            "Zni jako skutečný a velmi kompetentní člověk.\n\n"
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
        stop=stop_after_attempt(2), # 1 první pokus + 1 opakování = max 2 pokusy
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
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

        try:
            logger.info(f"Volání LLM ({self.model}) pro vygenerování e-mailu pro pozici {job_title}")
            response = await acompletion(
                model=self.model,
                messages=messages,
                response_format=JobAnalysisResult,
                temperature=0.3 # Nastavení teploty na 0.3 pro vysokou faktickou konzistenci
            )
            
            # litellm s response_format=PydanticModel zajistí JSON výstup.
            # Zpracujeme vrácený text pro zajištění přesné shody s JobAnalysisResult.
            content = response.choices[0].message.content
            if not content:
                raise ValueError("LLM vrátilo prázdný obsah odpovědi.")
                
            return JobAnalysisResult.model_validate_json(content)
        
        except ValidationError as ve:
            logger.error(f"Nepodařilo se naparsovat odpověď z LLM jako JobAnalysisResult: {ve}")
            raise LLMGenerationError("LLM vrátilo neplatné schéma") from ve
        except Exception as e:
            logger.error(f"Volání LLM API selhalo: {e}")
            # Tato výjimka je zachycena knihovnou tenacity pro opakování
            raise LLMGenerationError(f"Generování přes LLM selhalo: {e}") from e

    async def generate_email(self, user_cv: str, job_desc: str, job_title: str) -> JobAnalysisResult:
        """
        Vygeneruje návrh e-mailu pomocí specifikovaného LLM.
        Při selhání se jednou zopakuje, poté vyvolá LLMGenerationError.
        """
        try:
            return await self._call_llm(user_cv, job_desc, job_title)
        except Exception as e:
            logger.error(f"Konečné selhání při generování e-mailu pro pozici {job_title}: {e}")
            raise LLMGenerationError(f"Nepodařilo se vygenerovat e-mail: {e}") from e
