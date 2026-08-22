import random
import asyncio
import logging
import urllib.parse
import re
import unicodedata
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
import httpx
from selectolax.parser import HTMLParser

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    url: str
    title: str
    company: str
    source: str
    relevance_score: float = 1.0


def normalize_text(text: str) -> str:
    """Odstraní diakritiku a převede na malá písmena pro spolehlivé porovnávání."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


# Slovník synonym a ekvivalentů (česky <-> anglicky <-> zkratky)
ROLE_SYNONYMS: Dict[str, List[str]] = {
    "produktovy": ["produkt", "product", "po", "pm", "cpo", "vlastnik produktu"],
    "produkt": ["produkt", "product", "po", "pm", "cpo"],
    "product": ["produkt", "product", "po", "pm", "cpo"],
    "projektovy": ["projekt", "project", "pmo"],
    "projekt": ["projekt", "project", "pmo"],
    "project": ["projekt", "project", "pmo"],
    "vyvojar": ["vyvojar", "developer", "programator", "engineer", "software", "coder", "dev"],
    "developer": ["vyvojar", "developer", "programator", "engineer", "software", "coder", "dev"],
    "programator": ["vyvojar", "developer", "programator", "engineer", "software"],
    "manazer": ["manazer", "manager", "lead", "head", "director", "vedouci", "specialista", "owner"],
    "manager": ["manazer", "manager", "lead", "head", "director", "vedouci", "specialista", "owner"],
    "vedouci": ["vedouci", "manazer", "manager", "lead", "head", "director"],
    "analytik": ["analytik", "analyst", "analytics"],
    "analyst": ["analytik", "analyst", "analytics"],
    "obchodnik": ["obchodnik", "sales", "obchod", "account", "representative", "prodejce"],
    "sales": ["obchodnik", "sales", "obchod", "account", "representative", "prodejce"],
    "ucetni": ["ucetni", "accountant", "accounting", "finance", "financial"],
    "tester": ["tester", "qa", "test", "quality assurance"],
    "qa": ["tester", "qa", "test", "quality assurance"],
    "designer": ["designer", "ux", "ui", "grafik", "design"],
    "grafik": ["designer", "ux", "ui", "grafik", "design"],
    "spravce": ["spravce", "admin", "administrator", "devops", "sysadmin"],
    "administrator": ["spravce", "admin", "administrator", "devops", "sysadmin"],
}

# Negativní distraktory: pokud uživatel hledá X, ale inzerát je Y bez výskytu X
ROLE_CONFLICTS = [
    ({"produkt", "product"}, {"projekt", "project", "account", "office", "hr", "sales", "prodejce", "rekruter", "development"}),
    ({"projekt", "project"}, {"produkt", "product", "ucetni", "skladnik", "ridic"}),
    ({"vyvojar", "developer", "programator"}, {"obchodnik", "sales", "recruiter", "asistent"}),
]


def is_variant_in_text(variant: str, text: str, tokens: Set[str]) -> bool:
    """Ověří, zda se varianta vyskytuje v textu (krátké zkratky vyžadují celé slovo)."""
    if len(variant) <= 3:
        return variant in tokens
    return variant in text or any(t.startswith(variant) for t in tokens)


def calculate_relevance(query: str, title: str, snippet: str = "") -> float:
    """
    Vypočítá míru shody (0.0 až 1.0) mezi hledaným dotazem a inzerátem.
    Eliminuje falešné pozitivní výsledky (např. 'Projektový manažer' při hledání 'Produktový manažer').
    """
    q_norm = normalize_text(query)
    t_norm = normalize_text(title)
    s_norm = normalize_text(snippet)

    if not q_norm:
        return 1.0

    if q_norm in t_norm:
        return 1.0

    q_words = [w for w in re.split(r"\s+", q_norm) if len(w) >= 2]
    if not q_words:
        return 1.0

    t_tokens = set(re.findall(r"\w+", t_norm))
    s_tokens = set(re.findall(r"\w+", s_norm))

    # Kontrola striktních konfliktů rolí
    for target_set, conflict_set in ROLE_CONFLICTS:
        query_has_target = any(is_variant_in_text(target, q_norm, set(q_words)) for target in target_set)
        title_has_target = any(is_variant_in_text(target, t_norm, t_tokens) for target in target_set)
        title_has_conflict = any(is_variant_in_text(conflict, t_norm, t_tokens) for conflict in conflict_set)

        if query_has_target and not title_has_target and title_has_conflict:
            return 0.0

    matched_words = 0
    for w in q_words:
        variants = ROLE_SYNONYMS.get(w, [w])
        if any(is_variant_in_text(v, t_norm, t_tokens) for v in variants):
            matched_words += 1
        elif any(is_variant_in_text(v, s_norm, s_tokens) for v in variants):
            matched_words += 0.4

    score = matched_words / len(q_words)
    return min(1.0, score)


def clean_portal_title(raw_title: str) -> str:
    """Odstraní z titulku inzerátu zbytečné reklamní a navigační texty."""
    if not raw_title:
        return ""
    title = raw_title.strip()
    prefixes_to_strip = [
        "Detail pozice | ", "Detail nabídky | ", "Nabídka práce - ", "Volné místo - ",
        "Detail pozice - ", "Pracovní nabídka: "
    ]
    for p in prefixes_to_strip:
        if title.lower().startswith(p.lower()):
            title = title[len(p):].strip()
    return title


class JobSearchScraper:
    """
    Pokročilý vyhledávač nabídek práce s relevančním filtrem napříč českými portály:
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
        if not sources or total_count <= 0:
            return {}
        k = len(sources)
        base = total_count // k
        remainder = total_count % k
        counts = {source: base for source in sources}
        if remainder > 0:
            bonus_sources = random.sample(sources, remainder)
            for s in bonus_sources:
                counts[s] += 1
        return counts

    async def _search_jobs_cz(self, query: str, count: int) -> List[SearchResult]:
        """Vyhledá a přesně vyfiltruje nabídky na jobs.cz."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query.strip())
        url = f"https://www.jobs.cz/prace/?q={encoded_query}" if query.strip() else "https://www.jobs.cz/prace/"

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return []

            tree = HTMLParser(response.text)
            results: List[SearchResult] = []

            for article in tree.css("article"):
                title_node = article.css_first("h2, h3, a.link-primary, [data-test='job-title']")
                title = clean_portal_title(title_node.text().strip() if title_node else "")
                
                # Extrakce firmy s vyloučením Atmoskop odznaků
                company = "Neznámá společnost"
                for c_sel in ["[data-test='job-company']", ".typography-company-name", "a.link-secondary", "[class*='company']"]:
                    c_node = article.css_first(c_sel)
                    if c_node:
                        c_text = c_node.text().strip()
                        if c_text and "atmoskop" not in c_text.lower():
                            company = c_text
                            break

                # Extrakce odkazu
                link_node = article.css_first("a[href*='/rpd/'], a[href*='/r/'], a.link-primary, h2 a, h3 a")
                if not link_node:
                    continue
                href = link_node.attributes.get("href", "")
                if not href or "/prihlasit-se" in href:
                    continue

                clean_url = urllib.parse.urljoin("https://www.jobs.cz", href.split("?")[0])
                
                snippet = article.text().strip()
                rel_score = calculate_relevance(query, title, snippet)

                # Prahová hodnota relevance (>= 0.6 pro přesnou shodu)
                if not query.strip() or rel_score >= 0.6:
                    results.append(SearchResult(
                        url=clean_url,
                        title=title or "Pracovní pozice",
                        company=company,
                        source="Jobs.cz",
                        relevance_score=rel_score
                    ))

            results.sort(key=lambda x: x.relevance_score, reverse=True)
            return results
        except Exception as e:
            logger.warning(f"Chyba při vyhledávání na Jobs.cz: {e}")
            return []

    async def _search_prace_cz(self, query: str, count: int) -> List[SearchResult]:
        """Vyhledá a přesně vyfiltruje nabídky na prace.cz s ignorováním sponzorovaných nerelevantních bannerů."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query.strip())
        url = f"https://www.prace.cz/nabidky/?q={encoded_query}" if query.strip() else "https://www.prace.cz/nabidky/"

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return []

            tree = HTMLParser(response.text)
            results: List[SearchResult] = []

            for card in tree.css("article, [data-qa='job-card'], li.search-result, .job-card, [class*='JobCard']"):
                title_node = card.css_first("h2 a, h3 a, [class*='JobCardTitle'] a, [class*='job-title'] a, h2, h3")
                title = clean_portal_title(title_node.text().strip() if title_node else "")
                
                company_node = card.css_first(".employer, .company, [data-qa='job-ad-company'], .job-card__employer")
                company = company_node.text().strip() if company_node else "Neznámá společnost"

                link_node = card.css_first("a[href*='/nabidka/'], a[href*='/rpd/'], h2 a, h3 a")
                if not link_node:
                    continue
                href = link_node.attributes.get("href", "")
                if not href or "/prihlasit-se" in href or "/hledam-praci" in href:
                    continue

                full_url = urllib.parse.urljoin("https://www.prace.cz", href.split("?")[0])
                if "prace.cz" not in full_url:
                    continue

                snippet = card.text().strip()
                rel_score = calculate_relevance(query, title, snippet)

                if not query.strip() or rel_score >= 0.6:
                    results.append(SearchResult(
                        url=full_url,
                        title=title or "Pracovní pozice",
                        company=company,
                        source="Prace.cz",
                        relevance_score=rel_score
                    ))

            results.sort(key=lambda x: x.relevance_score, reverse=True)
            return results
        except Exception as e:
            logger.warning(f"Chyba při vyhledávání na Prace.cz: {e}")
            return []

    async def _search_startupjobs_cz(self, query: str, count: int) -> List[SearchResult]:
        """Vyhledá a přesně vyfiltruje nabídky na startupjobs.cz."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query.strip())
        url = f"https://core.startupjobs.cz/api/search/offers?fulltext[]={encoded_query}" if query.strip() else "https://core.startupjobs.cz/api/search/offers"

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return []

            data = response.json()
            results: List[SearchResult] = []

            for item in data.get("member", []):
                name_val = item.get("name") or item.get("title") or ""
                if isinstance(name_val, dict):
                    title = name_val.get("cs") or name_val.get("en") or next(iter(name_val.values()), "") or ""
                else:
                    title = str(name_val).strip()

                title = clean_portal_title(title)
                
                # Získání firmy
                company = "StartupJobs"
                company_obj = item.get("company")
                if isinstance(company_obj, dict):
                    company = company_obj.get("name") or company
                elif isinstance(item.get("companyName"), str):
                    company = item.get("companyName")

                slug = item.get("slug")
                display_id = item.get("displayId")
                if not slug:
                    continue

                if display_id:
                    offer_url = f"https://www.startupjobs.cz/nabidka/{display_id}/{slug}"
                else:
                    offer_url = f"https://www.startupjobs.cz/nabidka/{slug}"

                # Role a dovednosti pro výpočet relevance
                raw_roles = item.get("roles") or []
                roles_str = " ".join([r.get("name", "") if isinstance(r, dict) else str(r) for r in raw_roles])
                raw_skills = item.get("skills") or []
                skills_str = " ".join([s.get("name", "") if isinstance(s, dict) else str(s) for s in raw_skills])
                snippet = f"{roles_str} {skills_str}"

                rel_score = calculate_relevance(query, title, snippet)

                if not query.strip() or rel_score >= 0.6:
                    results.append(SearchResult(
                        url=offer_url,
                        title=title or "Pracovní pozice",
                        company=company,
                        source="StartupJobs.cz",
                        relevance_score=rel_score
                    ))

            results.sort(key=lambda x: x.relevance_score, reverse=True)
            return results
        except Exception as e:
            logger.warning(f"Chyba při vyhledávání na StartupJobs.cz: {e}")
            return []

    async def _search_profesia_cz(self, query: str, count: int) -> List[SearchResult]:
        """Vyhledá a vyfiltruje nabídky na profesia.cz."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query.strip())
        url = f"https://www.profesia.cz/prace/?search_anywhere={encoded_query}" if query.strip() else "https://www.profesia.cz/prace/"

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return []

            tree = HTMLParser(response.text)
            results: List[SearchResult] = []

            for item in tree.css("li.list-row, .list-row, article"):
                title_node = item.css_first("h2 a, .title a, a.title, h2")
                title = clean_portal_title(title_node.text().strip() if title_node else "")
                
                company_node = item.css_first(".employer, .company-name")
                company = company_node.text().strip() if company_node else "Neznámá společnost"

                link_node = item.css_first("a[href*='/prace/O'], h2 a")
                if not link_node:
                    continue
                href = link_node.attributes.get("href", "")
                if not href or not re.search(r'/O\d+', href):
                    continue

                full_url = urllib.parse.urljoin("https://www.profesia.cz", href.split("?")[0])
                rel_score = calculate_relevance(query, title, item.text().strip())

                if not query.strip() or rel_score >= 0.6:
                    results.append(SearchResult(
                        url=full_url,
                        title=title or "Pracovní pozice",
                        company=company,
                        source="Profesia.cz",
                        relevance_score=rel_score
                    ))

            results.sort(key=lambda x: x.relevance_score, reverse=True)
            return results
        except Exception as e:
            logger.warning(f"Chyba při vyhledávání na Profesia.cz: {e}")
            return []

    async def _search_volnamista_cz(self, query: str, count: int) -> List[SearchResult]:
        """Vyhledá a vyfiltruje nabídky na volnamista.cz."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query.strip())
        url = f"https://www.volnamista.cz/prace/{encoded_query}" if query.strip() else "https://www.volnamista.cz/hledam-praci"

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return []

            tree = HTMLParser(response.text)
            results: List[SearchResult] = []

            for card in tree.css("article, .job-item, .box-job"):
                title_node = card.css_first("h2 a, h3 a, .job-title a, h2, h3")
                title = clean_portal_title(title_node.text().strip() if title_node else "")
                
                company_node = card.css_first(".company, .employer, .company-name")
                company = company_node.text().strip() if company_node else "Neznámá společnost"

                link_node = card.css_first("a[href*='/nabidka-prace/'], a[href*='/pozice/'], h2 a")
                if not link_node:
                    continue
                href = link_node.attributes.get("href", "")
                if not href:
                    continue

                full_url = urllib.parse.urljoin("https://www.volnamista.cz", href.split("?")[0])
                rel_score = calculate_relevance(query, title, card.text().strip())

                if not query.strip() or rel_score >= 0.6:
                    results.append(SearchResult(
                        url=full_url,
                        title=title or "Pracovní pozice",
                        company=company,
                        source="Volnamista.cz",
                        relevance_score=rel_score
                    ))

            results.sort(key=lambda x: x.relevance_score, reverse=True)
            return results
        except Exception as e:
            logger.warning(f"Chyba při vyhledávání na Volnamista.cz: {e}")
            return []

    async def search_single_source(self, source: str, query: str, count: int) -> List[SearchResult]:
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
    ) -> List[SearchResult]:
        """
        Hlavní asynchronní metoda vyhledávání:
        1. Rozdělí kvóty pro vybrané portály.
        2. Paralelně stáhne a přísně vyfiltruje nabídky podle relevance dotazu.
        3. Spojí výsledky, odstraní duplicity a vrátí nejrelevantnější nabídky.
        """
        valid_sources = [
            s.strip() for s in (sources or ["jobs.cz", "prace.cz", "startupjobs.cz"]) if s.strip()
        ]
        if not valid_sources:
            valid_sources = ["jobs.cz"]

        quotas = self.distribute_counts(count, valid_sources)
        logger.info(f"Hledám '{query}' (celkem {count} pozic) napříč zdroji: {quotas}")

        tasks = []
        for source, quota in quotas.items():
            fetch_count = max(quota * 4, 20) if quota > 0 else 0
            tasks.append(self.search_single_source(source, query, fetch_count))

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: List[SearchResult] = []
        seen_urls = set()

        # 1. Zpracování a rozdělení podle kvót z jednotlivých portálů
        for source, res in zip(quotas.keys(), results_lists):
            if isinstance(res, Exception):
                logger.error(f"Chyba při scrapování vyhledávání ze zdroje {source}: {res}")
                continue
            
            source_items = res or []
            added_for_source = 0
            target_quota = quotas[source]

            for item in source_items:
                if item.url not in seen_urls and added_for_source < target_quota:
                    all_results.append(item)
                    seen_urls.add(item.url)
                    added_for_source += 1

        # 2. Backfill (doplnění) z jakéhokoliv dalšího zdroje s vysokou relevancí
        if len(all_results) < count:
            for res in results_lists:
                if isinstance(res, Exception) or not res:
                    continue
                for item in res:
                    if item.url not in seen_urls:
                        all_results.append(item)
                        seen_urls.add(item.url)
                        if len(all_results) >= count:
                            break
                if len(all_results) >= count:
                    break

        all_results.sort(key=lambda x: x.relevance_score, reverse=True)
        return all_results[:count]
