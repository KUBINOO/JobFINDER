from selectolax.parser import HTMLParser
from scrapers.base import AbstractCSSScraper
from schemas import ScrapedJob

class CzechJobScraper(AbstractCSSScraper):
    async def extract_job_details(self, url: str) -> ScrapedJob:
        try:
            response = await self.client.get(url)
            tree = HTMLParser(response.text)
            
            title_node = tree.css_first(self.TITLE_SELECTOR)
            company_node = tree.css_first(self.COMPANY_SELECTOR)
            desc_node = tree.css_first(self.DESCRIPTION_SELECTOR)

            title = title_node.text(strip=True) if title_node else ""
            company = company_node.text(strip=True) if company_node else "Neznámá společnost"
            description = desc_node.text(strip=True) if desc_node else ""

            if not title:
                title_node = tree.css_first("h1") or tree.css_first("title")
                title = title_node.text(strip=True) if title_node else "Neznámá pozice"

            # Kritický fallback: Pokud selže CSS selektor popisu nebo je stránka JS-only (krátký text)
            if not description or len(description) < 500:
                print(f"DEBUG: triggering fallback. Current desc len: {len(description)}")
                try:
                    import httpx
                    jina_url = f"https://r.jina.ai/{url}"
                    async with httpx.AsyncClient(timeout=15.0) as jina_client:
                        jina_res = await jina_client.get(jina_url)
                        jina_res.raise_for_status()
                        jina_text = jina_res.text
                    print(f"DEBUG: jina_text len: {len(jina_text)}")
                    
                    # Pokus o extrakci titulku z Jina AI (Title: ...)
                    if "Title: " in jina_text:
                        jina_title = jina_text.split("Title: ")[1].split("\n")[0].strip()
                        if jina_title:
                            # 1. Zkusíme extrahovat název společnosti z titulku
                            if not company or company == "Neznámá společnost":
                                for sep in [" – ", " - ", " | ", " at "]:
                                    if sep in jina_title:
                                        parts = jina_title.split(sep)
                                        # Poslední část je většinou název společnosti
                                        potential_company = parts[-1].strip()
                                        if potential_company:
                                            company = potential_company
                                            # Volitelně ořízneme title, aby neobsahoval název společnosti
                                            jina_title = sep.join(parts[:-1]).strip()
                                        break
                                        
                            # 2. Aktualizujeme samotný název pozice
                            if not title or title == "Neznámá pozice":
                                title = jina_title
                            
                    description = jina_text
                except Exception as jina_e:
                    print(f"DEBUG: Jina failed: {jina_e}")
                    # Původní fallback
                    for tag in tree.css("nav, footer, header, aside, script, style, noscript"):
                        tag.decompose()
                    
                    fallback_node = tree.css_first("main") or tree.css_first("body")
                    if fallback_node:
                        description = fallback_node.text(strip=True)
                    else:
                        description = "Nepodařilo se vyextrahovat obsah inzerátu."

            return ScrapedJob(
                source_url=url, # type: ignore
                title=title,
                company_name=company,
                description=description
            )
        except Exception as e:
            # Záznam chyby pro debugging
            raise Exception(f"Chyba při scrapování {url}: {e}") from e


class JobsCzScraper(CzechJobScraper):
    TITLE_SELECTOR = "h1"
    COMPANY_SELECTOR = ".typography-company-name, .company-title, div.company"
    DESCRIPTION_SELECTOR = ".job-description, div.description, .typography-body"


class PraceCzScraper(CzechJobScraper):
    TITLE_SELECTOR = "h1.job-title, h1"
    COMPANY_SELECTOR = ".employer, .company, .detail__company"
    DESCRIPTION_SELECTOR = ".description, .detail__description, .job-text"


class VolnamistaScraper(CzechJobScraper):
    TITLE_SELECTOR = "h1"
    COMPANY_SELECTOR = ".company-name, .employer"
    DESCRIPTION_SELECTOR = ".job-description, .content, .description"


class ProfesiaScraper(CzechJobScraper):
    TITLE_SELECTOR = "h1"
    COMPANY_SELECTOR = ".employer, .company-name"
    DESCRIPTION_SELECTOR = ".job-description, .description, #description"


class StartupJobsScraper(CzechJobScraper):
    TITLE_SELECTOR = "h1"
    COMPANY_SELECTOR = ".company-name, .employer-name, div.company"
    DESCRIPTION_SELECTOR = ".description, .job-description, .content"
