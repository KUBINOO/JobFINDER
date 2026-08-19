import os
import logging
import traceback
from typing import Optional
from datetime import datetime, timezone


from sqlmodel import Session
from database import engine
from models import Application, ApplicationStatus, UserPreferences

from factory import get_scraper
from llm_service import CoverLetterGenerator
from email_service import AsyncEmailSender
from utils.pdf_parser import extract_text_from_pdf

logger = logging.getLogger(__name__)

class JobContentValidationError(Exception):
    """Výjimka vyvolaná, pokud inzerát neobsahuje dostatečný nebo čitelný popis."""
    pass

async def _run_scraping(session: Session, application: Application) -> None:
    """
    Krok 1: Získání dat z pracovního inzerátu (Scraping) a validace obsahu (Quality Gate).
    """
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

    # Kontrola kvality (Quality Gate): Počet znaků a čitelnost popisu
    cleaned_desc = (job.description or "").strip()
    if len(cleaned_desc) < 150:
        logger.warning(
            f"Inzerát {job.source_url} má nedostatečný popis ({len(cleaned_desc)} znaků). Zastavuji pipeline."
        )
        raise JobContentValidationError(
            "Inzerát neobsahuje čitelný popis pracovní pozice (pravděpodobně dynamický JavaScript nebo externí kariérní stránka)."
        )

async def _run_llm_generation(session: Session, application: Application) -> None:
    """Krok 2 a 3: Vygenerování e-mailu pomocí LLM a sestavení výsledného textu."""
    user = application.user
    job = application.job_posting
    
    # Získání nastavení s cestou k PDF životopisu
    user_prefs = session.get(UserPreferences, 1)
    
    cv_text = ""
    if user_prefs and user_prefs.cv_file_path and os.path.exists(user_prefs.cv_file_path):
        try:
            cv_text = extract_text_from_pdf(user_prefs.cv_file_path)
            logger.info(f"Úspěšně extrahován text z CV PDF: {user_prefs.cv_file_path}")
        except Exception as e:
            logger.error(f"Nepodařilo se extrahovat text z PDF ({user_prefs.cv_file_path}): {e}")

    # Pokud text není k dispozici nebo soubor nebyl nalezen, zkusíme najít existující PDF ve složce uploads/
    if not cv_text or not cv_text.strip():
        uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
        if os.path.exists(uploads_dir):
            pdf_files = [os.path.join(uploads_dir, f) for f in os.listdir(uploads_dir) if f.lower().endswith(".pdf")]
            if pdf_files:
                # Seřadíme podle data úpravy a vezmeme nejnovější
                pdf_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                latest_pdf = pdf_files[0]
                try:
                    cv_text = extract_text_from_pdf(latest_pdf)
                    logger.info(f"Automaticky obnovena cesta k nalezenému CV PDF: {latest_pdf}")
                    if user_prefs:
                        user_prefs.cv_file_path = latest_pdf
                        session.add(user_prefs)
                        session.commit()
                except Exception as e:
                    logger.error(f"Nepodařilo se extrahovat text z nalezeného PDF ({latest_pdf}): {e}")

    # Fallback na textový profil z preferencí nebo User modelu, pokud PDF není vůbec
    if not cv_text or not cv_text.strip():
        profile_parts = []
        if user_prefs:
            if user_prefs.full_name: profile_parts.append(f"Jméno: {user_prefs.full_name}")
            if user_prefs.education: profile_parts.append(f"Vzdělání: {user_prefs.education}")
            if user_prefs.industry: profile_parts.append(f"Obor / Zaměření: {user_prefs.industry}")
            if user_prefs.linkedin_url: profile_parts.append(f"LinkedIn: {user_prefs.linkedin_url}")
        if user and user.cv_summary:
            profile_parts.append(f"Shrnutí zkušeností: {user.cv_summary}")
            
        if profile_parts:
            cv_text = "\n".join(profile_parts)
        else:
            cv_text = "Životopis není k dispozici."

    llm_model = None
    if user_prefs:

        llm_model = user_prefs.llm_model
        
        # Mapování modelů na aktuální verze
        if llm_model in ["gemini-1.5-flash", "gemini-flash-latest"]:
            llm_model = "gemini-1.5-flash"
        elif llm_model in ["gemini-1.5-pro", "gemini-pro-latest"]:
            llm_model = "gemini-1.5-pro"

        api_key = user_prefs.llm_api_key
        if user_prefs.llm_provider == "Google Gemini":
            if not llm_model.startswith("gemini/"):
                llm_model = f"gemini/{llm_model}"
            if api_key:
                os.environ["GEMINI_API_KEY"] = api_key
                os.environ["GOOGLE_API_KEY"] = api_key
        elif user_prefs.llm_provider == "OpenAI":
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
        elif user_prefs.llm_provider == "Anthropic":
            if api_key:
                os.environ["ANTHROPIC_API_KEY"] = api_key
        elif user_prefs.llm_provider == "Ollama":
            if not llm_model.startswith("ollama/"):
                llm_model = f"ollama/{llm_model}"
    else:
        api_key = None
                
    llm_generator = CoverLetterGenerator(model=llm_model, api_key=api_key)
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

async def _run_sending(
    session: Session, 
    application: Application, 
    recipient_email: Optional[str] = None, 
    subject: Optional[str] = None, 
    body: Optional[str] = None
) -> None:
    """Krok 4: Odeslání vygenerovaného e-mailu přes SMTP."""
    user = application.user
    job = application.job_posting
    user_prefs = session.get(UserPreferences, 1)
    
    smtp_email = (user_prefs and user_prefs.smtp_email) or user.email or user.smtp_username
    smtp_password = (user_prefs and user_prefs.smtp_password) or user.smtp_password
    smtp_port = (user_prefs and user_prefs.smtp_port) or 587
    cv_pdf_path = (user_prefs and user_prefs.cv_file_path)
    
    if not smtp_email or not smtp_password:
        logger.warning("Uživatel nemá nakonfigurované SMTP údaje v nastavení.")
        raise ValueError("V nastavení chybí SMTP přihlašovací údaje (e-mail a heslo aplikace).")
    
    host = "smtp.gmail.com"
    if "@seznam.cz" in smtp_email:
        host = "smtp.seznam.cz"
    elif "@outlook.com" in smtp_email or "@hotmail.com" in smtp_email:
        host = "smtp.office365.com"
        
    email_sender = AsyncEmailSender(
        host=host, 
        port=smtp_port,
        username=smtp_email,
        password=smtp_password,
        sender_email=smtp_email
    )
    
    final_recipient = recipient_email or getattr(job, "hr_email", None) or smtp_email
    final_subject = subject or application.generated_subject or f"Zájem o pozici: {job.title or 'Pracovní pozice'}"
    final_body = body or application.generated_body or ""
    
    await email_sender.send_application(
        recipient_email=final_recipient,
        subject=final_subject,
        body=final_body,
        cv_pdf_path=cv_pdf_path
    )

async def process_job_application(application_id: int) -> None:
    """
    Spouští kompletní automatizovanou pipeline pro nově přidanou nebo prozkoumanou pozici:
    1. Fáze Scraping: Inzerát se stáhne, zvaliduje (Quality Gate) a uloží do DB.
    2. Fáze AI Analýza: Pokud má uživatel nastavené LLM preference, automaticky se vygeneruje
       motivační e-mail a vypočítá AI Match Score (stav GENERATED / Připraveno).
    """
    import asyncio
    import random
    
    delay = random.uniform(0.5, 2.0)
    await asyncio.sleep(delay)
    
    with Session(engine) as session:
        application = session.get(Application, application_id)
        if not application:
            logger.error(f"Žádost {application_id} nebyla nalezena v databázi.")
            return

        try:
            # Fáze 1: Scraping a stažení inzerátu
            application.status = ApplicationStatus.SCRAPING
            application.updated_at = datetime.now(timezone.utc)
            session.add(application)
            session.commit()
            
            await _run_scraping(session, application)
            
            # Po úspěšném scrapingu nastavíme stav na PENDING (připraveno pro uživatele)
            application.status = ApplicationStatus.PENDING
            application.updated_at = datetime.now(timezone.utc)
            application.error_logs = None
            session.add(application)
            session.commit()
            logger.info(f"Úspěšně stažen inzerát pro žádost {application_id}. Připraveno k manuálnímu spuštění generování uživatelem.")
            
        except JobContentValidationError as val_err:

            logger.warning(f"Quality gate selhala pro žádost {application_id}: {val_err}")
            session.rollback()
            application.status = ApplicationStatus.FAILED
            application.error_logs = str(val_err)
            application.updated_at = datetime.now(timezone.utc)
            session.add(application)
            session.commit()
        except Exception as e:
            logger.error(f"Chyba při zpracování žádosti {application_id}: {e}")
            error_msg = f"{str(e)}\n\n{traceback.format_exc()}"
            session.rollback()
            application.status = ApplicationStatus.FAILED
            application.error_logs = error_msg
            application.updated_at = datetime.now(timezone.utc)
            session.add(application)
            session.commit()

async def generate_application_email(application_id: int) -> None:
    """
    Manuálně spuštěné vygenerování motivačního e-mailu a AI shody (Match score).
    """
    with Session(engine) as session:
        application = session.get(Application, application_id)
        if not application:
            logger.error(f"Žádost {application_id} nebyla nalezena.")
            return

        try:
            application.status = ApplicationStatus.GENERATING
            application.updated_at = datetime.now(timezone.utc)
            session.add(application)
            session.commit()

            await _run_llm_generation(session, application)

            application.status = ApplicationStatus.GENERATED
            application.updated_at = datetime.now(timezone.utc)
            application.error_logs = None
            session.add(application)
            session.commit()
            logger.info(f"Úspěšně vygenerován motivační e-mail pro žádost {application_id}.")
        except Exception as e:
            logger.error(f"Chyba při generování e-mailu pro žádost {application_id}: {e}")
            error_msg = f"{str(e)}\n\n{traceback.format_exc()}"
            session.rollback()
            application.status = ApplicationStatus.FAILED
            application.error_logs = f"Chyba při generování e-mailu: {error_msg}"
            application.updated_at = datetime.now(timezone.utc)
            session.add(application)
            session.commit()

async def send_application_email(
    application_id: int, 
    recipient_email: Optional[str] = None, 
    subject: Optional[str] = None, 
    body: Optional[str] = None
) -> None:
    """
    Manuální odeslání e-mailu přes SMTP.
    """
    with Session(engine) as session:
        application = session.get(Application, application_id)
        if not application:
            raise ValueError(f"Žádost {application_id} nebyla nalezena.")

        try:
            application.status = ApplicationStatus.SENDING
            if subject:
                application.generated_subject = subject
            if body:
                application.generated_body = body
            application.updated_at = datetime.now(timezone.utc)
            session.add(application)
            session.commit()

            await _run_sending(session, application, recipient_email, subject, body)

            application.status = ApplicationStatus.SENT
            application.updated_at = datetime.now(timezone.utc)
            application.error_logs = None
            session.add(application)
            session.commit()
            logger.info(f"Úspěšně odeslán e-mail pro žádost {application_id}.")
        except Exception as e:
            logger.error(f"Chyba při odesílání e-mailu pro žádost {application_id}: {e}")
            session.rollback()
            application.status = ApplicationStatus.FAILED
            application.error_logs = f"Chyba při odesílání e-mailu přes SMTP: {str(e)}"
            application.updated_at = datetime.now(timezone.utc)
            session.add(application)
            session.commit()
            raise
