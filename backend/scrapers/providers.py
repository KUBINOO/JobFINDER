import logging
import httpx
from urllib.parse import urljoin
from typing import List, Optional
from selectolax.parser import HTMLParser

from scrapers.base import AbstractCSSScraper
from scrapers.cleaner import DOMCleaner
from schemas import ScrapedJob

logger = logging.getLogger(__name__)

class CzechJobScraper(AbstractCSSScraper):
    """
    Základní scraper pro české pracovní portály.
    Využívá prioritní selektory, čištění DOM a detekci vložených inzerátů v iframe.
    """
    
    # Prioritní CSS selektory pro tělo inzerátu dle specifikace
    PRIORITY_BODY_SELECTORS: List[str] = [
        '[data-qa="job-ad-body"]',
        '.rich-text',
        '.standalone.cp',
        '.cp-job-ad-body',
        '.vacancy-description',
        'article',
        '.job-description',
        'div.description',
        '.typography-body',
        '.detail__description',
        '.job-text'
    ]

    async def _fetch_iframe_body(self, base_url: str, iframe_src: str) -> Optional[str]:
        """
        Stáhne obsah inzerátu z vloženého iframe a vyčistí jeho text.
        """
        try:
            # Sestavení absolutní URL adresy iframe
            full_iframe_url = urljoin(base_url, iframe_src)
            logger.info(f"Detekován vložený iframe s inzerátem: {full_iframe_url}")
            
            iframe_response = await self.client.get(full_iframe_url)
            if not iframe_response or not iframe_response.text:
                return None
                
            iframe_tree = HTMLParser(iframe_response.text)
            DOMCleaner.clean_tree(iframe_tree)
            
            iframe_text = DOMCleaner.extract_clean_text(iframe_tree)
            if len(iframe_text.strip()) >= 150:
                return iframe_text
                
            # Pokud přímý text nestačí, zkusíme sémantickou extrakci
            semantic_text = DOMCleaner.extract_semantic_text(iframe_tree)
            if len(semantic_text.strip()) >= 150:
                return semantic_text
                
            return None
        except Exception as e:
            logger.warning(f"Nepodařilo se stáhnout obsah z iframe ({iframe_src}): {e}")
            return None

    async def extract_job_details(self, url: str) -> ScrapedJob:
        """
        Extrahuje detaily pracovní nabídky z dané URL adresy.
        """
        try:
            response = await self.client.get(url)
            tree = HTMLParser(response.text)
            
            # 1. Extrakce titulku inzerátu
            title = ""
            title_selectors = [
                self.TITLE_SELECTOR,
                '[data-qa="job-ad-title"]',
                'h1.job-title',
                'h1',
                'title'
            ]
            for selector in title_selectors:
                node = tree.css_first(selector)
                if node:
                    extracted_title = node.text(strip=True)
                    if extracted_title:
                        title = extracted_title
                        break
                        
            if not title:
                title = "Neznámá pozice"

            # 2. Extrakce názvu společnosti
            company = ""
            company_selectors = [
                self.COMPANY_SELECTOR,
                '[data-qa="job-ad-company"]',
                '.typography-company-name',
                '.company-title',
                '.employer',
                '.detail__company',
                'div.company'
            ]
            for selector in company_selectors:
                node = tree.css_first(selector)
                if node:
                    extracted_company = node.text(strip=True)
                    if extracted_company:
                        company = extracted_company
                        break
                        
            if not company:
                company = "Neznámá společnost"

            # 3. Kontrola vloženého iframe s tělem inzerátu
            description = ""
            iframe_src = DOMCleaner.find_iframe_src(tree)
            if iframe_src:
                iframe_desc = await self._fetch_iframe_body(url, iframe_src)
                if iframe_desc:
                    description = iframe_desc

            # 4. Extrakce podle prioritních CSS selektorů, pokud nemáme popis z iframe
            if not description or len(description.strip()) < 150:
                all_selectors = self.PRIORITY_BODY_SELECTORS.copy()
                if self.DESCRIPTION_SELECTOR not in all_selectors:
                    all_selectors.insert(0, self.DESCRIPTION_SELECTOR)
                    
                for selector in all_selectors:
                    node = tree.css_first(selector)
                    if node:
                        # Zkontrolujeme, zda uzel neobsahuje vnitřní iframe
                        internal_iframe = node.css_first("iframe")
                        if internal_iframe:
                            internal_src = internal_iframe.attributes.get("src")
                            if internal_src:
                                internal_desc = await self._fetch_iframe_body(url, internal_src)
                                if internal_desc:
                                    description = internal_desc
                                    break
                                    
                        # Vyčištění konkrétního uzlu
                        DOMCleaner.clean_node(node)
                        extracted = DOMCleaner.extract_clean_text(node)
                        
                        if len(extracted.strip()) >= 150:
                            description = extracted
                            break

            # 5. Záložní fallback: Čistý body fallback pouze se sémantickými odstavci (<p>, <li>, <h3>, <h4>)
            if not description or len(description.strip()) < 150:
                # Vyčistíme celý strom od menu, patiček, patičkových linků atd.
                DOMCleaner.clean_tree(tree)
                fallback_container = tree.css_first("main") or tree.css_first("article") or tree.css_first("body")
                if fallback_container:
                    semantic_text = DOMCleaner.extract_semantic_text(fallback_container)
                    if len(semantic_text.strip()) >= 150:
                        description = semantic_text

            # 6. Sekundární záchranný fallback (Jina AI Reader pro těžce dynamické JS stránky)
            if not description or len(description.strip()) < 150:
                logger.info(f"Lokální extrakce vrátila krátký text ({len(description)} znaků), zkouším Jina AI Reader pro: {url}")
                try:
                    jina_url = f"https://r.jina.ai/{url}"
                    async with httpx.AsyncClient(timeout=15.0) as jina_client:
                        jina_res = await jina_client.get(jina_url)
                        if jina_res.status_code == 200:
                            jina_text = jina_res.text
                            if "Title: " in jina_text:
                                jina_title = jina_text.split("Title: ")[1].split("\n")[0].strip()
                                if jina_title and title == "Neznámá pozice":
                                    title = jina_title
                            if len(jina_text.strip()) >= 150:
                                description = jina_text
                except Exception as jina_err:
                    logger.warning(f"Jina AI Reader fallback selhal: {jina_err}")

            return ScrapedJob(
                source_url=url, # type: ignore
                title=title,
                company_name=company,
                description=description
            )
        except Exception as e:
            logger.error(f"Chyba při scrapování {url}: {e}")
            raise Exception(f"Chyba při scrapování {url}: {e}") from e


class JobsCzScraper(CzechJobScraper):
    """Scraper specializovaný na portál Jobs.cz."""
    TITLE_SELECTOR = 'h1[data-qa="job-ad-title"], h1'
    COMPANY_SELECTOR = '[data-qa="job-ad-company"], .typography-company-name, .company-title, div.company'
    DESCRIPTION_SELECTOR = '[data-qa="job-ad-body"], .rich-text, .standalone.cp, .cp-job-ad-body'


class PraceCzScraper(CzechJobScraper):
    """Scraper specializovaný na portál Prace.cz."""
    TITLE_SELECTOR = 'h1.job-title, h1[data-qa="job-ad-title"], h1'
    COMPANY_SELECTOR = '.employer, .company, .detail__company, [data-qa="job-ad-company"]'
    DESCRIPTION_SELECTOR = '[data-qa="job-ad-body"], .rich-text, .description, .detail__description, .job-text'


class VolnamistaScraper(CzechJobScraper):
    """Scraper specializovaný na portál Volnamista.cz."""
    TITLE_SELECTOR = "h1"
    COMPANY_SELECTOR = ".company-name, .employer"
    DESCRIPTION_SELECTOR = '[data-qa="job-ad-body"], .job-description, .content, .description'


class ProfesiaScraper(CzechJobScraper):
    """Scraper specializovaný na portál Profesia.cz."""
    TITLE_SELECTOR = "h1"
    COMPANY_SELECTOR = ".employer, .company-name"
    DESCRIPTION_SELECTOR = ".job-description, .description, #description"


class StartupJobsScraper(CzechJobScraper):
    """Scraper specializovaný na portál StartupJobs.cz."""
    TITLE_SELECTOR = "h1"
    COMPANY_SELECTOR = 'a[href*="/startup/"], .company-name, .employer-name, div.company, h2 a'
    DESCRIPTION_SELECTOR = ".description, .job-description, .content"
