from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
from database import engine, create_db_and_tables
from routers import settings, upload, applications

# Initialize SQLite database tables
create_db_and_tables()

app = FastAPI(title="Job Application Automation API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrace routerů
app.include_router(settings.router)
app.include_router(upload.router)
app.include_router(applications.router)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "API is running"}

def process_job_application(job_id: int):
    # Long-running job application logic runs here locally
    print(f"Background task started for job {job_id}...")
    # Add automation, browser interaction, or API logic here
    print(f"Background task finished for job {job_id}.")

@app.post("/jobs/automate")
def automate_job(background_tasks: BackgroundTasks):
    # Create job tracking record in DB and get its ID (mocked for now)
    job_id = 1
    
    # Enqueue native FastAPI background task
    background_tasks.add_task(process_job_application, job_id)
    return {"message": "Job automation started in the background", "job_id": job_id}


