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
        # fitz.open může vyhodit výjimku, pokud je soubor poškozený
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text()
        return text
    except Exception as e:
        raise ValueError(f"Chyba při extrakci textu z PDF: {str(e)}") from e
