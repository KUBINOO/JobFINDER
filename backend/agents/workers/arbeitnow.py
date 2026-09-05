import logging
from typing import List
from datetime import datetime, timezone
import httpx
from schemas_v2 import RawJobPayload
from agents.relevance import calculate_relevance
from .base import BaseRemoteWorker

logger = logging.getLogger(__name__)


class ArbeitnowWorker(BaseRemoteWorker):
    """Tier 1 Worker pro Arbeitnow API (https://www.arbeitnow.com/api/job-board-api)."""

    def __init__(self):
        super().__init__(name="Arbeitnow", timeout=12.0)
        self.api_url = "https://www.arbeitnow.com/api/job-board-api"

    async def fetch_jobs(
        self, 
        query: str = "", 
        limit: int = 15, 
        part_time_only: bool = False
    ) -> List[RawJobPayload]:
        results: List[RawJobPayload] = []

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(self.api_url)
                if resp.status_code != 200:
                    logger.warning(f"Arbeitnow API vrátilo status {resp.status_code}")
                    return []

                data = resp.json()
                items = data.get("data", [])
                if not isinstance(items, list):
                    return []

                for item in items:
                    # Filtrujeme pouze remote nabídky
                    is_remote = item.get("remote", False)
                    if not is_remote:
                        continue

                    title = item.get("title", "").strip()
                    company = item.get("company_name", "").strip()
                    url = item.get("url", "").strip()
                    desc = item.get("description", "").strip()
                    job_types = [str(j).lower() for j in (item.get("job_types") or [])]
                    tags = [str(t).lower() for t in (item.get("tags") or [])]

                    # Filtrování na part-time / contract
                    if part_time_only:
                        is_pt = any(t in job_types for t in ["part-time", "contract", "freelance", "student"]) or \
                                "part-time" in title.lower() or "contract" in title.lower() or "student" in title.lower()
                        if not is_pt:
                            continue

                    # Filtrování dotazu pomocí sémantické relevance
                    if query.strip():
                        rel = calculate_relevance(query, title, tags=tags + job_types, snippet=desc)
                        if rel < 0.5:
                            continue

                    # Datum publikace (timestamp)
                    pub_date = None
                    created_at = item.get("created_at")
                    if isinstance(created_at, (int, float)):
                        try:
                            pub_date = datetime.fromtimestamp(created_at, tz=timezone.utc)
                        except Exception:
                            pub_date = None

                    results.append(
                        RawJobPayload(
                            source_portal="Arbeitnow (EU Remote)",
                            source_url=url,
                            title=title,
                            company_name=company or "European Tech",
                            description=desc,
                            raw_location=item.get("location") or "Europe / Remote",
                            raw_tags=tags + job_types,
                            apply_url=url,
                            published_at=pub_date
                        )
                    )

                    if len(results) >= limit:
                        break

        except Exception as e:
            logger.error(f"Chyba při stahování z Arbeitnow: {e}")
            raise

        logger.info(f"Arbeitnow vrátil {len(results)} pozic.")
        return results
