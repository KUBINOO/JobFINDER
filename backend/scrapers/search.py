import logging
from selectolax.parser import HTMLParser
import httpx

logger = logging.getLogger(__name__)

class JobSearchScraper:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=15.0)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def search_jobs(self, query: str = "", count: int = 10) -> list[str]:
        """
        Vyhledá zadané klíčové slovo na jobs.cz a vrátí seznam URL adres (maximálně `count` inzerátů).
        """
        url = f"https://www.jobs.cz/prace/?q={query}"
        
        try:
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            tree = HTMLParser(response.text)
            
            job_links = []
            
            # Hledáme všechny odkazy na inzeráty (rpd)
            for a in tree.css("a"):
                href = a.attributes.get("href", "")
                if "jobs.cz/rpd/" in href or "jobs.cz/r/" in href:
                    # Chceme jen čisté URL bez parametrů searchId apod.
                    clean_url = href.split("?")[0]
                    if clean_url not in job_links:
                        job_links.append(clean_url)
                        
            # Oříznutí na požadovaný počet
            return job_links[:count]
            
        except Exception as e:
            logger.error(f"Chyba při hledání nabídek na jobs.cz: {e}")
            return []
