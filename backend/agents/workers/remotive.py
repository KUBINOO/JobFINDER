import logging
from typing import List
from datetime import datetime, timezone
import httpx
from schemas_v2 import RawJobPayload
from agents.relevance import calculate_relevance
from .base import BaseRemoteWorker

logger = logging.getLogger(__name__)


class RemotiveWorker(BaseRemoteWorker):
    """Tier 1 Worker pro Remotive API (https://remotive.com/api/remote-jobs)."""

    def __init__(self):
        super().__init__(name="Remotive", timeout=12.0)
        self.api_url = "https://remotive.com/api/remote-jobs"

    async def fetch_jobs(
        self, 
        query: str = "", 
        limit: int = 15, 
        part_time_only: bool = False
    ) -> List[RawJobPayload]:
        params = {
            "limit": str(limit * 3)  # stáhneme více pro následné filtrování
        }
        if query.strip():
            params["search"] = query.strip()

        results: List[RawJobPayload] = []

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(self.api_url, params=params)
                if resp.status_code != 200:
                    logger.warning(f"Remotive API vrátilo status {resp.status_code}")
                    return []

                data = resp.json()
                jobs = data.get("jobs", [])
                if not isinstance(jobs, list):
                    return []

                for item in jobs:
                    title = item.get("title", "").strip()
                    company = item.get("company_name", "").strip()
                    url = item.get("url", "").strip()
                    desc = item.get("description", "").strip()
                    job_type = str(item.get("job_type", "")).lower()
                    location = item.get("candidate_required_location", "Worldwide")
                    tags = item.get("tags") or []
                    tags_clean = [str(t).lower() for t in tags]

                    # Filtrování relevance podle dotazu (Data Engineer vs Copywriter)
                    if query.strip():
                        rel_score = calculate_relevance(query, title, tags_clean, desc)
                        if rel_score < 0.5:
                            continue

                    # Filtrování na part-time / contract
                    if part_time_only:
                        is_pt = any(t in job_type for t in ["part_time", "contract", "freelance"]) or \
                                "part-time" in title.lower() or "contract" in title.lower()
                        if not is_pt:
                            continue

                    # Datum publikace
                    pub_date = None
                    date_val = item.get("publication_date")
                    if date_val:
                        try:
                            pub_date = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
                        except Exception:
                            pub_date = None

                    results.append(
                        RawJobPayload(
                            source_portal="Remotive",
                            source_url=url,
                            title=title,
                            company_name=company or "Remote Company",
                            description=desc,
                            raw_location=location,
                            raw_tags=[str(t).lower() for t in tags],
                            raw_salary=item.get("salary"),
                            apply_url=url,
                            published_at=pub_date
                        )
                    )

                    if len(results) >= limit:
                        break

        except Exception as e:
            logger.error(f"Chyba při stahování z Remotive: {e}")
            raise

        logger.info(f"Remotive vrátil {len(results)} pozic.")
        return results
