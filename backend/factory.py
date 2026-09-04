from typing import Optional
from urllib.parse import urlparse
from scrapers.base import BaseJobScraper
from client import StealthClient
from scrapers.providers import (
    CzechJobScraper,
    JobsCzScraper,
    PraceCzScraper,
    VolnamistaScraper,
    ProfesiaScraper,
    StartupJobsScraper
)

def get_scraper(url: str, client: Optional[StealthClient] = None) -> BaseJobScraper:
    domain = urlparse(url).netloc.lower()
    
    if "startupjobs" in domain:
        return StartupJobsScraper(client=client)
    elif "prace.cz" in domain:
        return PraceCzScraper(client=client)
    elif "volnamista.cz" in domain:
        return VolnamistaScraper(client=client)
    elif "profesia.cz" in domain:
        return ProfesiaScraper(client=client)
    elif "jobs.cz" in domain:
        return JobsCzScraper(client=client)
    else:
        # Generický scraper s podporou JSON-LD, meta tagů a Jina AI pro libovolné weby
        return CzechJobScraper(client=client)
