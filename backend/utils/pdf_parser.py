import fitz
import os

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extrahuje veškerý text ze zadaného PDF souboru.
    
    Args:
        file_path (str): Cesta k PDF souboru.
        
    Returns:
        str: Extrahovaný text.
        
    Raises:
        FileNotFoundError: Pokud soubor neexistuje.
        ValueError: Pokud dojde k chybě při parsování PDF.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF soubor nenalezen na cestě: {file_path}")
        
    text = ""
    try:
        page_count = 0
        # fitz.open může vyhodit výjimku, pokud je soubor poškozený
        with fitz.open(file_path) as doc:
            page_count = len(doc)
            for page in doc:
                text += page.get_text()
        if page_count > 0 and not text.strip():
            raise ValueError("Nahraný PDF soubor obsahuje pouze naskenované obrázky bez čitelné textové vrstvy. Použijte prosím PDF vygenerované s textem nebo doplňte své údaje v profilu v Nastavení.")
        return text
    except Exception as e:
        raise ValueError(f"Chyba při extrakci textu z PDF: {str(e)}") from e
