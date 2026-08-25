import os
import logging
import traceback
from typing import Optional
from datetime import datetime, timezone


from sqlmodel import Session
from database import engine
from models import Application, ApplicationStatus, UserPreferences

from factory import get_scraper
from llm_service import CoverLetterGenerator, JobMatcher
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
    
    # Aktualizace detailů inzerátu v databázi (nepřepisovat kvalitní název generickými texty)
    if scraped_job.description:
        job.description = scraped_job.description
    
    if scraped_job.title and scraped_job.title not in ["Neznámá pozice", "Zatím nenačteno"] and not scraped_job.title.lower().startswith("detail pozice"):
        job.title = scraped_job.title
    elif not job.title or job.title in ["Zatím nenačteno", "Neznámá pozice"]:
        job.title = scraped_job.title or "Pracovní pozice"

    if scraped_job.company_name and scraped_job.company_name not in ["Neznámá společnost", "Zatím nenačteno"] and "atmoskop" not in scraped_job.company_name.lower():
        job.company_name = scraped_job.company_name
    elif not job.company_name or job.company_name in ["Zatím nenačteno", "Neznámá společnost"]:
        job.company_name = scraped_job.company_name or "Neznámá společnost"

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

def _get_llm_setup(session: Session, application: Application):
    """Získá kompletní profil uživatele (CV + formulář) a nakonfiguruje LLM model a klíč."""
    user = application.user
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

    profile_parts = []
    if user_prefs:
        if user_prefs.full_name: profile_parts.append(f"Jméno: {user_prefs.full_name}")
        if user_prefs.phone_number: profile_parts.append(f"Telefon: {user_prefs.phone_number}")
        if user_prefs.education: profile_parts.append(f"Vzdělání: {user_prefs.education}")
        if user_prefs.industry: profile_parts.append(f"Obor / Specializace: {user_prefs.industry}")
        if user_prefs.linkedin_url: profile_parts.append(f"LinkedIn: {user_prefs.linkedin_url}")
        if user_prefs.custom_prompt: profile_parts.append(f"Specifické instrukce a preference uchazeče: {user_prefs.custom_prompt}")
    if user and user.cv_summary:
        profile_parts.append(f"Shrnutí zkušeností: {user.cv_summary}")
        
    full_user_context_parts = []
    if cv_text and cv_text.strip():
        full_user_context_parts.append(f"=== TEXT EXTRAHOVANÝ Z ŽIVOTOPISU (CV PDF) ===\n{cv_text.strip()}")
    if profile_parts:
        full_user_context_parts.append(f"=== DOPLŇUJÍCÍ PROFIL UŽIVATELE Z NASTAVENÍ ===\n" + "\n".join(profile_parts))
        
    full_user_context = "\n\n".join(full_user_context_parts).strip()
    if not full_user_context:
        raise ValueError("Chybí podklady pro AI: Nemáte nahraný životopis (PDF) ani vyplněný profil v Nastavení. Doplňte prosím své údaje, aby AI mohla vyhodnotit shodu s pozicí.")

    llm_provider = user_prefs.llm_provider if user_prefs else "Google Gemini"
    llm_model = (user_prefs.llm_model if user_prefs and user_prefs.llm_model else "gemini-3.7-flash").strip()
    if llm_model == "gemini-1.5-flash":
        llm_model = "gemini-3.7-flash"
    api_key = (user_prefs.llm_api_key if user_prefs and user_prefs.llm_api_key else "").strip()

    # Validace a konfigurace poskytovatele LLM
    if llm_provider == "Google Gemini":
        if not api_key:
            raise ValueError("Chybí API klíč pro Google Gemini. Zadejte prosím svůj platný API klíč v Nastavení -> AI a Chování (klíč získáte zdarma na aistudio.google.com).")
        if not llm_model.startswith("gemini/"):
            llm_model = f"gemini/{llm_model}"
        os.environ["GEMINI_API_KEY"] = api_key
        os.environ["GOOGLE_API_KEY"] = api_key
    elif llm_provider == "OpenAI":
        if not api_key:
            raise ValueError("Chybí API klíč pro OpenAI. Zadejte svůj API klíč (sk-...) v Nastavení -> AI a Chování.")
        os.environ["OPENAI_API_KEY"] = api_key
        if not (llm_model.startswith("openai/") or llm_model.startswith("gpt-") or llm_model.startswith("o1") or llm_model.startswith("o3") or llm_model.startswith("chatgpt-")):
            llm_model = f"openai/{llm_model}"
    elif llm_provider == "Anthropic":
        if not api_key:
            raise ValueError("Chybí API klíč pro Anthropic. Zadejte svůj API klíč (sk-ant-...) v Nastavení -> AI a Chování.")
        os.environ["ANTHROPIC_API_KEY"] = api_key
        if not (llm_model.startswith("anthropic/") or llm_model.startswith("claude-")):
            llm_model = f"anthropic/{llm_model}"
    elif llm_provider == "DeepSeek":
        if not api_key:
            raise ValueError("Chybí API klíč pro DeepSeek. Zadejte svůj API klíč v Nastavení -> AI a Chování.")
        os.environ["DEEPSEEK_API_KEY"] = api_key
        if not llm_model.startswith("deepseek/"):
            llm_model = f"deepseek/{llm_model}"
    elif llm_provider in ("Kimi / Moonshot AI", "Moonshot AI", "Kimi"):
        if not api_key:
            raise ValueError("Chybí API klíč pro Kimi / Moonshot AI. Zadejte svůj API klíč v Nastavení -> AI a Chování.")
        os.environ["MOONSHOT_API_KEY"] = api_key
        if not llm_model.startswith("moonshot/"):
            llm_model = f"moonshot/{llm_model}"
    elif llm_provider in ("Ollama", "Ollama (Lokální)", "Ollama (Local)"):
        if not llm_model.startswith("ollama/"):
            llm_model = f"ollama/{llm_model}"
            
    return full_user_context, llm_model, api_key

async def _run_matching(session: Session, application: Application) -> None:
    """Samostatné rychlé vyhodnocení shody (Match score & Reason) bez generování dopisu."""
    job = application.job_posting
    full_user_context, llm_model, api_key = _get_llm_setup(session, application)
    
    matcher = JobMatcher(model=llm_model, api_key=api_key if api_key else None)
    res = await matcher.evaluate_match(
        user_cv=full_user_context,
        job_desc=job.description or "Popis pozice není k dispozici.",
        job_title=job.title or job.company_name or "Neznámá pozice"
    )
    
    application.match_score = res.match_score
    application.match_reason = res.match_reason
    session.add(application)
    session.commit()

async def evaluate_single_match(application_id: int) -> None:
    """Samostatné vyhodnocení shody (Match Score & Reason) pro jednu pozici."""
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

            await _run_matching(session, application)

            if application.generated_body:
                application.status = ApplicationStatus.GENERATED
            else:
                application.status = ApplicationStatus.COMPLETED
            application.updated_at = datetime.now(timezone.utc)
            application.error_logs = None
            session.add(application)
            session.commit()
            logger.info(f"Úspěšně vyhodnocena shoda {application.match_score}% pro žádost {application_id}.")
        except Exception as e:
            logger.error(f"Chyba při vyhodnocování shody pro žádost {application_id}: {e}")
            if application.generated_body:
                application.status = ApplicationStatus.GENERATED
            else:
                application.status = ApplicationStatus.COMPLETED
            application.error_logs = f"Vyhodnocení shody selhalo: {str(e)}"
            application.updated_at = datetime.now(timezone.utc)
            session.add(application)
            session.commit()

async def evaluate_all_matches() -> int:
    """Hromadné vyhodnocení shody pro všechny pozice v databázi."""
    with Session(engine) as session:
        from sqlmodel import select
        apps = session.exec(select(Application)).all()
        app_ids = [app.id for app in apps]
    
    count = 0
    for app_id in app_ids:
        try:
            await evaluate_single_match(app_id)
            count += 1
        except Exception as e:
            logger.warning(f"Chyba při hromadném hodnocení žádosti {app_id}: {e}")
    return count

async def _run_llm_generation(session: Session, application: Application) -> None:
    """Vygenerování motivačního e-mailu pomocí LLM."""
    job = application.job_posting
    full_user_context, llm_model, api_key = _get_llm_setup(session, application)
                
    llm_generator = CoverLetterGenerator(model=llm_model, api_key=api_key if api_key else None)
    draft = await llm_generator.generate_email(
        user_cv=full_user_context,
        job_desc=job.description or "Popis pozice není k dispozici.",
        job_title=job.title or job.company_name or "Neznámá pozice"
    )
    
    # Sestavení výsledného e-mailu (Assembly)
    assembled_body = "\n\n".join([
        draft.osloveni,
        draft.uvod,
        draft.moje_zkusenosti,
        draft.tech_stack_shoda,
        draft.zaver_cta,
        draft.podpis
    ])
    
    # Pokud ještě nebylo spočítáno match_score, uložme ho také
    if application.match_score is None:
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
            
            # Po úspěšném scrapingu nastavíme stav na COMPLETED (dokončeno stažení inzerátu)
            application.status = ApplicationStatus.COMPLETED
            application.updated_at = datetime.now(timezone.utc)
            application.error_logs = None
            session.add(application)
            session.commit()
            logger.info(f"Úspěšně stažen inzerát pro žádost {application_id}. Scraping dokončen.")

            # Fáze 2: AI Analýza shody (pokud má uživatel nastavené podklady a platný klíč)
            user_prefs = session.get(UserPreferences, 1)
            raw_key = (user_prefs.llm_api_key or "").strip() if user_prefs else ""
            is_ollama = bool(user_prefs and user_prefs.llm_provider in ("Ollama", "Ollama (Lokální)", "Ollama (Local)"))
            has_api_key = is_ollama or bool(raw_key)
            has_profile = bool(user_prefs and (user_prefs.cv_file_path or user_prefs.full_name or user_prefs.industry or user_prefs.education))

            if has_api_key and has_profile:
                try:
                    logger.info(f"Automaticky spouštím AI vyhodnocení shody pro žádost {application_id}")
                    await _run_matching(session, application)
                    logger.info(f"Úspěšně automaticky vyhodnocena shoda {application.match_score}% pro žádost {application_id}.")
                except Exception as llm_err:
                    logger.warning(f"Automatické AI vyhodnocení pro žádost {application_id} selhalo: {llm_err}")
                    application.error_logs = f"Automatické AI hodnocení selhalo: {str(llm_err)}"
                    session.add(application)
                    session.commit()
            
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
            err_msg = str(e)
            if "API key not valid" in err_msg or "API_KEY_INVALID" in err_msg:
                friendly_error = "Neplatný API klíč: Poskytovatel AI odmítl zadaný klíč. Zkontrolujte prosím svůj API klíč v Nastavení -> AI a Chování (pro Google Gemini získejte klíč zdarma na aistudio.google.com)."
            elif "gen-lang-client" in err_msg or "Chybí podklady" in err_msg or "Chybí API klíč" in err_msg or "Neplatný API klíč" in err_msg:
                friendly_error = err_msg
            elif "AuthenticationError" in err_msg:
                friendly_error = f"Chyba autentizace AI: Zkontrolujte platnost svého API klíče v Nastavení -> AI a Chování ({err_msg})."
            else:
                friendly_error = f"Chyba při generování: {err_msg}"
                
            session.rollback()
            application.status = ApplicationStatus.FAILED
            application.error_logs = friendly_error
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
