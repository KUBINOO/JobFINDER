from urllib.parse import urlparse
from scrapers.base import BaseJobScraper
from scrapers.providers import (
    JobsCzScraper,
    PraceCzScraper,
    VolnamistaScraper,
    ProfesiaScraper,
    StartupJobsScraper
)

def get_scraper(url: str) -> BaseJobScraper:
    domain = urlparse(url).netloc.lower()
    
    if "startupjobs" in domain:
        return StartupJobsScraper()
    elif "prace.cz" in domain:
        return PraceCzScraper()
    elif "volnamista.cz" in domain:
        return VolnamistaScraper()
    elif "profesia.cz" in domain:
        return ProfesiaScraper()
    elif "jobs.cz" in domain:
        return JobsCzScraper()
    else:
        raise ValueError(f"No scraper available for domain: {domain}")
