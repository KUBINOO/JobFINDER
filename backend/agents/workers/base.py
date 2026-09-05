import logging
from abc import ABC, abstractmethod
from typing import List, Optional
import httpx
from schemas_v2 import RawJobPayload

logger = logging.getLogger(__name__)


class BaseRemoteWorker(ABC):
    """Abstraktní bázová třída pro všechny globální API a RSS workery."""

    def __init__(self, name: str, timeout: float = 10.0):
        self.name = name
        self.timeout = timeout
        self.headers = {
            "User-Agent": "JobFinderBot/2.0 (+https://github.com/desktop-jobfinder; contact@example.com)",
            "Accept": "application/json, application/xml, text/xml, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    @abstractmethod
    async def fetch_jobs(
        self, 
        query: str = "", 
        limit: int = 15, 
        part_time_only: bool = False
    ) -> List[RawJobPayload]:
        """Stáhne surové nabídky ze zadaného zdroje."""
        pass
