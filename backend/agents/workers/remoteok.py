import re
import logging
from typing import List
from datetime import datetime, timezone
import httpx
from schemas_v2 import RawJobPayload
from agents.relevance import calculate_relevance
from .base import BaseRemoteWorker

logger = logging.getLogger(__name__)


class RemoteOKWorker(BaseRemoteWorker):
    """Tier 1 Worker pro RemoteOK API (https://remoteok.com/api)."""

    def __init__(self):
        super().__init__(name="RemoteOK", timeout=12.0)
        self.api_url = "https://remoteok.com/api"

    async def fetch_jobs(
        self, 
        query: str = "", 
        limit: int = 15, 
        part_time_only: bool = False
    ) -> List[RawJobPayload]:
        params = {}
        
        # RemoteOK podporuje jednoduché tagy (např. data, engineer, dev, python)
        COMMON_TAGS = {"data", "engineer", "dev", "python", "react", "golang", "backend", "frontend", "devops", "cloud", "sql"}
        q_lower = query.strip().lower()
        words = [w for w in re.split(r"\s+", q_lower) if len(w) >= 2]

        chosen_tag = None
        for w in words:
            if w in COMMON_TAGS:
                chosen_tag = w
                break

        if chosen_tag:
            params["tag"] = chosen_tag
        elif part_time_only:
            params["tag"] = "part-time"

        results: List[RawJobPayload] = []

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(self.api_url, params=params)
                if resp.status_code != 200:
                    logger.warning(f"RemoteOK API vrátilo status {resp.status_code}")
                    return []

                data = resp.json()
                if not isinstance(data, list):
                    return []

                for item in data:
                    # První položka v RemoteOK API bývá legální disclaimer
                    if not isinstance(item, dict) or "position" not in item:
                        continue

                    title = item.get("position", "").strip()
                    company = item.get("company", "").strip()
                    url = item.get("url", "").strip()
                    desc = item.get("description", "").strip()
                    tags = item.get("tags", [])
                    if isinstance(tags, list):
                        tags_cleaned = [str(t).lower() for t in tags]
                    else:
                        tags_cleaned = []

                    # Sémantická relevance inzerátu
                    if query.strip():
                        rel_score = calculate_relevance(query, title, tags_cleaned, desc)
                        if rel_score < 0.5:
                            continue

                    # Pokud je vyžadován part-time a není v tagu, zkontrolujeme tagy nebo text
                    if part_time_only:
                        is_pt = any("part-time" in t or "contract" in t for t in tags_cleaned) or \
                                "part-time" in title.lower() or "part-time" in desc.lower() or "contract" in desc.lower()
                        if not is_pt:
                            continue

                    # Pokud máme query, zkontrolujeme relevanci v title nebo tags
                    if query.strip():
                        q_words = query.lower().split()
                        matches_query = any(w in title.lower() or any(w in t for t in tags_cleaned) for w in q_words)
                        if not matches_query:
                            continue

                    # Extrakce platu pokud existuje
                    salary_str = None
                    sal_min = item.get("salary_min")
                    sal_max = item.get("salary_max")
                    if sal_min or sal_max:
                        salary_str = f"${sal_min or 0} - ${sal_max or 0} USD/year"

                    # Datum publikace
                    pub_date = None
                    date_val = item.get("date")
                    if date_val:
                        try:
                            pub_date = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
                        except Exception:
                            pub_date = None

                    results.append(
                        RawJobPayload(
                            source_portal="RemoteOK",
                            source_url=url or f"https://remoteok.com/l/{item.get('id', '')}",
                            title=title,
                            company_name=company or "Remote Company",
                            description=desc,
                            raw_location=item.get("location") or "Worldwide",
                            raw_tags=tags_cleaned,
                            raw_salary=salary_str,
                            apply_url=item.get("apply_url") or url,
                            published_at=pub_date
                        )
                    )

                    if len(results) >= limit:
                        break

        except Exception as e:
            logger.error(f"Chyba při stahování z RemoteOK: {e}")
            raise

        logger.info(f"RemoteOK vrátil {len(results)} pozic.")
        return results
