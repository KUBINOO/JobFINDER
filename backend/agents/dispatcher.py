import asyncio
import logging
import uuid
from typing import List, Optional, Dict
from datetime import datetime, timezone

from schemas_v2 import RawJobPayload, JobListing
from .state import AgentExecutionState
from .normalizer import NormalizationAgent
from .workers import (
    RemoteOKWorker, 
    RemotiveWorker, 
    WeWorkRemotelyWorker, 
    ArbeitnowWorker,
    JobicyWorker
)

logger = logging.getLogger(__name__)


class DispatcherAgent:
    """
    Agent 1: Orchestration & Dispatcher Agent
    Řídí paralelní exekuci scraperů a API consumerů, hlídá SLA a timeouty
    a předává data normalizačnímu agentovi.
    """

    def __init__(self):
        self.global_workers = [
            RemoteOKWorker(),
            RemotiveWorker(),
            WeWorkRemotelyWorker(),
            ArbeitnowWorker(),
            JobicyWorker(),
        ]

    async def execute_search(
        self,
        query: str = "",
        count: int = 15,
        market: str = "global",
        employment_type: str = "ALL",
        timezone_preference: str = "EMEA_ONLY"
    ) -> AgentExecutionState:
        run_id = str(uuid.uuid4())[:8]
        state = AgentExecutionState(
            run_id=run_id,
            query=query,
            market=market.lower(),
            requested_count=count,
            status="DISPATCHING"
        )

        part_time_only = employment_type.upper() in ("PART_TIME", "CONTRACTOR", "PARTTIME", "CONTRACT")
        per_worker_limit = max(count // 2, 8)

        tasks = []
        worker_names = []

        # 1. Spuštění globálních API workerů
        if state.market in ("global", "hybrid"):
            for w in self.global_workers:
                tasks.append(
                    asyncio.wait_for(
                        w.fetch_jobs(
                            query=query, 
                            limit=per_worker_limit, 
                            part_time_only=part_time_only
                        ),
                        timeout=14.0
                    )
                )
                worker_names.append(w.name)

        # 2. Spuštění českého scraperu (pokud je zvolen trh "cz" nebo "hybrid")
        if state.market in ("cz", "hybrid"):
            from scrapers.search import JobSearchScraper
            async def run_cz():
                async with JobSearchScraper() as cz_s:
                    cz_results = await cz_s.search_jobs(query=query, count=count)
                    # Převod do RawJobPayload
                    raw_cz = []
                    for r in cz_results:
                        raw_cz.append(
                            RawJobPayload(
                                source_portal=r.source,
                                source_url=r.url,
                                title=r.title,
                                company_name=r.company,
                                description="", # Dočte se v detailu
                                raw_location="Česká republika",
                                raw_tags=["cz", "local"],
                                apply_url=r.url
                            )
                        )
                    return raw_cz

            tasks.append(asyncio.wait_for(run_cz(), timeout=18.0))
            worker_names.append("CzechJobScrapers")

        logger.info(f"[{run_id}] Spouštím {len(tasks)} workerů paralelně pro dotaz: '{query}', trh: '{market}'")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_raw_payloads: List[RawJobPayload] = []

        for name, res in zip(worker_names, results):
            if isinstance(res, Exception):
                logger.warning(f"[{run_id}] Worker {name} selhal: {res}")
                state.record_worker_failure(name, res)
            else:
                count_found = len(res)
                state.record_worker_success(name, count_found)
                all_raw_payloads.extend(res)
                logger.info(f"[{run_id}] Worker {name} úspěšně dodal {count_found} pozic.")

        state.raw_payloads = all_raw_payloads
        state.status = "NORMALIZING"

        # 3. Normalizace a deduplikace s kontrolou relevance
        normalizer = NormalizationAgent(timezone_preference=timezone_preference)
        normalized = normalizer.normalize_and_deduplicate(
            all_raw_payloads, 
            query=query,
            part_time_only=part_time_only
        )

        state.normalized_listings = normalized[:count]
        state.status = "COMPLETED"
        logger.info(
            f"[{run_id}] Dokončeno. Z {len(all_raw_payloads)} surových nabídek vzniklo "
            f"{len(state.normalized_listings)} unikátních normalizovaných pozic."
        )

        return state
