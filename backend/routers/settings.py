from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from database import get_session
from models import UserPreferences, User
from schemas import PreferencesUpdate

router = APIRouter()

@router.put("/api/settings", response_model=UserPreferences)
def update_settings(prefs: PreferencesUpdate, session: Session = Depends(get_session)):
    dump_data = prefs.model_dump(exclude_unset=True)
    print(f"Received PUT /api/settings request. Payload: {dump_data}")
    
    # Toto je lokální aplikace pro jednoho uživatele (Singleton vzor)
    user_prefs = session.get(UserPreferences, 1)
    
    if user_prefs:
        print("Existing preferences found, updating...")
        # Aktualizujeme existující záznam
        for key, value in dump_data.items():
            if value is not None or key not in ("cv_file_path",):
                setattr(user_prefs, key, value)
    else:
        print("No existing preferences found, creating new record...")
        # Vytvoříme nový záznam pro prvního uživatele
        user_prefs = UserPreferences(id=1, **dump_data)
        
    session.add(user_prefs)
    
    # Synchronizujeme také User(id=1) pro vazby v Application
    user = session.get(User, 1)
    full_name = prefs.full_name or ""
    parts = full_name.strip().split(" ", 1)
    first_name = parts[0] if parts and parts[0] else "Uživatel"
    last_name = parts[1] if len(parts) > 1 else ""
    user_email = prefs.smtp_email if (prefs.smtp_email and "@" in prefs.smtp_email) else "demo@example.com"
    
    if not user:
        user = User(id=1, first_name=first_name, last_name=last_name, email=user_email)
    else:
        if prefs.full_name:
            user.first_name = first_name
            user.last_name = last_name
        if prefs.smtp_email and "@" in prefs.smtp_email:
            user.email = user_email
    session.add(user)
    
    try:
        session.commit()
        session.refresh(user_prefs)
        return user_prefs
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"Chyba při ukládání nastavení do databáze: {str(e)}"
        )

@router.get("/api/settings", response_model=UserPreferences)
def get_settings(session: Session = Depends(get_session)):
    user_prefs = session.get(UserPreferences, 1)
    if not user_prefs:
        raise HTTPException(status_code=404, detail="Nastavení nenalezeno")
    return user_prefs


from pydantic import BaseModel
import aiosmtplib

class SmtpTestRequest(BaseModel):
    host: str = "smtp.gmail.com"
    port: int
    username: str
    password: str

@router.post("/api/settings/test-smtp")
async def test_smtp(req: SmtpTestRequest):
    try:
        smtp = aiosmtplib.SMTP(
            hostname=req.host, 
            port=req.port,
            use_tls=req.port == 465,
            start_tls=req.port == 587
        )
        await smtp.connect()
        await smtp.login(req.username, req.password)
        await smtp.quit()
        return {"message": "Připojení k SMTP bylo úspěšné!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Chyba SMTP: {str(e)}")
