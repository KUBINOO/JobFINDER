import os
import re
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
import aiofiles
from sqlmodel import Session
from database import get_session
from models import UserPreferences

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

@router.post("/api/upload-cv")
async def upload_cv(file: UploadFile = File(...), session: Session = Depends(get_session)):
    # Validate PDF content type or extension
    is_pdf = (file.content_type == "application/pdf") or (file.filename and file.filename.lower().endswith(".pdf"))
    if not is_pdf:
        raise HTTPException(
            status_code=400, 
            detail="Nahraný soubor musí být ve formátu PDF."
        )
        
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Sanitize filename for safe disk and DB storage
    safe_name = os.path.basename(file.filename or "cv.pdf")
    safe_name = re.sub(r'[^\w\.\-\_]', '_', safe_name)
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"
        
    file_path = os.path.abspath(os.path.join(UPLOAD_DIR, safe_name))
    
    try:
        MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail="Velikost souboru přesahuje povolený limit 15 MB."
            )
        async with aiofiles.open(file_path, 'wb') as out_file:
            await out_file.write(content)
    except HTTPException:
        raise
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
            llm_provider="Google Gemini",
            llm_model="gemini-3.7-flash",
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
        session.refresh(user_prefs)
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"Chyba při ukládání cesty k souboru do databáze: {str(e)}"
        )
        
    return {"message": "Životopis byl úspěšně nahrán.", "file_path": file_path}

