from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
from database import get_session
from models import Application, JobPosting, ApplicationStatus, User
from orchestrator import process_job_application, generate_application_email, send_application_email

router = APIRouter(prefix="/api/applications", tags=["applications"])

class ApplicationCreate(BaseModel):
    url: str

class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus

class SendEmailRequest(BaseModel):
    recipient_email: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None

class ExploreRequest(BaseModel):
    count: int
    query: Optional[str] = ""
    sources: Optional[List[str]] = None

@router.post("/explore")
async def explore_jobs(explore_req: ExploreRequest, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    user = session.get(User, 1)
    if not user:
        user = User(first_name="Demo", last_name="User", email="demo@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)

    from scrapers.search import JobSearchScraper
    scraper = JobSearchScraper()
    job_urls = await scraper.search_jobs(
        query=explore_req.query, 
        count=explore_req.count,
        sources=explore_req.sources
    )

    if not job_urls:
        raise HTTPException(status_code=404, detail="Žádné pozice nebyly nalezeny pro zadané klíčové slovo.")

    created_apps = []
    
    for url in job_urls:
        job = session.exec(select(JobPosting).where(JobPosting.source_url == url)).first()
        if not job:
            job = JobPosting(source_url=url, title="Zatím nenačteno", company_name="Zatím nenačteno")
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
        created_apps.append(application.id)

    return {"message": f"Nalezeno {len(job_urls)} pozic. Spouštím analýzu.", "count": len(job_urls), "urls": job_urls}

@router.get("/", response_model=List[dict])
def get_applications(session: Session = Depends(get_session)):
    applications = session.exec(select(Application)).all()
    result = []
    for app in applications:
        job = app.job_posting
        result.append({
            "id": str(app.id),
            "title": job.title or "Zatím nenačteno",
            "company": job.company_name or "Zatím nenačteno",
            "description": job.description or "",
            "status": app.status.value.capitalize(),
            "dateAdded": app.created_at.strftime("%d.%m.%Y"),
            "match_score": app.match_score,
            "match_reason": app.match_reason,
            "generated_subject": app.generated_subject,
            "generated_body": app.generated_body,
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
    return {
        "id": str(app.id),
        "title": job.title or "Zatím nenačteno" if job else "Zatím nenačteno",
        "company": job.company_name or "Zatím nenačteno" if job else "Zatím nenačteno",
        "description": job.description or "" if job else "",
        "status": app.status.value.capitalize(),
        "dateAdded": app.created_at.strftime("%d.%m.%Y"),
        "match_score": app.match_score,
        "match_reason": app.match_reason,
        "generated_subject": app.generated_subject,
        "generated_body": app.generated_body,
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
