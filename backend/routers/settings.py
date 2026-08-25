from typing import Optional
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
    # Automatická migrace zastaralého gemini-1.5-flash na aktuální gemini-3.7-flash
    if user_prefs.llm_model == "gemini-1.5-flash":
        user_prefs.llm_model = "gemini-3.7-flash"
        session.add(user_prefs)
        session.commit()
        session.refresh(user_prefs)
    return user_prefs

@router.delete("/api/settings/reset")
def reset_settings(session: Session = Depends(get_session)):
    """Resetuje uživatelská nastavení a profil, aby se znovu zobrazil úvodní Onboarding Wizard."""
    user_prefs = session.get(UserPreferences, 1)
    if user_prefs:
        session.delete(user_prefs)
    session.commit()
    return {"message": "Nastavení a profil byly úspěšně resetovány. Můžete projít onboardingem."}



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

class LlmTestRequest(BaseModel):
    provider: str = "Google Gemini"
    model: str = "gemini-3.7-flash"
    api_key: Optional[str] = None
    ollama_host: Optional[str] = None

@router.post("/api/settings/test-llm")
async def test_llm(req: LlmTestRequest):
    from litellm import acompletion
    
    model_name = req.model.strip() if req.model else "gemini-3.7-flash"
    if model_name == "gemini-1.5-flash":
        model_name = "gemini-3.7-flash"
    api_key = req.api_key.strip() if req.api_key else ""
    
    if req.provider == "Google Gemini":
        if not api_key:
            raise HTTPException(
                status_code=400, 
                detail="Chybí API klíč pro Google Gemini. Zadejte platný API klíč z Google AI Studio."
            )
        if not model_name.startswith("gemini/"):
            model_name = f"gemini/{model_name}"
    elif req.provider == "OpenAI":
        if not api_key:
            raise HTTPException(status_code=400, detail="Chybí API klíč pro OpenAI (začíná na sk-...).")
        if not (model_name.startswith("openai/") or model_name.startswith("gpt-") or model_name.startswith("o1") or model_name.startswith("o3") or model_name.startswith("chatgpt-")):
            model_name = f"openai/{model_name}"
    elif req.provider == "Anthropic":
        if not api_key:
            raise HTTPException(status_code=400, detail="Chybí API klíč pro Anthropic (začíná na sk-ant-...).")
        if not (model_name.startswith("anthropic/") or model_name.startswith("claude-")):
            model_name = f"anthropic/{model_name}"
    elif req.provider == "DeepSeek":
        if not api_key:
            raise HTTPException(status_code=400, detail="Chybí API klíč pro DeepSeek (začíná na sk-...).")
        if not model_name.startswith("deepseek/"):
            model_name = f"deepseek/{model_name}"
    elif req.provider in ("Kimi / Moonshot AI", "Moonshot AI", "Kimi"):
        if not api_key:
            raise HTTPException(status_code=400, detail="Chybí API klíč pro Kimi / Moonshot AI.")
        if not model_name.startswith("moonshot/"):
            model_name = f"moonshot/{model_name}"
    elif req.provider in ("Ollama", "Ollama (Lokální)", "Ollama (Local)"):
        if not model_name.startswith("ollama/"):
            model_name = f"ollama/{model_name}"
            
    try:
        kwargs = {
            "model": model_name,
            "messages": [{"role": "user", "content": "Odpovez pouze jednim slovem: OK"}],
            "max_tokens": 10,
        }
        if api_key:
            kwargs["api_key"] = api_key
        if req.ollama_host:
            kwargs["api_base"] = req.ollama_host
            
        resp = await acompletion(**kwargs)
        content = resp.choices[0].message.content or "OK"
        return {"message": f"Spojení s AI ({req.provider} - {req.model}) funguje bezchybně! (Odpověď: {content.strip()})"}
    except Exception as e:
        err_str = str(e)
        if "API key not valid" in err_str or "API_KEY_INVALID" in err_str:
            raise HTTPException(
                status_code=400, 
                detail="Neplatný API klíč: Poskytovatel odmítl zadaný klíč. Ujistěte se, že používáte platný API klíč pro danou službu."
            )
        if "AuthenticationError" in err_str:
            raise HTTPException(status_code=400, detail=f"Chyba autentizace AI: {err_str}")
        raise HTTPException(status_code=400, detail=f"Chyba při komunikaci s AI ({model_name}): {err_str}")
