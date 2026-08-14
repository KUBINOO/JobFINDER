import random
import asyncio
import logging
import urllib.parse
import re
from typing import List, Dict, Optional
import httpx
from selectolax.parser import HTMLParser

logger = logging.getLogger(__name__)

class JobSearchScraper:
    """
    Vyhledávač nabídek práce napříč podporovanými českými portály:
    - Jobs.cz
    - Prace.cz
    - StartupJobs.cz
    - Profesia.cz
    - Volnamista.cz
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8",
            },
            timeout=15.0,
            follow_redirects=True
        )

    @staticmethod
    def distribute_counts(total_count: int, sources: List[str]) -> Dict[str, int]:
        """
        Rovnoměrně rozdělí celkový počet inzerátů mezi vybrané zdroje.
        Případný zbytek náhodně přiřadí jednotlivým zdrojům bez opakování.
        """
        if not sources or total_count <= 0:
            return {}

        k = len(sources)
        base = total_count // k
        remainder = total_count % k

        counts = {source: base for source in sources}

        if remainder > 0:
            # Náhodný výběr zdrojů pro přidělení bonusového +1 inzerátu
            bonus_sources = random.sample(sources, remainder)
            for s in bonus_sources:
                counts[s] += 1

        return counts

    async def _search_jobs_cz(self, query: str, count: int) -> List[str]:
        """Vyhledá nabídky na jobs.cz."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://www.jobs.cz/prace/?q={encoded_query}" if query else "https://www.jobs.cz/prace/"

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return []

            tree = HTMLParser(response.text)
            links = []

            for a in tree.css("a"):
                href = a.attributes.get("href", "")
                if "jobs.cz/rpd/" in href or "jobs.cz/r/" in href:
                    clean_url = href.split("?")[0]
                    if clean_url not in links:
                        links.append(clean_url)
                        if len(links) >= count:
                            break

            return links
        except Exception as e:
            logger.warning(f"Chyba při vyhledávání na Jobs.cz: {e}")
            return []

    async def _search_prace_cz(self, query: str, count: int) -> List[str]:
        """Vyhledá nabídky na prace.cz."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://www.prace.cz/nabidky/?q={encoded_query}" if query else "https://www.prace.cz/nabidky/"

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return []

            tree = HTMLParser(response.text)
            links = []

            for a in tree.css("a"):
                href = a.attributes.get("href", "")
                if "/nabidka/" in href or "/rpd/" in href:
                    full_url = urllib.parse.urljoin("https://www.prace.cz", href.split("?")[0])
                    if full_url not in links and "prace.cz" in full_url:
                        links.append(full_url)
                        if len(links) >= count:
                            break

            return links
        except Exception as e:
            logger.warning(f"Chyba při vyhledávání na Prace.cz: {e}")
            return []

    async def _search_startupjobs_cz(self, query: str, count: int) -> List[str]:
        """Vyhledá nabídky na startupjobs.cz přes oficiální core API."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://core.startupjobs.cz/api/search/offers?query={encoded_query}"

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return []

            data = response.json()
            links = []
            for item in data.get("member", []):
                slug = item.get("slug")
                display_id = item.get("displayId")
                if slug and display_id:
                    offer_url = f"https://www.startupjobs.cz/nabidka/{display_id}/{slug}"
                    if offer_url not in links:
                        links.append(offer_url)
                        if len(links) >= count:
                            break
                elif slug:
                    offer_url = f"https://www.startupjobs.cz/nabidka/{slug}"
                    if offer_url not in links:
                        links.append(offer_url)
                        if len(links) >= count:
                            break

            return links
        except Exception as e:
            logger.warning(f"Chyba při vyhledávání na StartupJobs.cz: {e}")
            return []

    async def _search_profesia_cz(self, query: str, count: int) -> List[str]:
        """Vyhledá nabídky na profesia.cz."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://www.profesia.cz/prace/?search_keywords={encoded_query}" if query else "https://www.profesia.cz/prace/"

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return []

            tree = HTMLParser(response.text)
            links = []

            for a in tree.css("a"):
                href = a.attributes.get("href", "")
                if "/prace/" in href and re.search(r'/O\d+', href):
                    full_url = urllib.parse.urljoin("https://www.profesia.cz", href.split("?")[0])
                    if full_url not in links:
                        links.append(full_url)
                        if len(links) >= count:
                            break

            return links
        except Exception as e:
            logger.warning(f"Chyba při vyhledávání na Profesia.cz: {e}")
            return []

    async def _search_volnamista_cz(self, query: str, count: int) -> List[str]:
        """Vyhledá nabídky na volnamista.cz."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://www.volnamista.cz/hledam-praci?q={encoded_query}" if query else "https://www.volnamista.cz/hledam-praci"

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return []

            tree = HTMLParser(response.text)
            links = []

            for a in tree.css("a"):
                href = a.attributes.get("href", "")
                if "/nabidka-prace/" in href or "/pozice/" in href:
                    full_url = urllib.parse.urljoin("https://www.volnamista.cz", href.split("?")[0])
                    if full_url not in links:
                        links.append(full_url)
                        if len(links) >= count:
                            break

            return links
        except Exception as e:
            logger.warning(f"Chyba při vyhledávání na Volnamista.cz: {e}")
            return []

    async def search_single_source(self, source: str, query: str, count: int) -> List[str]:
        """Vyhledá inzeráty na konkrétním vybraném portálu."""
        s = source.lower().strip()
        if "startupjobs" in s:
            return await self._search_startupjobs_cz(query, count)
        elif "prace.cz" in s or "prace" in s:
            return await self._search_prace_cz(query, count)
        elif "profesia" in s:
            return await self._search_profesia_cz(query, count)
        elif "volnamista" in s:
            return await self._search_volnamista_cz(query, count)
        elif "jobs.cz" in s or "jobs" in s:
            return await self._search_jobs_cz(query, count)
        else:
            logger.warning(f"Neznámý zdroj vyhledávání: {source}")
            return []

    async def search_jobs(
        self, 
        query: str = "", 
        count: int = 10, 
        sources: Optional[List[str]] = None
    ) -> List[str]:
        """
        Hlavní asynchronní metoda:
        1. Rozdělí kvótu pro vybrané zdroje (se spravedlivým náhodným zbytkem).
        2. Paralelně spustí vyhledávání na zvolených portálech.
        3. Spojí výsledky a v případě výpadku jednoho portálu zkusí doplnit kvótu.
        """
        valid_sources = [
            s.strip() for s in (sources or ["jobs.cz", "prace.cz", "startupjobs.cz"]) if s.strip()
        ]
        if not valid_sources:
            valid_sources = ["jobs.cz"]

        # 1. Výpočet kvót pro každý vybraný zdroj
        quotas = self.distribute_counts(count, valid_sources)
        logger.info(f"Rozdělení kvót pro prozkoumání trhu (celkem {count}): {quotas}")

        # 2. Paralelní spuštění vyhledávání
        tasks = []
        for source, quota in quotas.items():
            # Požádáme o dostatečný počet odkazů z každého zdroje pro možnost doplnění
            fetch_count = max(quota, 10) if quota > 0 else 0
            tasks.append(self.search_single_source(source, query, fetch_count))

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        all_collected_links: List[str] = []
        source_links_map: Dict[str, List[str]] = {}

        # 3. Zpracování výsledků
        for source, res in zip(quotas.keys(), results_lists):
            if isinstance(res, Exception):
                logger.error(f"Chyba při scrapování vyhledávání ze zdroje {source}: {res}")
                source_links_map[source] = []
            else:
                source_links_map[source] = res or []

        # 4. Výběr přiděleného počtu odkazů z každého portálu
        for source, quota in quotas.items():
            assigned_links = source_links_map[source][:quota]
            for link in assigned_links:
                if link not in all_collected_links:
                    all_collected_links.append(link)

        # 5. Doplnění (Backfill), pokud některý portál vrátil méně než svou kvótu
        if len(all_collected_links) < count:
            for source, links in source_links_map.items():
                for link in links:
                    if link not in all_collected_links:
                        all_collected_links.append(link)
                        if len(all_collected_links) >= count:
                            break
                if len(all_collected_links) >= count:
                    break

        return all_collected_links[:count]
