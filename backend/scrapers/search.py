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
    Eliminuje falešné pozitivní výsledky (např. 'Projektový manažer' při hledání 'Produktový manažer'),
    ale nezahazuje relevantní nabídky vrácené vyhledávačem pracovního portálu.
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

    matched_words = 0.0
    for w in q_words:
        variants = ROLE_SYNONYMS.get(w, [w])
        if any(is_variant_in_text(v, t_norm, t_tokens) for v in variants):
            matched_words += 1.0
        elif any(is_variant_in_text(v, s_norm, s_tokens) for v in variants):
            matched_words += 0.8
        elif w in s_norm or w in t_norm:
            matched_words += 0.6
        else:
            # Inzerát vrátil přímo vyhledávač portálu pro zadaný dotaz
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


# 14 českých krajů a jejich mapování pro pracovní portály
CZECH_REGIONS: Dict[str, Dict[str, any]] = {
    "praha": {
        "id": "praha",
        "name": "Hlavní město Praha",
        "city": "Praha",
        "jobs_slug": "praha",
        "prace_slug": "praha",
        "profesia_slug": "hlavni-mesto-praha",
        "volnamista_slug": "praha",
        "keywords": ["praha", "prague"],
    },
    "stredocesky": {
        "id": "stredocesky",
        "name": "Středočeský kraj",
        "city": "Praha (sídlo kraje)",
        "jobs_slug": "stredocesky-kraj",
        "prace_slug": "stredocesky-kraj",
        "profesia_slug": "stredocesky-kraj",
        "volnamista_slug": "stredocesky-kraj",
        "keywords": ["stredocesky", "stredni cechy", "kladno", "mlada boleslav", "pribram", "kolin", "kutna hora", "melnik", "beroun", "benesov", "nymburk", "rakovnik", "brandys", "ricany"],
    },
    "jihocesky": {
        "id": "jihocesky",
        "name": "Jihočeský kraj",
        "city": "České Budějovice",
        "jobs_slug": "jihocesky-kraj",
        "prace_slug": "jihocesky-kraj",
        "profesia_slug": "jihocesky-kraj",
        "volnamista_slug": "jihocesky-kraj",
        "keywords": ["jihocesky", "jizni cechy", "ceske budejovice", "tabor", "pisek", "strakonice", "jindrichuv hradec", "prachatice", "cesky krumlov"],
    },
    "plzensky": {
        "id": "plzensky",
        "name": "Plzeňský kraj",
        "city": "Plzeň",
        "jobs_slug": "plzensky-kraj",
        "prace_slug": "plzensky-kraj",
        "profesia_slug": "plzensky-kraj",
        "volnamista_slug": "plzensky-kraj",
        "keywords": ["plzensky", "plzen", "klatovy", "rokycany", "tachov", "domazlice"],
    },
    "karlovarsky": {
        "id": "karlovarsky",
        "name": "Karlovarský kraj",
        "city": "Karlovy Vary",
        "jobs_slug": "karlovarsky-kraj",
        "prace_slug": "karlovarsky-kraj",
        "profesia_slug": "karlovarsky-kraj",
        "volnamista_slug": "karlovarsky-kraj",
        "keywords": ["karlovarsky", "karlovy vary", "cheb", "sokolov", "ostrov", "as"],
    },
    "ustecky": {
        "id": "ustecky",
        "name": "Ústecký kraj",
        "city": "Ústí nad Labem",
        "jobs_slug": "ustecky-kraj",
        "prace_slug": "ustecky-kraj",
        "profesia_slug": "ustecky-kraj",
        "volnamista_slug": "ustecky-kraj",
        "keywords": ["ustecky", "usti nad labem", "most", "decin", "teplice", "chomutov", "litomerice", "louny", "zatec", "kadan"],
    },
    "liberecky": {
        "id": "liberecky",
        "name": "Liberecký kraj",
        "city": "Liberec",
        "jobs_slug": "liberecky-kraj",
        "prace_slug": "liberecky-kraj",
        "profesia_slug": "liberecky-kraj",
        "volnamista_slug": "liberecky-kraj",
        "keywords": ["liberecky", "liberec", "jablonec nad nisou", "ceska lipa", "turnov", "semily", "novy bor"],
    },
    "kralovehradecky": {
        "id": "kralovehradecky",
        "name": "Královéhradecký kraj",
        "city": "Hradec Králové",
        "jobs_slug": "kralovehradecky-kraj",
        "prace_slug": "kralovehradecky-kraj",
        "profesia_slug": "kralovehradecky-kraj",
        "volnamista_slug": "kralovehradecky-kraj",
        "keywords": ["kralovehradecky", "hradec kralove", "trutnov", "nachod", "jicin", "rychnov nad kneznou", "vrchlabi", "jaromer"],
    },
    "pardubicky": {
        "id": "pardubicky",
        "name": "Pardubický kraj",
        "city": "Pardubice",
        "jobs_slug": "pardubicky-kraj",
        "prace_slug": "pardubicky-kraj",
        "profesia_slug": "pardubicky-kraj",
        "volnamista_slug": "pardubicky-kraj",
        "keywords": ["pardubicky", "pardubice", "chrudim", "svitavy", "usti nad orlici", "ceska trebova", "litomysl", "lanstroun", "vysoke myto"],
    },
    "vysocina": {
        "id": "vysocina",
        "name": "Kraj Vysočina",
        "city": "Jihlava",
        "jobs_slug": "vysocina-kraj",
        "prace_slug": "vysocina",
        "profesia_slug": "kraj-vysocina",
        "volnamista_slug": "vysocina",
        "keywords": ["vysocina", "jihlava", "trebic", "havlickuv brod", "zdar nad sazavou", "pelhrimov", "velke mezirici", "humpolec"],
    },
    "jihomoravsky": {
        "id": "jihomoravsky",
        "name": "Jihomoravský kraj",
        "city": "Brno",
        "jobs_slug": "jihomoravsky-kraj",
        "prace_slug": "jihomoravsky-kraj",
        "profesia_slug": "jihomoravsky-kraj",
        "volnamista_slug": "jihomoravsky-kraj",
        "keywords": ["jihomoravsky", "jizni morava", "brno", "znojmo", "hodonin", "breclav", "vyskov", "blansko", "kyjov", "boskovice"],
    },
    "olomoucky": {
        "id": "olomoucky",
        "name": "Olomoucký kraj",
        "city": "Olomouc",
        "jobs_slug": "olomoucky-kraj",
        "prace_slug": "olomoucky-kraj",
        "profesia_slug": "olomoucky-kraj",
        "volnamista_slug": "olomoucky-kraj",
        "keywords": ["olomoucky", "olomouc", "prostejov", "prerov", "sumperk", "jesenik", "hranice", "zabreh", "stemberk"],
    },
    "zlinsky": {
        "id": "zlinsky",
        "name": "Zlínský kraj",
        "city": "Zlín",
        "jobs_slug": "zlinsky-kraj",
        "prace_slug": "zlinsky-kraj",
        "profesia_slug": "zlinsky-kraj",
        "volnamista_slug": "zlinsky-kraj",
        "keywords": ["zlinsky", "zlin", "uherske hradiste", "vsetin", "kromeriz", "valasske mezirici", "otrokovice", "roznov pod radhostem", "uhersky brod"],
    },
    "moravskoslezsky": {
        "id": "moravskoslezsky",
        "name": "Moravskoslezský kraj",
        "city": "Ostrava",
        "jobs_slug": "moravskoslezsky-kraj",
        "prace_slug": "moravskoslezsky-kraj",
        "profesia_slug": "moravskoslezsky-kraj",
        "volnamista_slug": "moravskoslezsky-kraj",
        "keywords": ["moravskoslezsky", "severni morava", "ostrava", "opava", "frydek-mistek", "karvina", "havirov", "trinec", "novy jicin", "krnov", "bohumin", "bruntal"],
    }
}


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

    async def aclose(self):
        """Uzavře podkladového HTTP klienta pro uvolnění systémových prostředků."""
        if hasattr(self, "client") and not self.client.is_closed:
            await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

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

    async def _search_jobs_cz(self, query: str, count: int, locations: Optional[List[str]] = None) -> List[SearchResult]:
        """Vyhledá a přesně vyfiltruje nabídky na jobs.cz s podporou krajů a měst."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query.strip())
        
        urls_to_fetch = []
        if locations and len(locations) > 0:
            for loc_id in locations:
                region_info = CZECH_REGIONS.get(loc_id.lower().strip())
                slug = region_info["jobs_slug"] if region_info else loc_id.lower().strip()
                loc_url = f"https://www.jobs.cz/prace/{slug}/?q={encoded_query}" if query.strip() else f"https://www.jobs.cz/prace/{slug}/"
                urls_to_fetch.append(loc_url)
        else:
            main_url = f"https://www.jobs.cz/prace/?q={encoded_query}" if query.strip() else "https://www.jobs.cz/prace/"
            urls_to_fetch.append(main_url)

        results: List[SearchResult] = []
        seen_urls = set()

        for url in urls_to_fetch:
            try:
                response = await self.client.get(url)
                if response.status_code != 200:
                    continue

                tree = HTMLParser(response.text)
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
                    if clean_url in seen_urls:
                        continue
                    
                    snippet = article.text().strip()
                    rel_score = calculate_relevance(query, title, snippet)

                    # Akceptujeme relevantní výsledky
                    if not query.strip() or rel_score >= 0.3:
                        seen_urls.add(clean_url)
                        results.append(SearchResult(
                            url=clean_url,
                            title=title or "Pracovní pozice",
                            company=company,
                            source="Jobs.cz",
                            relevance_score=rel_score
                        ))
            except Exception as e:
                logger.warning(f"Chyba při vyhledávání na Jobs.cz ({url}): {e}")

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results

    async def _search_prace_cz(self, query: str, count: int, locations: Optional[List[str]] = None) -> List[SearchResult]:
        """Vyhledá a přesně vyfiltruje nabídky na prace.cz s podporou krajů a měst."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query.strip())
        
        urls_to_fetch = []
        if locations and len(locations) > 0:
            for loc_id in locations:
                region_info = CZECH_REGIONS.get(loc_id.lower().strip())
                slug = region_info["prace_slug"] if region_info else loc_id.lower().strip()
                loc_url = f"https://www.prace.cz/nabidky/{slug}/?q={encoded_query}" if query.strip() else f"https://www.prace.cz/nabidky/{slug}/"
                urls_to_fetch.append(loc_url)
        else:
            main_url = f"https://www.prace.cz/nabidky/?q={encoded_query}" if query.strip() else "https://www.prace.cz/nabidky/"
            urls_to_fetch.append(main_url)

        results: List[SearchResult] = []
        seen_urls = set()

        for url in urls_to_fetch:
            try:
                response = await self.client.get(url)
                if response.status_code != 200:
                    continue

                tree = HTMLParser(response.text)
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
                    if full_url in seen_urls:
                        continue

                    snippet = card.text().strip()
                    rel_score = calculate_relevance(query, title, snippet)

                    if not query.strip() or rel_score >= 0.3:
                        seen_urls.add(full_url)
                        results.append(SearchResult(
                            url=full_url,
                            title=title or "Pracovní pozice",
                            company=company,
                            source="Prace.cz",
                            relevance_score=rel_score
                        ))
            except Exception as e:
                logger.warning(f"Chyba při vyhledávání na Prace.cz ({url}): {e}")

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results

    async def _search_startupjobs_cz(self, query: str, count: int, locations: Optional[List[str]] = None) -> List[SearchResult]:
        """Vyhledá a přesně vyfiltruje nabídky na startupjobs.cz s podporou Nuxt 3 stavu."""
        if count <= 0:
            return []
        
        encoded_query = urllib.parse.quote_plus(query.strip())
        urls_to_fetch = []
        if locations and len(locations) > 0:
            for loc_id in locations:
                slug = "praha" if loc_id.lower().strip() in ["praha", "stredocesky"] else ("brno" if "jihomoravsky" in loc_id.lower() else "")
                if slug:
                    urls_to_fetch.append(f"https://www.startupjobs.cz/nabidky/{slug}?supersearch={encoded_query}" if query.strip() else f"https://www.startupjobs.cz/nabidky/{slug}")
        
        if not urls_to_fetch:
            urls_to_fetch.append(f"https://www.startupjobs.cz/nabidky?supersearch={encoded_query}" if query.strip() else "https://www.startupjobs.cz/nabidky")

        def _resolve(val, data):
            if isinstance(val, int) and 0 <= val < len(data):
                return _resolve(data[val], data)
            elif isinstance(val, dict):
                if "cs" in val:
                    return _resolve(val["cs"], data)
                elif "en" in val:
                    return _resolve(val["en"], data)
                else:
                    return {k: _resolve(v, data) for k, v in val.items()}
            elif isinstance(val, list):
                return [_resolve(item, data) for item in val]
            return val

        results: List[SearchResult] = []
        seen_urls = set()

        for url in urls_to_fetch:
            try:
                response = await self.client.get(url)
                if response.status_code != 200:
                    continue

                tree = HTMLParser(response.text)
                scripts = tree.css("script")
                for s in scripts:
                    text = s.text()
                    if not text or not text.startswith("[{"):
                        continue
                    try:
                        import json
                        data = json.loads(text)
                        for item in data:
                            if isinstance(item, dict) and ("name" in item or "title" in item) and "slug" in item:
                                raw_title = _resolve(item.get("name") or item.get("title"), data)
                                slug = _resolve(item.get("slug"), data)
                                if isinstance(raw_title, str) and isinstance(slug, str) and raw_title and slug and len(slug) > 3:
                                    offer_url = f"https://www.startupjobs.cz/nabidka/{slug}"
                                    if offer_url in seen_urls:
                                        continue

                                    title = clean_portal_title(raw_title)
                                    rel_score = calculate_relevance(query, title, "")
                                    if not query.strip() or rel_score >= 0.3:
                                        seen_urls.add(offer_url)
                                        results.append(SearchResult(
                                            url=offer_url,
                                            title=title or "Pracovní pozice",
                                            company="StartupJobs",
                                            source="StartupJobs.cz",
                                            relevance_score=rel_score
                                        ))
                    except Exception as json_err:
                        logger.debug(f"StartupJobs JSON parse skip: {json_err}")

            except Exception as e:
                logger.warning(f"Chyba při vyhledávání na StartupJobs.cz: {e}")

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results

    async def _search_profesia_cz(self, query: str, count: int, locations: Optional[List[str]] = None) -> List[SearchResult]:
        """Vyhledá a vyfiltruje nabídky na profesia.cz."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query.strip())
        
        urls_to_fetch = []
        if locations and len(locations) > 0:
            for loc_id in locations:
                region_info = CZECH_REGIONS.get(loc_id.lower().strip())
                slug = region_info["profesia_slug"] if region_info else loc_id.lower().strip()
                loc_url = f"https://www.profesia.cz/prace/{slug}/?search_anywhere={encoded_query}" if query.strip() else f"https://www.profesia.cz/prace/{slug}/"
                urls_to_fetch.append(loc_url)
        else:
            main_url = f"https://www.profesia.cz/prace/?search_anywhere={encoded_query}" if query.strip() else "https://www.profesia.cz/prace/"
            urls_to_fetch.append(main_url)

        results: List[SearchResult] = []
        seen_urls = set()

        for url in urls_to_fetch:
            try:
                response = await self.client.get(url)
                if response.status_code != 200:
                    continue

                tree = HTMLParser(response.text)
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
                    if full_url in seen_urls:
                        continue

                    rel_score = calculate_relevance(query, title, item.text().strip())

                    if not query.strip() or rel_score >= 0.3:
                        seen_urls.add(full_url)
                        results.append(SearchResult(
                            url=full_url,
                            title=title or "Pracovní pozice",
                            company=company,
                            source="Profesia.cz",
                            relevance_score=rel_score
                        ))
            except Exception as e:
                logger.warning(f"Chyba při vyhledávání na Profesia.cz ({url}): {e}")

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results

    async def _search_volnamista_cz(self, query: str, count: int, locations: Optional[List[str]] = None) -> List[SearchResult]:
        """Vyhledá a vyfiltruje nabídky na volnamista.cz."""
        if count <= 0:
            return []
        encoded_query = urllib.parse.quote_plus(query.strip())
        
        urls_to_fetch = []
        if locations and len(locations) > 0:
            for loc_id in locations:
                region_info = CZECH_REGIONS.get(loc_id.lower().strip())
                slug = region_info["volnamista_slug"] if region_info else loc_id.lower().strip()
                loc_url = f"https://www.volnamista.cz/hledam-praci?misto={slug}&q={encoded_query}" if query.strip() else f"https://www.volnamista.cz/hledam-praci?misto={slug}"
                urls_to_fetch.append(loc_url)
        else:
            main_url = f"https://www.volnamista.cz/hledam-praci?q={encoded_query}" if query.strip() else "https://www.volnamista.cz/hledam-praci"
            urls_to_fetch.append(main_url)

        results: List[SearchResult] = []
        seen_urls = set()

        for url in urls_to_fetch:
            try:
                response = await self.client.get(url)
                if response.status_code != 200:
                    continue

                tree = HTMLParser(response.text)
                for a_elem in tree.css("a[href*='/nabidka-prace/'], a[href*='/pozice/']"):
                    raw_href = a_elem.attributes.get("href", "")
                    if not raw_href:
                        continue

                    title = clean_portal_title(a_elem.text().strip())
                    if not title or len(title) < 3:
                        continue

                    full_url = urllib.parse.urljoin("https://www.volnamista.cz", raw_href.split("?")[0])
                    if full_url in seen_urls:
                        continue

                    rel_score = calculate_relevance(query, title, "")
                    if not query.strip() or rel_score >= 0.3:
                        seen_urls.add(full_url)
                        results.append(SearchResult(
                            url=full_url,
                            title=title or "Pracovní pozice",
                            company="VolnaMista",
                            source="Volnamista.cz",
                            relevance_score=rel_score
                        ))
            except Exception as e:
                logger.warning(f"Chyba při vyhledávání na Volnamista.cz ({url}): {e}")

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results

    async def search_single_source(self, source: str, query: str, count: int, locations: Optional[List[str]] = None) -> List[SearchResult]:
        s = source.lower().strip()
        if "startupjobs" in s:
            return await self._search_startupjobs_cz(query, count, locations)
        elif "prace.cz" in s or "prace" in s:
            return await self._search_prace_cz(query, count, locations)
        elif "profesia" in s:
            return await self._search_profesia_cz(query, count, locations)
        elif "volnamista" in s:
            return await self._search_volnamista_cz(query, count, locations)
        elif "jobs.cz" in s or "jobs" in s:
            return await self._search_jobs_cz(query, count, locations)
        else:
            logger.warning(f"Neznámý zdroj vyhledávání: {source}")
            return []

    async def search_jobs(
        self, 
        query: str = "", 
        count: int = 10, 
        sources: Optional[List[str]] = None,
        locations: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """
        Hlavní asynchronní metoda vyhledávání:
        1. Rozdělí kvóty pro vybrané portály.
        2. Paralelně stáhne a vyfiltruje nabídky podle relevance dotazu a zadaných lokalit.
        3. Spojí výsledky, odstraní duplicity a vrátí nejrelevantnější nabídky.
        4. Pokud některé zdroje vrátí méně pozic, automaticky doplní kvótu z ostatních zdrojů.
        """
        valid_sources = [
            s.strip() for s in (sources or ["jobs.cz", "prace.cz", "startupjobs.cz"]) if s.strip()
        ]
        if not valid_sources:
            valid_sources = ["jobs.cz"]

        quotas = self.distribute_counts(count, valid_sources)
        logger.info(f"Hledám '{query}' (celkem {count} pozic) napříč zdroji: {quotas}, lokality: {locations}")

        tasks = []
        for source, quota in quotas.items():
            fetch_count = max(quota * 4, 20) if quota > 0 else 0
            tasks.append(self.search_single_source(source, query, fetch_count, locations))

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

        # 2. Backfill (doplnění kvóty) z jakéhokoliv dalšího úspěšného zdroje
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
