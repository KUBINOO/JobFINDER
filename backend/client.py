import asyncio
import random
import logging
from typing import Any
from curl_cffi.requests import AsyncSession, Response
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, wait_random

logger = logging.getLogger(__name__)

class StealthClient:
    def __init__(self, impersonate: str = "chrome110", delay_min: float = 1.0, delay_max: float = 3.0):
        self.impersonate = impersonate
        self.delay_min = delay_min
        self.delay_max = delay_max

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10) + wait_random(0, 2),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def get(self, url: str, **kwargs: Any) -> Response:
        # Dynamic delay based on user settings to avoid rate limits
        min_d = max(0.1, float(self.delay_min or 1.0))
        max_d = max(min_d, float(self.delay_max or 3.0))
        await asyncio.sleep(random.uniform(min_d, max_d))
        
        async with AsyncSession(impersonate=self.impersonate) as session:
            logger.debug(f"Fetching {url}")
            response = await session.get(url, **kwargs)
            if response.status_code >= 400:
                raise Exception(f"HTTP Error {response.status_code} for url: {url}")
            return response
