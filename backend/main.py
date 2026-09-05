from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session
from database import engine, create_db_and_tables
from routers import settings, upload, applications
from sqlalchemy import text

# Inicializace databáze SQLite
create_db_and_tables()

# Migrace sloupců pro existující SQLite databázi
try:
    with engine.connect() as conn:
        cursor = conn.execute(text("PRAGMA table_info(application)"))
        cols = [row[1] for row in cursor.fetchall()]
        if cols and "outreach_message" not in cols:
            conn.execute(text("ALTER TABLE application ADD COLUMN outreach_message TEXT"))
            conn.commit()
        if cols and "tailored_cv_path" not in cols:
            conn.execute(text("ALTER TABLE application ADD COLUMN tailored_cv_path TEXT"))
            conn.commit()
except Exception:
    pass

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


