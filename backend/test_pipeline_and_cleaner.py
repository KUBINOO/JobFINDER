import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from selectolax.parser import HTMLParser

from scrapers.cleaner import DOMCleaner
from scrapers.providers import JobsCzScraper, PraceCzScraper
from orchestrator import _run_scraping, JobContentValidationError, process_job_application
from models import Application, JobPosting, ApplicationStatus, User
from schemas import ScrapedJob


class TestDOMCleaner(unittest.TestCase):
    def test_strip_unwanted_tags(self):
        html = """
        <html>
            <head><title>Test Title</title><style>body { color: red; }</style></head>
            <body>
                <header><nav><a href="/home">Home</a></nav></header>
                <div class="job-content">
                    <h1>Senior Developer</h1>
                    <p>Skvělá pracovní pozice v Praze pro zkušeného vývojáře.</p>
                </div>
                <footer><p>© 2026 Všechna práva vyhrazena</p></footer>
                <script>console.log('tracker');</script>
            </body>
        </html>
        """
        tree = HTMLParser(html)
        DOMCleaner.clean_tree(tree)
        
        self.assertIsNone(tree.css_first("nav"))
        self.assertIsNone(tree.css_first("footer"))
        self.assertIsNone(tree.css_first("header"))
        self.assertIsNone(tree.css_first("script"))
        self.assertIsNone(tree.css_first("style"))
        
        text = DOMCleaner.extract_clean_text(tree)
        self.assertIn("Senior Developer", text)
        self.assertIn("Skvělá pracovní pozice", text)
        self.assertNotIn("Home", text)
        self.assertNotIn("Všechna práva vyhrazena", text)

    def test_strip_boilerplate_classes_and_ids(self):
        html = """
        <div>
            <div class="cookie-banner-popup">Souhlasíte s cookies?</div>
            <div id="social-share-buttons"><a href="#">Sdílet na LinkedIn</a></div>
            <div class="navigation-menu-links"><ul><li>O nás</li><li>Kariéra</li></ul></div>
            <div class="main-body">
                <p>Hledáme nového kolegu do týmu.</p>
            </div>
        </div>
        """
        tree = HTMLParser(html)
        DOMCleaner.clean_tree(tree)
        
        text = DOMCleaner.extract_clean_text(tree)
        self.assertNotIn("cookies", text)
        self.assertNotIn("Sdílet", text)
        self.assertNotIn("O nás", text)
        self.assertIn("Hledáme nového kolegu do týmu.", text)

    def test_extract_semantic_text(self):
        html = """
        <div>
            <div class="link-cloud">
                <a href="#">Práce Praha</a> <a href="#">Práce Brno</a> <a href="#">IT pozice</a>
            </div>
            <h3>O pozici</h3>
            <p>Budete se podílet na vývoji moderních webových aplikací v Reactu a Pythonu.</p>
            <h4>Požadujeme:</h4>
            <ul>
                <li>Znalost Pythonu a FastAPI</li>
                <li>Zkušenost s PostgreSQL</li>
            </ul>
        </div>
        """
        tree = HTMLParser(html)
        semantic_text = DOMCleaner.extract_semantic_text(tree)
        
        self.assertNotIn("Práce Praha", semantic_text)
        self.assertIn("O pozici", semantic_text)
        self.assertIn("Budete se podílet na vývoji", semantic_text)
        self.assertIn("• Znalost Pythonu a FastAPI", semantic_text)

    def test_find_iframe_src(self):
        html = """
        <div class="standalone cp">
            <iframe class="cp-iframe" src="https://jobs.example.cz/ad-detail/12345"></iframe>
        </div>
        """
        tree = HTMLParser(html)
        src = DOMCleaner.find_iframe_src(tree)
        self.assertEqual(src, "https://jobs.example.cz/ad-detail/12345")


class TestScrapers(unittest.IsolatedAsyncioTestCase):
    async def test_jobscz_priority_selectors(self):
        html = """
        <html>
            <body>
                <h1 data-qa="job-ad-title">Senior Python Engineer</h1>
                <div data-qa="job-ad-company">Tech Corp s.r.o.</div>
                <div data-qa="job-ad-body">
                    <p>Hledáme zkušeného vývojáře pro backend našeho klíčového produktu. Náplní práce je návrh a vývoj škálovatelných mikroservis v Pythonu a integrace s moderními cloudovými službami. Požadujeme praxi s relačními databázemi a automatizovaným testováním.</p>
                </div>
            </body>
        </html>
        """
        scraper = JobsCzScraper()
        mock_response = MagicMock()
        mock_response.text = html
        scraper.client = MagicMock()
        scraper.client.get = AsyncMock(return_value=mock_response)
        
        job = await scraper.extract_job_details("https://www.jobs.cz/rpd/123456")
        self.assertEqual(job.title, "Senior Python Engineer")
        self.assertEqual(job.company_name, "Tech Corp s.r.o.")
        self.assertIn("Hledáme zkušeného vývojáře", job.description)
        self.assertGreaterEqual(len(job.description), 150)

    async def test_jobscz_iframe_ad(self):
        main_html = """
        <html>
            <body>
                <h1>Frontend Architect</h1>
                <div class="company-title">Innovation Hub</div>
                <div class="standalone cp">
                    <iframe src="/embedded/ad-123.html"></iframe>
                </div>
            </body>
        </html>
        """
        iframe_html = """
        <html>
            <body>
                <h2>Popis pracovní pozice</h2>
                <p>Do našeho rostoucího týmu hledáme Frontend Architekta, který bude řídit technický směr a standardy pro aplikace s miliony návštěvníků měsíčně. Požadujeme hlubokou znalost TypeScriptu, React ekosystému a architektury moderních webových aplikací.</p>
            </body>
        </html>
        """
        scraper = JobsCzScraper()
        
        main_resp = MagicMock()
        main_resp.text = main_html
        
        iframe_resp = MagicMock()
        iframe_resp.text = iframe_html
        
        async def mock_get(url, **kwargs):
            if "embedded" in url:
                return iframe_resp
            return main_resp
            
        scraper.client = MagicMock()
        scraper.client.get = AsyncMock(side_effect=mock_get)
        
        job = await scraper.extract_job_details("https://www.jobs.cz/rpd/999999")
        self.assertEqual(job.title, "Frontend Architect")
        self.assertEqual(job.company_name, "Innovation Hub")
        self.assertIn("Frontend Architekta", job.description)
        self.assertGreaterEqual(len(job.description), 150)


class TestQualityGate(unittest.IsolatedAsyncioTestCase):
    async def test_quality_gate_raises_on_short_description(self):
        session = MagicMock()
        application = MagicMock()
        job = MagicMock()
        job.source_url = "https://www.jobs.cz/rpd/invalid"
        application.job_posting = job
        
        mock_scraper = MagicMock()
        mock_scraper.extract_job_details = AsyncMock(return_value=ScrapedJob(
            source_url="https://www.jobs.cz/rpd/invalid",
            title="Nějaká pozice",
            company_name="Nějaká firma",
            description="Příliš krátký text." # Pouze cca 20 znaků (< 150)
        ))
        
        with patch("orchestrator.get_scraper", return_value=mock_scraper):
            with self.assertRaises(JobContentValidationError) as ctx:
                await _run_scraping(session, application)
                
            self.assertIn("Inzerát neobsahuje čitelný popis pracovní pozice", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
