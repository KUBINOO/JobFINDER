import asyncio
from datetime import datetime, timezone, date
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

from schemas_v2 import RawJobPayload
from agents.workers.base import BaseRemoteWorker
from agents.workers.jobspy_worker import (
    JobSpyWorker, 
    _clean_str, 
    _format_salary, 
    _parse_published_at
)
from agents.dispatcher import DispatcherAgent


class TestJobSpyWorkerUnit(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.worker = JobSpyWorker(timeout=5.0)

    def test_worker_inheritance_and_properties(self):
        """Worker must inherit from BaseRemoteWorker with correct defaults."""
        self.assertIsInstance(self.worker, BaseRemoteWorker)
        self.assertEqual(self.worker.name, "JobSpy")
        self.assertEqual(self.worker.timeout, 5.0)
        self.assertIn("linkedin", self.worker.default_sites)
        self.assertIn("indeed", self.worker.default_sites)
        self.assertIn("glassdoor", self.worker.default_sites)

    def test_determine_location_parameters_cz(self):
        """CZ market adapts location to Czech Republic and country_indeed to czech republic."""
        params = self.worker._determine_location_parameters(
            query="python developer",
            market="cz",
            explicit_location=None
        )
        self.assertEqual(params["location"], "Czech Republic")
        self.assertEqual(params["country_indeed"], "czech republic")
        self.assertFalse(params["is_remote"])

    def test_determine_location_parameters_prague_query(self):
        """Queries mentioning Prague/Praha adapt location to Prague, Czechia."""
        params = self.worker._determine_location_parameters(
            query="Python Developer Praha",
            market="cz",
            explicit_location=None
        )
        self.assertEqual(params["location"], "Prague, Czechia")
        self.assertEqual(params["country_indeed"], "czech republic")
        self.assertFalse(params["is_remote"])

    def test_determine_location_parameters_brno_query(self):
        """Queries mentioning Brno adapt location to Brno, Czechia."""
        params = self.worker._determine_location_parameters(
            query="Data Engineer v Brně",
            market="global",  # Even with global market, query CZ indicator triggers CZ
            explicit_location=None
        )
        self.assertEqual(params["location"], "Brno, Czechia")
        self.assertEqual(params["country_indeed"], "czech republic")
        self.assertFalse(params["is_remote"])

    def test_determine_location_parameters_hybrid(self):
        """Hybrid market defaults to Czech Republic with remote enabled."""
        params = self.worker._determine_location_parameters(
            query="Fullstack Engineer",
            market="hybrid",
            explicit_location=None
        )
        self.assertEqual(params["location"], "Czech Republic")
        self.assertEqual(params["country_indeed"], "czech republic")
        self.assertTrue(params["is_remote"])

    def test_determine_location_parameters_global(self):
        """Global market defaults to USA/remote without explicit location."""
        params = self.worker._determine_location_parameters(
            query="DevOps Engineer",
            market="global",
            explicit_location=None
        )
        self.assertIsNone(params["location"])
        self.assertEqual(params["country_indeed"], "usa")
        self.assertTrue(params["is_remote"])

    def test_determine_location_parameters_explicit_override(self):
        """Explicit location parameter overrides market defaults."""
        params = self.worker._determine_location_parameters(
            query="Software Architect",
            market="global",
            explicit_location="Berlin, Germany"
        )
        self.assertEqual(params["location"], "Berlin, Germany")
        self.assertEqual(params["country_indeed"], "usa")
        self.assertFalse(params["is_remote"])

    def test_helper_clean_str(self):
        """_clean_str handles None, NaN, and whitespace properly."""
        self.assertEqual(_clean_str(None, "default"), "default")
        self.assertEqual(_clean_str(float("nan"), "default"), "default")
        self.assertEqual(_clean_str("nan", "default"), "default")
        self.assertEqual(_clean_str("  Hello World  "), "Hello World")

    def test_helper_format_salary(self):
        """_format_salary formats single and range salary bounds."""
        row_range = pd.Series({
            "min_amount": 80000,
            "max_amount": 120000,
            "currency": "USD",
            "interval": "yearly"
        })
        self.assertEqual(_format_salary(row_range), "80000 - 120000 USD/yearly")

        row_min_only = pd.Series({
            "min_amount": 95000,
            "max_amount": None,
            "currency": "EUR",
            "interval": "year"
        })
        self.assertEqual(_format_salary(row_min_only), "95000+ EUR/year")

        row_none = pd.Series({
            "min_amount": None,
            "max_amount": None
        })
        self.assertIsNone(_format_salary(row_none))

    def test_helper_parse_published_at(self):
        """_parse_published_at correctly parses dates, datetimes, and pandas timestamps."""
        d = date(2026, 9, 1)
        parsed_d = _parse_published_at(d)
        self.assertEqual(parsed_d, datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc))

        dt_naive = datetime(2026, 9, 2, 10, 30)
        parsed_dt = _parse_published_at(dt_naive)
        self.assertEqual(parsed_dt.tzinfo, timezone.utc)

        ts = pd.Timestamp("2026-09-03 15:00:00")
        parsed_ts = _parse_published_at(ts)
        self.assertIsInstance(parsed_ts, datetime)

        self.assertIsNone(_parse_published_at(None))
        self.assertIsNone(_parse_published_at(float("nan")))

    async def test_normalization_and_mapping(self):
        """Verifies full mapping of JobSpy DataFrame to RawJobPayload list."""
        mock_df = pd.DataFrame([
            {
                "site": "linkedin",
                "job_url": "https://www.linkedin.com/jobs/view/1001",
                "job_url_direct": "https://company.com/apply/1001",
                "title": "Senior Python Backend Developer",
                "company": "Acme Corp",
                "location": "Prague, Czechia",
                "date_posted": "2026-09-01",
                "job_type": "fulltime",
                "min_amount": 100000,
                "max_amount": 140000,
                "currency": "CZK",
                "interval": "monthly",
                "skills": "Python, FastAPI, Docker",
                "description": "We are looking for a Senior Python Developer with FastAPI expertise to build modern cloud services."
            },
            {
                "site": "indeed",
                "job_url": "https://cz.indeed.com/viewjob?jk=2002",
                "job_url_direct": None,
                "title": "Python Data Engineer",
                "company": "Data Insights s.r.o.",
                "location": "Brno",
                "date_posted": "2026-09-02",
                "job_type": "contract",
                "min_amount": None,
                "max_amount": None,
                "currency": None,
                "interval": None,
                "skills": "Python, SQL, ETL",
                "description": "Join our data team to build high-throughput ETL pipelines with Python and SQL in Brno."
            },
            {
                "site": "glassdoor",
                "job_url": "https://www.glassdoor.com/job-listing/3003",
                "job_url_direct": None,
                "title": "Lead Python Architect",
                "company": "Global Cloud Inc.",
                "location": "Remote",
                "date_posted": "2026-09-03",
                "job_type": "fulltime",
                "min_amount": 150000,
                "max_amount": 180000,
                "currency": "USD",
                "interval": "year",
                "skills": "Python, AWS, Architecture",
                "description": "Lead our cloud architecture and backend platforms using Python and AWS microservices."
            }
        ])

        with patch.object(self.worker, "_execute_jobspy_scrape", return_value=mock_df):
            jobs = await self.worker.fetch_jobs(query="Python", limit=10, market="cz")

        self.assertEqual(len(jobs), 3)

        # 1. LinkedIn item
        j1 = jobs[0]
        self.assertEqual(j1.source_portal, "JobSpy (LinkedIn)")
        self.assertEqual(j1.source_url, "https://www.linkedin.com/jobs/view/1001")
        self.assertEqual(j1.apply_url, "https://company.com/apply/1001")
        self.assertEqual(j1.title, "Senior Python Backend Developer")
        self.assertEqual(j1.company_name, "Acme Corp")
        self.assertEqual(j1.raw_location, "Prague, Czechia")
        self.assertEqual(j1.raw_salary, "100000 - 140000 CZK/monthly")
        self.assertIn("fastapi", j1.raw_tags)
        self.assertIn("linkedin", j1.raw_tags)
        self.assertIsNotNone(j1.published_at)

        # 2. Indeed item
        j2 = jobs[1]
        self.assertEqual(j2.source_portal, "JobSpy (Indeed)")
        self.assertEqual(j2.source_url, "https://cz.indeed.com/viewjob?jk=2002")
        self.assertEqual(j2.apply_url, "https://cz.indeed.com/viewjob?jk=2002")
        self.assertEqual(j2.title, "Python Data Engineer")
        self.assertIsNone(j2.raw_salary)

        # 3. Glassdoor item
        j3 = jobs[2]
        self.assertEqual(j3.source_portal, "JobSpy (Glassdoor)")
        self.assertEqual(j3.raw_salary, "150000 - 180000 USD/year")

    async def test_semantic_relevance_filtering(self):
        """Irrelevant jobs (e.g. Civil Engineer, Housekeeper) must be eliminated by relevance filter."""
        mock_df = pd.DataFrame([
            {
                "site": "indeed",
                "job_url": "https://indeed.com/viewjob?jk=relevant",
                "job_url_direct": None,
                "title": "Senior Python Backend Developer",
                "company": "Tech Corp",
                "location": "Remote",
                "date_posted": "2026-09-01",
                "job_type": "fulltime",
                "min_amount": None,
                "max_amount": None,
                "currency": None,
                "interval": None,
                "skills": "Python, Django",
                "description": "Building microservices with Python and Django."
            },
            {
                "site": "indeed",
                "job_url": "https://indeed.com/viewjob?jk=irrelevant1",
                "job_url_direct": None,
                "title": "Civil Engineer / Bridge Designer",
                "company": "Build Corp",
                "location": "New York",
                "date_posted": "2026-09-01",
                "job_type": "fulltime",
                "min_amount": None,
                "max_amount": None,
                "currency": None,
                "interval": None,
                "skills": "AutoCAD, Construction",
                "description": "Designing bridges and concrete structures for highway projects."
            },
            {
                "site": "linkedin",
                "job_url": "https://linkedin.com/jobs/view/irrelevant2",
                "job_url_direct": None,
                "title": "Executive Housekeeper & Hotel Cleaner",
                "company": "Grand Hotel",
                "location": "Prague",
                "date_posted": "2026-09-01",
                "job_type": "fulltime",
                "min_amount": None,
                "max_amount": None,
                "currency": None,
                "interval": None,
                "skills": "Cleaning, Management",
                "description": "Responsible for managing housekeeping operations at luxury hotel."
            }
        ])

        with patch.object(self.worker, "_execute_jobspy_scrape", return_value=mock_df):
            jobs = await self.worker.fetch_jobs(query="Python Developer", limit=10)

        # Only the relevant Python job should pass
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Senior Python Backend Developer")

    async def test_part_time_filtering(self):
        """When part_time_only=True, full-time listings are excluded."""
        mock_df = pd.DataFrame([
            {
                "site": "indeed",
                "job_url": "https://indeed.com/viewjob?jk=ft",
                "job_url_direct": None,
                "title": "Python Developer (Full-time)",
                "company": "Full Corp",
                "location": "Remote",
                "date_posted": "2026-09-01",
                "job_type": "fulltime",
                "min_amount": None,
                "max_amount": None,
                "currency": None,
                "interval": None,
                "skills": "Python",
                "description": "Full time role 40 hours per week only."
            },
            {
                "site": "indeed",
                "job_url": "https://indeed.com/viewjob?jk=pt",
                "job_url_direct": None,
                "title": "Python Developer (Part-time)",
                "company": "Flex Tech",
                "location": "Remote",
                "date_posted": "2026-09-01",
                "job_type": "parttime",
                "min_amount": None,
                "max_amount": None,
                "currency": None,
                "interval": None,
                "skills": "Python",
                "description": "Flexible part-time 20 hours/week contractor role."
            }
        ])

        with patch.object(self.worker, "_execute_jobspy_scrape", return_value=mock_df):
            jobs = await self.worker.fetch_jobs(query="Python", part_time_only=True)

        self.assertEqual(len(jobs), 1)
        self.assertIn("Part-time", jobs[0].title)

    async def test_graceful_degradation_on_exception(self):
        """Rate limits, anti-bot blocks, or network errors must be caught gracefully and return []."""
        with patch.object(
            self.worker, 
            "_execute_jobspy_scrape", 
            side_effect=RuntimeError("TLS Client Cloudflare Challenge Blocked 403")
        ):
            jobs = await self.worker.fetch_jobs(query="Python Developer")

        self.assertEqual(jobs, [])

    async def test_graceful_degradation_on_timeout(self):
        """Worker times out gracefully without unhandled exceptions."""
        with patch.object(self.worker, "_execute_jobspy_scrape", side_effect=TimeoutError("Timed out")):
            jobs = await self.worker.fetch_jobs(query="Python Developer")

        self.assertEqual(jobs, [])

    async def test_empty_dataframe_handling(self):
        """Empty DataFrame returns empty list."""
        with patch.object(self.worker, "_execute_jobspy_scrape", return_value=pd.DataFrame()):
            jobs = await self.worker.fetch_jobs(query="Python Developer")
        self.assertEqual(jobs, [])


class TestDispatcherJobSpyIntegration(unittest.IsolatedAsyncioTestCase):
    def test_dispatcher_registers_jobspy_worker(self):
        """DispatcherAgent must have JobSpyWorker registered in global_workers."""
        dispatcher = DispatcherAgent()
        worker_classes = [w.__class__.__name__ for w in dispatcher.global_workers]
        self.assertIn("JobSpyWorker", worker_classes)

        jobspy_instance = next(w for w in dispatcher.global_workers if isinstance(w, JobSpyWorker))
        self.assertEqual(jobspy_instance.name, "JobSpy")

    async def test_dispatcher_executes_jobspy_in_global_market(self):
        """DispatcherAgent runs JobSpyWorker during global search and normalizes output."""
        dispatcher = DispatcherAgent()

        mock_payload = RawJobPayload(
            source_portal="JobSpy (LinkedIn)",
            source_url="https://linkedin.com/jobs/view/999",
            title="Senior Python Engineer",
            company_name="Global Innovations",
            description="Detailed job description of Senior Python Engineer with cloud and microservices.",
            raw_location="Worldwide / Remote",
            raw_tags=["linkedin", "python", "remote"]
        )

        # Patch all workers in global_workers to return mock data
        for w in dispatcher.global_workers:
            if isinstance(w, JobSpyWorker):
                w.fetch_jobs = unittest.mock.AsyncMock(return_value=[mock_payload])
            else:
                w.fetch_jobs = unittest.mock.AsyncMock(return_value=[])

        state = await dispatcher.execute_search(
            query="Python Engineer",
            count=5,
            market="global",
            timezone_preference="ALL"
        )

        self.assertEqual(state.status, "COMPLETED")
        self.assertIn("JobSpy", state.worker_counts)
        self.assertEqual(state.worker_counts["JobSpy"], 1)
        self.assertGreaterEqual(len(state.normalized_listings), 1)
        self.assertEqual(state.normalized_listings[0].company_name, "Global Innovations")

    async def test_dispatcher_executes_jobspy_in_cz_market(self):
        """DispatcherAgent runs JobSpyWorker adapted for CZ market alongside CzechJobScrapers."""
        dispatcher = DispatcherAgent()

        mock_jobspy_cz = RawJobPayload(
            source_portal="JobSpy (Indeed)",
            source_url="https://cz.indeed.com/viewjob?jk=cz1",
            title="Backend Developer Python",
            company_name="Prague Tech Lab",
            description="Developing backend solutions in Prague with Python and FastAPI for enterprise clients.",
            raw_location="Prague, Czechia",
            raw_tags=["indeed", "cz", "python"]
        )

        for w in dispatcher.global_workers:
            if isinstance(w, JobSpyWorker):
                w.fetch_jobs = unittest.mock.AsyncMock(return_value=[mock_jobspy_cz])
            else:
                w.fetch_jobs = unittest.mock.AsyncMock(return_value=[])

        # Patch CzechJobScraper
        with patch("scrapers.search.JobSearchScraper") as mock_cz_scraper_cls:
            mock_cz_inst = MagicMock()
            mock_cz_inst.__aenter__ = unittest.mock.AsyncMock(return_value=mock_cz_inst)
            mock_cz_inst.__aexit__ = unittest.mock.AsyncMock(return_value=None)
            mock_cz_inst.search_jobs = unittest.mock.AsyncMock(return_value=[])
            mock_cz_scraper_cls.return_value = mock_cz_inst

            state = await dispatcher.execute_search(
                query="Python",
                count=5,
                market="cz",
                timezone_preference="EMEA_ONLY"
            )

        self.assertEqual(state.status, "COMPLETED")
        self.assertIn("JobSpy", state.worker_counts)
        self.assertEqual(state.worker_counts["JobSpy"], 1)


if __name__ == "__main__":
    unittest.main()
