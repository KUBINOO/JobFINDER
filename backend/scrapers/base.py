import logging
from abc import ABC, abstractmethod
from selectolax.parser import HTMLParser

from schemas import ScrapedJob
from client import StealthClient

logger = logging.getLogger(__name__)

class ScrapingError(Exception):
    """Custom exception raised when critical data cannot be scraped."""
    pass

class BaseJobScraper(ABC):
    def __init__(self, client: StealthClient = None):
        self.client = client or StealthClient()

    @abstractmethod
    async def extract_job_details(self, url: str) -> ScrapedJob:
        """Extract job details from the given URL."""
        pass

class AbstractCSSScraper(BaseJobScraper):
    """
    Generic scraper implementation using selectolax to parse CSS selectors.
    Concrete classes only need to define the selectors.
    """
    TITLE_SELECTOR: str = "h1"
    COMPANY_SELECTOR: str = ".company"
    DESCRIPTION_SELECTOR: str = ".description"

    async def extract_job_details(self, url: str) -> ScrapedJob:
        try:
            response = await self.client.get(url)
            tree = HTMLParser(response.text)
            
            title_node = tree.css_first(self.TITLE_SELECTOR)
            company_node = tree.css_first(self.COMPANY_SELECTOR)
            desc_node = tree.css_first(self.DESCRIPTION_SELECTOR)

            if not title_node:
                raise ScrapingError(f"Title not found for url: {url}")

            title = title_node.text(strip=True)
            company = company_node.text(strip=True) if company_node else "Unknown"
            description = desc_node.text(strip=True) if desc_node else ""

            return ScrapedJob(
                source_url=url, # type: ignore
                title=title,
                company_name=company,
                description=description
            )
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            if isinstance(e, ScrapingError):
                raise
            raise ScrapingError(f"Failed to scrape {url}") from e
