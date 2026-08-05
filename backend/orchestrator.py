import logging
import traceback
from datetime import datetime, timezone

from sqlmodel import Session
from database import engine
from models import Application, ApplicationStatus, UserPreferences

from factory import get_scraper
from llm_service import CoverLetterGenerator
from email_service import AsyncEmailSender
from utils.pdf_parser import extract_text_from_pdf

logger = logging.getLogger(__name__)

async def _run_scraping(session: Session, application: Application) -> None:
    """Krok 1: Získání dat z pracovního inzerátu (Scraping)."""
    job = application.job_posting
    scraper = get_scraper(job.source_url)
    scraped_job = await scraper.extract_job_details(job.source_url)
    
    # Aktualizace detailů inzerátu v databázi
    job.description = scraped_job.description
    job.title = scraped_job.title
    job.company_name = scraped_job.company_name
    job.scraped_at = datetime.now(timezone.utc)
    
    session.add(job)
    session.commit()

async def _run_llm_generation(session: Session, application: Application) -> None:
    """Krok 2 a 3: Vygenerování e-mailu pomocí LLM a sestavení výsledného textu."""
    user = application.user
    job = application.job_posting
    
    # Získání nastavení s cestou k PDF životopisu
    user_prefs = session.get(UserPreferences, 1)
    
    cv_text = user.cv_summary or "Životopis není k dispozici."
    if user_prefs and user_prefs.cv_file_path:
        try:
            cv_text = extract_text_from_pdf(user_prefs.cv_file_path)
            logger.info(f"Úspěšně extrahován text z CV PDF: {user_prefs.cv_file_path}")
        except Exception as e:
            logger.error(f"Nepodařilo se extrahovat text z PDF: {e}")
            raise # Re-raise, as requested: "Include error handling... raise a clear exception" or rather let it fail the background job so we know
    
    import os
    llm_model = None
    if user_prefs:
        llm_model = user_prefs.llm_model
        
        # Map deprecated gemini models to their latest versions to prevent 404 errors
        if llm_model == "gemini-1.5-flash":
            llm_model = "gemini-flash-latest"
        elif llm_model == "gemini-1.5-pro":
            llm_model = "gemini-pro-latest"

        if user_prefs.llm_provider == "Google Gemini":
            if not llm_model.startswith("gemini/"):
                llm_model = f"gemini/{llm_model}"
            if user_prefs.llm_api_key:
                os.environ["GEMINI_API_KEY"] = user_prefs.llm_api_key
        elif user_prefs.llm_provider == "OpenAI":
            if user_prefs.llm_api_key:
                os.environ["OPENAI_API_KEY"] = user_prefs.llm_api_key
        elif user_prefs.llm_provider == "Anthropic":
            if user_prefs.llm_api_key:
                os.environ["ANTHROPIC_API_KEY"] = user_prefs.llm_api_key
        elif user_prefs.llm_provider == "Ollama":
            if not llm_model.startswith("ollama/"):
                llm_model = f"ollama/{llm_model}"
                
    llm_generator = CoverLetterGenerator(model=llm_model)
    draft = await llm_generator.generate_email(
        user_cv=cv_text,
        job_desc=job.description or "Popis pozice není k dispozici.",
        job_title=job.title or job.company_name or "Neznámá pozice"
    )
    
    # Krok 3: Sestavení výsledného e-mailu (Assembly)
    # Složení 6 polí do jednoho řetězce, oddělených dvojitým odřádkováním
    assembled_body = "\n\n".join([
        draft.osloveni,
        draft.uvod,
        draft.moje_zkusenosti,
        draft.tech_stack_shoda,
        draft.zaver_cta,
        draft.podpis
    ])
    
    # Uložení výsledku do modelu Application
    application.match_score = draft.match_score
    application.match_reason = draft.match_reason
    application.generated_subject = f"Zájem o pozici: {job.title or 'Neznámá pozice'}"
    application.generated_body = assembled_body
    
    session.add(application)
    session.commit()

async def _run_sending(session: Session, application: Application) -> None:
    """Krok 4: Odeslání vygenerovaného e-mailu přes SMTP."""
    user = application.user
    job = application.job_posting
    
    if not user.smtp_username or not user.smtp_password:
        logger.warning("Uživatel nemá nakonfigurované SMTP údaje. Přeskakuji odeslání e-mailu.")
        return
    
    email_sender = AsyncEmailSender(
        host="smtp.gmail.com", 
        port=587,
        username=user.smtp_username,
        password=user.smtp_password,
        sender_email=user.email
    )
    
    cv_pdf_path = getattr(user, "cv_pdf_path", None)
    
    # Záložní e-mail pro testování, pokud HR e-mail chybí
    recipient_email = getattr(job, "hr_email", user.email) 
    
    await email_sender.send_application(
        recipient_email=recipient_email,
        subject=application.generated_subject or "Žádost o zaměstnání",
        body=application.generated_body or "",
        cv_pdf_path=cv_pdf_path
    )

async def process_job_application(application_id: int) -> None:
    """
    Hlavní Orchestrator běžící na pozadí pomocí FastAPI BackgroundTasks.
    Explicitně vytváří vlastní izolovanou databázovou session pro bezpečné řízení stavů.
    """
    logger.info(f"Spouštím zpracování na pozadí pro žádost {application_id}")
    
    # Krok 1 (Kritický požadavek): Nezávislá izolovaná DB Session pomocí context manageru
    with Session(engine) as session:
        application = session.get(Application, application_id)
        if not application:
            logger.error(f"Žádost {application_id} nebyla nalezena v databázi.")
            return

        # Hranice chyb (Error Boundary) - Celá pipeline je zabalena v try/except bloku
        try:
            # Fáze 1: Scraping
            application.status = ApplicationStatus.SCRAPING
            application.updated_at = datetime.now(timezone.utc)
            session.add(application)
            session.commit()
            
            await _run_scraping(session, application)
            
            # Fáze 2 a 3: Generating a Assembly
            application.status = ApplicationStatus.GENERATING
            application.updated_at = datetime.now(timezone.utc)
            session.add(application)
            session.commit()
            
            await _run_llm_generation(session, application)
            
            # Fáze 4: Sending
            application.status = ApplicationStatus.SENDING
            application.updated_at = datetime.now(timezone.utc)
            session.add(application)
            session.commit()
            
            await _run_sending(session, application)
            
            # Fáze 5: Completed
            application.status = ApplicationStatus.COMPLETED
            application.updated_at = datetime.now(timezone.utc)
            session.add(application)
            session.commit()
            
            logger.info(f"Úspěšně dokončeno zpracování žádosti {application_id}.")
            
        except Exception as e:
            # Jakékoliv selhání nastaví stav na FAILED a uloží chybu
            logger.error(f"Chyba při zpracování žádosti {application_id}: {e}")
            
            # Extrakce celého tracebaku pro snadnější ladění vývojářem
            error_msg = f"{str(e)}\n\n{traceback.format_exc()}"
            
            # Zajištění čistého stavu session (rollback), abychom předešli pádům při chybě transakce
            session.rollback()
            
            application.status = ApplicationStatus.FAILED
            application.error_logs = error_msg
            application.updated_at = datetime.now(timezone.utc)
            
            session.add(application)
            try:
                session.commit()
                logger.info(f"Uložen chybový stav FAILED pro žádost {application_id}.")
            except Exception as db_err:
                logger.error(f"Kritická chyba: Nepodařilo se uložit chybový stav pro žádost {application_id}: {db_err}")
