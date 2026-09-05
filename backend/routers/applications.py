from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
import os
import re
import unicodedata
from database import get_session
from models import Application, JobPosting, ApplicationStatus, User
from orchestrator import (
    process_job_application, 
    generate_application_email, 
    send_application_email,
    evaluate_single_match,
    evaluate_all_matches
)

router = APIRouter(prefix="/api/applications", tags=["applications"])

class ApplicationCreate(BaseModel):
    url: str

class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus

class SendEmailRequest(BaseModel):
    recipient_email: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None

class OutreachRequest(BaseModel):
    custom_focus: Optional[str] = None

class OutreachResponse(BaseModel):
    outreach_message: str
    word_count: int
    application_id: int

class CvGenerateResponse(BaseModel):
    status: str
    file_path: str
    page_count: int
    filename: str

from services.outreach_service import generate_and_save_cold_outreach
from services.cv_generator import generate_tailored_cv_for_application

import json

class ExploreRequest(BaseModel):
    count: int
    query: Optional[str] = ""
    sources: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    market: Optional[str] = "cz"  # "cz" | "global" | "hybrid"
    employment_type: Optional[str] = "ALL"  # "ALL" | "PART_TIME" | "CONTRACTOR"
    timezone: Optional[str] = "EMEA"  # "EMEA" | "WORLDWIDE"

@router.post("/explore")
async def explore_jobs(explore_req: ExploreRequest, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    user = session.get(User, 1)
    if not user:
        user = User(first_name="Demo", last_name="User", email="demo@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)

    created_apps = []

    # Rozvětvení podle zvoleného trhu
    if explore_req.market in ("global", "hybrid"):
        from agents.dispatcher import DispatcherAgent
        dispatcher = DispatcherAgent()
        state = await dispatcher.execute_search(
            query=explore_req.query or "",
            count=explore_req.count,
            market=explore_req.market,
            employment_type=explore_req.employment_type or "ALL",
            timezone_preference=explore_req.timezone or "EMEA_ONLY"
        )

        if not state.normalized_listings:
            raise HTTPException(status_code=404, detail="Žádné relevantní globální pozice nebyly nalezeny pro zadané filtry.")

        for item in state.normalized_listings:
            job = session.exec(select(JobPosting).where(JobPosting.source_url == item.source_url)).first()
            if not job:
                job = JobPosting(
                    source_url=item.source_url,
                    title=item.title,
                    company_name=item.company_name,
                    description=item.description_raw,
                    source_portal=item.source_portal,
                    employment_type=item.employment_type.value,
                    remote_policy=item.remote_policy.value,
                    timezone_region=item.timezone_region.value,
                    canonical_hash=item.canonical_id
                )
                session.add(job)
                session.commit()
                session.refresh(job)
            else:
                job.title = item.title
                job.company_name = item.company_name
                if item.description_raw:
                    job.description = item.description_raw
                job.source_portal = item.source_portal
                job.employment_type = item.employment_type.value
                job.timezone_region = item.timezone_region.value
                session.add(job)
                session.commit()

            application = session.exec(
                select(Application).where(Application.job_id == job.id).where(Application.user_id == user.id)
            ).first()
            if not application:
                application = Application(user_id=user.id, job_id=job.id, status=ApplicationStatus.PENDING)
            else:
                application.status = ApplicationStatus.PENDING
                application.error_logs = None

            session.add(application)
            session.commit()
            session.refresh(application)

            background_tasks.add_task(process_job_application, application.id)
            created_apps.append(application.id)

        return {
            "message": f"Nalezeno {len(state.normalized_listings)} globálních pozic. Spouštím analýzu a scoring.",
            "count": len(state.normalized_listings),
            "urls": [item.source_url for item in state.normalized_listings],
            "worker_metrics": state.worker_counts
        }

    # Stávající logika pro český trh
    from scrapers.search import JobSearchScraper
    async with JobSearchScraper() as scraper:
        search_results = await scraper.search_jobs(
            query=explore_req.query, 
            count=explore_req.count,
            sources=explore_req.sources,
            locations=explore_req.locations
        )

    if not search_results:
        raise HTTPException(status_code=404, detail="Žádné relevantní pozice nebyly nalezeny pro zadané klíčové slovo.")

    for item in search_results:
        job = session.exec(select(JobPosting).where(JobPosting.source_url == item.url)).first()
        if not job:
            job = JobPosting(
                source_url=item.url, 
                title=item.title or "Zatím nenačteno", 
                company_name=item.company or "Zatím nenačteno",
                source_portal=item.source or "CZ Portal"
            )
            session.add(job)
            session.commit()
            session.refresh(job)
        else:
            if (not job.title or job.title in ["Zatím nenačteno", "Neznámá pozice"]) and item.title:
                job.title = item.title
            if (not job.company_name or job.company_name in ["Zatím nenačteno", "Neznámá společnost"]) and item.company:
                job.company_name = item.company
            if item.source:
                job.source_portal = item.source
            session.add(job)
            session.commit()
        
        application = session.exec(select(Application).where(Application.job_id == job.id).where(Application.user_id == user.id)).first()
        if not application:
            application = Application(user_id=user.id, job_id=job.id, status=ApplicationStatus.PENDING)
        else:
            application.status = ApplicationStatus.PENDING
            application.error_logs = None

        session.add(application)
        session.commit()
        session.refresh(application)

        background_tasks.add_task(process_job_application, application.id)
        created_apps.append(application.id)

    return {
        "message": f"Nalezeno {len(search_results)} relevantních pozic. Spouštím analýzu.", 
        "count": len(search_results), 
        "urls": [item.url for item in search_results]
    }

@router.get("/", response_model=List[dict])
def get_applications(session: Session = Depends(get_session)):
    applications = session.exec(select(Application)).all()
    result = []
    for app in applications:
        job = app.job_posting
        
        pros_list = []
        cons_list = []
        skills_list = []
        if app.pros:
            try: pros_list = json.loads(app.pros)
            except Exception: pros_list = [app.pros]
        if app.cons:
            try: cons_list = json.loads(app.cons)
            except Exception: cons_list = [app.cons]
        if app.missing_skills:
            try: skills_list = json.loads(app.missing_skills)
            except Exception: skills_list = [app.missing_skills]

        result.append({
            "id": str(app.id),
            "title": job.title or "Zatím nenačteno",
            "company": job.company_name or "Zatím nenačteno",
            "description": job.description or "",
            "status": app.status.value.capitalize(),
            "dateAdded": app.created_at.strftime("%d.%m.%Y"),
            "match_score": app.match_score,
            "match_reason": app.match_reason,
            "pros": pros_list,
            "cons": cons_list,
            "missing_skills": skills_list,
            "part_time_viability": app.part_time_viability,
            "source_portal": job.source_portal or "CZ Portal",
            "employment_type": job.employment_type or "UNKNOWN",
            "remote_policy": job.remote_policy or "UNKNOWN",
            "timezone_region": job.timezone_region or "UNKNOWN",
            "generated_subject": app.generated_subject,
            "generated_body": app.generated_body,
            "outreach_message": app.outreach_message,
            "tailored_cv_path": app.tailored_cv_path,
            "error_logs": app.error_logs,
            "url": job.source_url if job else "",
            "source_url": job.source_url if job else "",
        })
    return result

@router.get("/{app_id}", response_model=dict)
def get_application(app_id: int, session: Session = Depends(get_session)):
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    job = app.job_posting

    pros_list = []
    cons_list = []
    skills_list = []
    if app.pros:
        try: pros_list = json.loads(app.pros)
        except Exception: pros_list = [app.pros]
    if app.cons:
        try: cons_list = json.loads(app.cons)
        except Exception: cons_list = [app.cons]
    if app.missing_skills:
        try: skills_list = json.loads(app.missing_skills)
        except Exception: skills_list = [app.missing_skills]

    return {
        "id": str(app.id),
        "title": job.title or "Zatím nenačteno" if job else "Zatím nenačteno",
        "company": job.company_name or "Zatím nenačteno" if job else "Zatím nenačteno",
        "description": job.description or "" if job else "",
        "status": app.status.value.capitalize(),
        "dateAdded": app.created_at.strftime("%d.%m.%Y"),
        "match_score": app.match_score,
        "match_reason": app.match_reason,
        "pros": pros_list,
        "cons": cons_list,
        "missing_skills": skills_list,
        "part_time_viability": app.part_time_viability,
        "source_portal": (job.source_portal if job else "CZ Portal") or "CZ Portal",
        "employment_type": (job.employment_type if job else "UNKNOWN") or "UNKNOWN",
        "remote_policy": (job.remote_policy if job else "UNKNOWN") or "UNKNOWN",
        "timezone_region": (job.timezone_region if job else "UNKNOWN") or "UNKNOWN",
        "generated_subject": app.generated_subject,
        "generated_body": app.generated_body,
        "outreach_message": app.outreach_message,
        "tailored_cv_path": app.tailored_cv_path,
        "error_logs": app.error_logs,
        "url": job.source_url if job else "",
        "source_url": job.source_url if job else "",
    }

@router.post("/")
def create_application(app_in: ApplicationCreate, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    user = session.get(User, 1)
    if not user:
        user = User(first_name="Demo", last_name="User", email="demo@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)

    job = session.exec(select(JobPosting).where(JobPosting.source_url == app_in.url)).first()
    if not job:
        job = JobPosting(source_url=app_in.url, title="Zatím nenačteno", company_name="Zatím nenačteno")
        session.add(job)
        session.commit()
        session.refresh(job)
    
    application = session.exec(select(Application).where(Application.job_id == job.id).where(Application.user_id == user.id)).first()
    if not application:
        application = Application(user_id=user.id, job_id=job.id, status=ApplicationStatus.PENDING)
    else:
        application.status = ApplicationStatus.PENDING
        application.error_logs = None

    session.add(application)
    session.commit()
    session.refresh(application)

    background_tasks.add_task(process_job_application, application.id)
    return application

@router.patch("/{app_id}")
def update_application_status(app_id: int, status_update: ApplicationStatusUpdate, session: Session = Depends(get_session)):
    application = session.get(Application, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    application.status = status_update.status
    session.add(application)
    session.commit()
    session.refresh(application)
    
    return {"message": "Status updated", "status": application.status.value.capitalize()}

@router.delete("/{app_id}")
def delete_application(app_id: int, session: Session = Depends(get_session)):
    application = session.get(Application, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
        
    session.delete(application)
    session.commit()
    return {"message": "Application deleted"}

@router.post("/{app_id}/match")
def match_single_application(app_id: int, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    application = session.get(Application, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Žádost nebyla nalezena")

    application.status = ApplicationStatus.GENERATING
    application.error_logs = None
    session.add(application)
    session.commit()
    session.refresh(application)

    background_tasks.add_task(evaluate_single_match, app_id)
    return {"message": "Vyhodnocování AI shody bylo spuštěno.", "status": "Generating"}

@router.post("/match-all")
async def match_all_applications(background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    applications = session.exec(select(Application)).all()
    if not applications:
        raise HTTPException(status_code=404, detail="Žádné pozice k vyhodnocení.")

    background_tasks.add_task(evaluate_all_matches)
    return {"message": f"Spuštěno hromadné vyhodnocování AI shody pro {len(applications)} pozic.", "count": len(applications)}

@router.post("/{app_id}/generate")
def generate_email_for_application(app_id: int, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    application = session.get(Application, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Žádost nebyla nalezena")

    application.status = ApplicationStatus.GENERATING
    application.error_logs = None
    session.add(application)
    session.commit()
    session.refresh(application)

    background_tasks.add_task(generate_application_email, app_id)
    return {"message": "Generování e-mailu pomocí AI bylo spuštěno.", "status": "Generating"}

@router.post("/{app_id}/send")
async def send_email_for_application(app_id: int, send_req: Optional[SendEmailRequest] = None, session: Session = Depends(get_session)):
    application = session.get(Application, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Žádost nebyla nalezena")

    recipient_email = send_req.recipient_email if send_req else None
    subject = send_req.subject if send_req else None
    body = send_req.body if send_req else None

    try:
        await send_application_email(app_id, recipient_email, subject, body)
        return {"message": "E-mail byl úspěšně odeslán přes SMTP.", "status": "Sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{app_id}/outreach", response_model=OutreachResponse)
async def generate_outreach_for_application(
    app_id: int, 
    outreach_req: Optional[OutreachRequest] = None, 
    session: Session = Depends(get_session)
):
    application = session.get(Application, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    custom_focus = outreach_req.custom_focus if outreach_req else None
    result = await generate_and_save_cold_outreach(
        session=session,
        application=application,
        custom_focus=custom_focus
    )
    return result

@router.post("/{app_id}/cv/generate", response_model=CvGenerateResponse)
def generate_cv_for_application(app_id: int, session: Session = Depends(get_session)):
    application = session.get(Application, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Žádost nebyla nalezena")

    try:
        result = generate_tailored_cv_for_application(session=session, application_id=app_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chyba při generování ATS CV: {str(e)}")

@router.get("/{app_id}/cv/download")
def download_cv_for_application(app_id: int, session: Session = Depends(get_session)):
    application = session.get(Application, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Žádost nebyla nalezena")

    target_file = application.tailored_cv_path
    full_path = None
    if target_file:
        if os.path.isabs(target_file):
            full_path = target_file
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            full_path = os.path.join(base_dir, target_file)

    if not full_path or not os.path.exists(full_path):
        try:
            res = generate_tailored_cv_for_application(session=session, application_id=app_id)
            full_path = res["file_path"]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Chyba při generování ATS CV: {str(e)}")

    job = application.job_posting
    company_raw = (job.company_name if job and job.company_name else "Company").strip()
    normalized_company = unicodedata.normalize('NFKD', company_raw).encode('ascii', 'ignore').decode('ascii')
    company_slug = re.sub(r'[^a-zA-Z0-9_\-]', '', normalized_company.replace(" ", "_")) or "Company"
    filename = f"CV_Jakub_Slavik_{company_slug}.pdf"

    return FileResponse(
        path=full_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.delete("/action/wipe")
def wipe_applications(session: Session = Depends(get_session)):
    # Delete all applications and job postings securely
    applications = session.exec(select(Application)).all()
    for app in applications:
        session.delete(app)
        
    jobs = session.exec(select(JobPosting)).all()
    for job in jobs:
        session.delete(job)
        
    session.commit()
    return {"message": "Historie žádostí byla úspěšně smazána."}
