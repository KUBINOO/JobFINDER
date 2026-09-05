import logging
import xml.etree.ElementTree as ET
from typing import List
from datetime import datetime, timezone
import email.utils
import httpx
from schemas_v2 import RawJobPayload
from agents.relevance import calculate_relevance
from .base import BaseRemoteWorker

logger = logging.getLogger(__name__)


class WeWorkRemotelyWorker(BaseRemoteWorker):
    """Tier 1 Worker pro We Work Remotely veřejný RSS feed."""

    def __init__(self):
        super().__init__(name="WeWorkRemotely", timeout=12.0)
        self.rss_urls = [
            "https://weworkremotely.com/categories/remote-programming-jobs.rss",
            "https://weworkremotely.com/remote-jobs.rss",
            "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
        ]

    async def fetch_jobs(
        self, 
        query: str = "", 
        limit: int = 15, 
        part_time_only: bool = False
    ) -> List[RawJobPayload]:
        results: List[RawJobPayload] = []

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                for rss_url in self.rss_urls:
                    if len(results) >= limit:
                        break

                    resp = await client.get(rss_url)
                    if resp.status_code != 200:
                        logger.warning(f"WWR RSS vrátil status {resp.status_code} pro {rss_url}")
                        continue

                    try:
                        root = ET.fromstring(resp.content)
                    except Exception as parse_err:
                        logger.warning(f"Chyba při parsování RSS z {rss_url}: {parse_err}")
                        continue

                    channel = root.find("channel")
                    if channel is None:
                        continue

                    for item in channel.findall("item"):
                        raw_title = item.findtext("title", "").strip()
                        link = item.findtext("link", "").strip()
                        desc = item.findtext("description", "").strip()
                        pub_date_str = item.findtext("pubDate", "")

                        # WWR titulek bývá ve tvaru: "Firma: Název Pozice"
                        company = "Remote Company"
                        title = raw_title
                        if ":" in raw_title:
                            parts = raw_title.split(":", 1)
                            company = parts[0].strip()
                            title = parts[1].strip()

                        # Filtrování na part-time
                        if part_time_only:
                            is_pt = any(t in raw_title.lower() or t in desc.lower() for t in ["part-time", "contract", "freelance", "hourly"])
                            if not is_pt:
                                continue

                        # Dotaz filtr sémantické relevance
                        if query.strip():
                            rel = calculate_relevance(query, title, tags=["remote", "tech"], snippet=desc)
                            if rel < 0.5:
                                continue

                        # Datum publikace
                        pub_date = None
                        if pub_date_str:
                            try:
                                parsed_tuple = email.utils.parsedate_to_datetime(pub_date_str)
                                pub_date = parsed_tuple.astimezone(timezone.utc)
                            except Exception:
                                pub_date = None

                        results.append(
                            RawJobPayload(
                                source_portal="WeWorkRemotely",
                                source_url=link,
                                title=title,
                                company_name=company,
                                description=desc,
                                raw_location="Worldwide / Remote",
                                raw_tags=["remote", "programming"],
                                apply_url=link,
                                published_at=pub_date
                            )
                        )

                        if len(results) >= limit:
                            break

        except Exception as e:
            logger.error(f"Chyba při stahování z WeWorkRemotely: {e}")
            raise

        logger.info(f"WeWorkRemotely vrátil {len(results)} pozic.")
        return results
