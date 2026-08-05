from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from database import engine
from models import UserPreferences
from schemas import PreferencesUpdate

router = APIRouter()

def get_session():
    with Session(engine) as session:
        yield session

@router.put("/api/settings", response_model=UserPreferences)
def update_settings(prefs: PreferencesUpdate, session: Session = Depends(get_session)):
    print(f"Received PUT /api/settings request. Payload: {prefs.model_dump()}")
    
    # Toto je lokální aplikace pro jednoho uživatele (Singleton vzor)
    user_prefs = session.get(UserPreferences, 1)
    
    if user_prefs:
        print("Existing preferences found, updating...")
        # Aktualizujeme existující záznam
        for key, value in prefs.model_dump().items():
            setattr(user_prefs, key, value)
    else:
        print("No existing preferences found, creating new record...")
        # Vytvoříme nový záznam pro prvního uživatele
        user_prefs = UserPreferences(id=1, **prefs.model_dump())
        
    session.add(user_prefs)
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
