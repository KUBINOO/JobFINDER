import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
import aiofiles
from sqlmodel import Session
from database import engine
from models import UserPreferences

router = APIRouter()

def get_session():
    with Session(engine) as session:
        yield session

UPLOAD_DIR = "./uploads"

@router.post("/api/upload-cv")
async def upload_cv(file: UploadFile = File(...), session: Session = Depends(get_session)):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400, 
            detail="Nahraný soubor musí být ve formátu PDF."
        )
        
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    try:
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Chyba při ukládání souboru na disk: {str(e)}"
        )
        
    user_prefs = session.get(UserPreferences, 1)
    if not user_prefs:
        # Vytvoříme výchozí záznam, pokud ještě neexistuje
        user_prefs = UserPreferences(
            id=1,
            llm_provider="OpenAI",
            llm_model="gpt-4o",
            smtp_email="",
            smtp_password="",
            smtp_port=587,
            cv_file_path=file_path
        )
    else:
        user_prefs.cv_file_path = file_path
        
    session.add(user_prefs)
    try:
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"Chyba při ukládání cesty k souboru do databáze: {str(e)}"
        )
        
    return {"message": "Životopis byl úspěšně nahrán.", "file_path": file_path}
