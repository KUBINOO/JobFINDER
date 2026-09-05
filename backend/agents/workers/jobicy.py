import logging
import re
from typing import List, Optional
from datetime import datetime, timezone
import email.utils
import httpx

from schemas_v2 import RawJobPayload
from agents.relevance import calculate_relevance
from .base import BaseRemoteWorker

logger = logging.getLogger(__name__)


class JobicyWorker(BaseRemoteWorker):
    """
    Tier 1 Worker pro oficiální Jobicy Remote Jobs API (https://jobicy.com/api/v2/remote-jobs).
    Poskytuje vysoce kvalitní, ověřené globální a evropské remote pozice.
    """

    def __init__(self):
        super().__init__(name="Jobicy", timeout=12.0)
        self.api_url = "https://jobicy.com/api/v2/remote-jobs"

    def _resolve_tag(self, query: str) -> Optional[str]:
        q_lower = query.lower()
        if "data" in q_lower:
            return "data"
        if "python" in q_lower:
            return "python"
        if "react" in q_lower:
            return "react"
        if "devops" in q_lower or "cloud" in q_lower or "sre" in q_lower:
            return "devops"
        if "qa" in q_lower or "test" in q_lower:
            return "qa"
        if "frontend" in q_lower or "front-end" in q_lower:
            return "frontend"
        if "backend" in q_lower or "back-end" in q_lower:
            return "backend"
        if "engineer" in q_lower or "developer" in q_lower:
            return "engineering"
        return None

    async def fetch_jobs(
        self, 
        query: str = "", 
        limit: int = 15, 
        part_time_only: bool = False
    ) -> List[RawJobPayload]:
        results: List[RawJobPayload] = []
        fetch_count = min(50, max(limit * 3, 25))

        params = {"count": str(fetch_count)}
        tag = self._resolve_tag(query)
        if tag:
            params["tag"] = tag

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(self.api_url, params=params)
                if resp.status_code != 200:
                    logger.warning(f"Jobicy API vrátilo status {resp.status_code}")
                    return []

                data = resp.json()
                jobs = data.get("jobs", [])
                if not isinstance(jobs, list):
                    return []

                candidates = []
                for item in jobs:
                    title = item.get("jobTitle", "").strip()
                    company = item.get("companyName", "").strip()
                    url = item.get("url", "").strip()
                    desc = item.get("jobDescription", "").strip()
                    geo = item.get("jobGeo", "").strip() or "Worldwide"
                    job_type = str(item.get("jobType", "")).lower()
                    industry = item.get("jobIndustry") or []
                    if isinstance(industry, list):
                        raw_tags = [str(t).lower() for t in industry]
                    else:
                        raw_tags = [str(industry).lower()]

                    # Filtrování relevance podle dotazu
                    rel_score = 1.0
                    if query.strip():
                        rel_score = calculate_relevance(query, title, raw_tags, desc)
                        if rel_score < 0.5:
                            continue

                    # Filtrování na part-time / contract
                    if part_time_only:
                        is_pt = any(t in job_type for t in ["part-time", "contract", "freelance", "intern"]) or \
                                "part-time" in title.lower() or "contract" in title.lower() or "freelance" in title.lower()
                        if not is_pt:
                            continue

                    # Parsování data publikace
                    pub_date = None
                    pub_str = item.get("pubDate")
                    if pub_str:
                        try:
                            pub_tuple = email.utils.parsedate_to_datetime(pub_str)
                            pub_date = pub_tuple.astimezone(timezone.utc)
                        except Exception:
                            pub_date = None

                    # Plat pokud je dostupný
                    sal_min = item.get("annualSalaryMin")
                    sal_max = item.get("annualSalaryMax")
                    cur = item.get("salaryCurrency") or "USD"
                    salary_str = None
                    if sal_min or sal_max:
                        salary_str = f"${sal_min or 0} - ${sal_max or 0} {cur}/year"

                    payload = RawJobPayload(
                        source_portal="Jobicy",
                        source_url=url,
                        title=title,
                        company_name=company or "Remote Company",
                        description=desc,
                        raw_location=geo,
                        raw_tags=raw_tags,
                        raw_salary=salary_str,
                        apply_url=url,
                        published_at=pub_date
                    )
                    candidates.append((rel_score, payload))

                # Seřadit podle skóre relevance sestupně (nejlepší shody první)
                candidates.sort(key=lambda x: x[0], reverse=True)
                results = [c[1] for c in candidates[:limit]]

        except Exception as e:
            logger.error(f"Chyba při stahování z Jobicy: {e}")
            raise

        logger.info(f"Jobicy vrátil {len(results)} pozic.")
        return results
