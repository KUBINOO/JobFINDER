"""
Adversarial Stress & Resilience Test Suite for Module 1 (JobSpy) & Module 2 (Discord Alerts).
Author: Challenger 1 (critic, specialist).
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone, date
from pathlib import Path
import pandas as pd
import httpx

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from agents.workers.jobspy_worker import (
    JobSpyWorker,
    _clean_str,
    _format_salary,
    _parse_published_at,
)
from agents.dispatcher import DispatcherAgent
from services.discord_service import (
    send_discord_high_match_alert,
    build_discord_embed,
    format_discord_alert_payload,
    format_pros_bullets,
    DEFAULT_MIN_MATCH_SCORE,
)
from schemas_v2 import RawJobPayload


class TestJobSpyAdversarialResilience(unittest.IsolatedAsyncioTestCase):
    """Adversarial stress-testing of JobSpyWorker."""

    def setUp(self):
        self.worker = JobSpyWorker(timeout=2.0)

    # -------------------------------------------------------------------------
    # 1. Rate Limit Simulation (HTTP 429) & Bot Challenges
    # -------------------------------------------------------------------------
    async def test_jobspy_rate_limit_http_429_exception(self):
        """Simulate HTTP 429 Too Many Requests raised from underlying scraping layer."""
        class HTTP429Error(Exception):
            pass

        with patch.object(self.worker, "_execute_jobspy_scrape", side_effect=HTTP429Error("HTTP 429: Too Many Requests - Rate Limit Exceeded")):
            jobs = await self.worker.fetch_jobs(query="Python", limit=10)
            self.assertEqual(jobs, [])

    async def test_jobspy_cloudflare_turnstile_challenge(self):
        """Simulate Cloudflare Turnstile / 403 Forbidden Challenge block."""
        with patch.object(self.worker, "_execute_jobspy_scrape", side_effect=RuntimeError("Cloudflare 1020: Access Denied / WAF Challenge")):
            jobs = await self.worker.fetch_jobs(query="FastAPI", limit=10)
            self.assertEqual(jobs, [])

    async def test_jobspy_partial_rate_limit(self):
        """Simulate partial scrape before rate limit / network error occurs."""
        # When scrape returns DataFrame with 2 items, worker processes both safely
        partial_df = pd.DataFrame([
            {
                "site": "linkedin",
                "job_url": "https://linkedin.com/jobs/view/1",
                "title": "Backend Python Developer",
                "company": "Company A",
                "location": "Prague",
                "date_posted": "2026-09-01",
            },
            {
                "site": "indeed",
                "job_url": "https://indeed.com/viewjob?jk=2",
                "title": "Senior Python Engineer",
                "company": "Company B",
                "location": "Brno",
                "date_posted": "2026-09-01",
            }
        ])
        with patch.object(self.worker, "_execute_jobspy_scrape", return_value=partial_df):
            jobs = await self.worker.fetch_jobs(query="Python", limit=10)
            self.assertEqual(len(jobs), 2)
            self.assertEqual(jobs[0].title, "Backend Python Developer")
            self.assertEqual(jobs[1].title, "Senior Python Engineer")

    # -------------------------------------------------------------------------
    # 2. Timeouts & Event Loop Non-Blocking
    # -------------------------------------------------------------------------
    async def test_jobspy_thread_hang_timeout(self):
        """Simulate underlying scraper freezing or hanging indefinitely in a thread."""
        def slow_blocking_scrape(*args, **kwargs):
            import time
            time.sleep(5.0)  # Exceeds worker.timeout = 2.0s
            return pd.DataFrame()

        with patch.object(self.worker, "_execute_jobspy_scrape", side_effect=slow_blocking_scrape):
            start = asyncio.get_event_loop().time()
            jobs = await self.worker.fetch_jobs(query="Python", limit=10)
            elapsed = asyncio.get_event_loop().time() - start

            self.assertEqual(jobs, [])
            # Must abort close to timeout (2.0s), not hang for 5s
            self.assertLess(elapsed, 3.5)

    async def test_jobspy_asyncio_timeout_error(self):
        """Simulate asyncio.TimeoutError raised directly by wait_for."""
        with patch.object(self.worker, "_execute_jobspy_scrape", side_effect=asyncio.TimeoutError()):
            jobs = await self.worker.fetch_jobs(query="Python", limit=5)
            self.assertEqual(jobs, [])

    # -------------------------------------------------------------------------
    # 3. Malformed HTML / DataFrame Stress Testing
    # -------------------------------------------------------------------------
    async def test_jobspy_empty_and_corrupt_dataframes(self):
        """Test completely empty, None, or column-corrupted DataFrames."""
        test_cases = [
            None,
            pd.DataFrame(),
            pd.DataFrame(columns=["unrelated_col_1", "unrelated_col_2"]),
            pd.DataFrame([{"unrelated": 123}, {"broken": None}]),
        ]
        for corrupt_input in test_cases:
            with patch.object(self.worker, "_execute_jobspy_scrape", return_value=corrupt_input):
                jobs = await self.worker.fetch_jobs(query="Python")
                self.assertEqual(jobs, [])

    async def test_jobspy_dataframe_all_nan_values(self):
        """Test DataFrame containing all NaN / None values."""
        nan_df = pd.DataFrame([
            {
                "site": None,
                "job_url": None,
                "job_url_direct": None,
                "title": None,
                "company": None,
                "location": None,
                "date_posted": None,
                "job_type": None,
                "min_amount": None,
                "max_amount": None,
                "currency": None,
                "interval": None,
                "skills": None,
                "description": None,
            },
            {
                "site": float("nan"),
                "job_url": float("nan"),
                "job_url_direct": float("nan"),
                "title": float("nan"),
                "company": float("nan"),
                "location": float("nan"),
                "date_posted": float("nan"),
                "job_type": float("nan"),
                "min_amount": float("nan"),
                "max_amount": float("nan"),
                "currency": float("nan"),
                "interval": float("nan"),
                "skills": float("nan"),
                "description": float("nan"),
            }
        ])
        with patch.object(self.worker, "_execute_jobspy_scrape", return_value=nan_df):
            jobs = await self.worker.fetch_jobs(query="Python")
            # Rows with missing title or url are safely skipped
            self.assertEqual(jobs, [])

    async def test_jobspy_dataframe_with_string_and_invalid_salaries(self):
        """Test resilient salary formatting when amounts are strings, negative, or invalid."""
        row_str_salary = pd.Series({
            "min_amount": "100000",
            "max_amount": "140000",
            "currency": "EUR",
            "interval": "year"
        })
        # If min_amount is str, _format_salary should either parse or degrade gracefully without unhandled crash
        try:
            res = _format_salary(row_str_salary)
        except Exception as e:
            self.fail(f"_format_salary crashed on string salary: {e}")

        # Negative and zero salaries
        row_zero = pd.Series({"min_amount": 0, "max_amount": 0})
        self.assertIsNone(_format_salary(row_zero))

        row_neg = pd.Series({"min_amount": -500, "max_amount": -100})
        self.assertIsNone(_format_salary(row_neg))

    async def test_jobspy_dataframe_with_unexpected_types_in_columns(self):
        """Test columns containing lists, dicts, ints where strings or dates are expected."""
        weird_df = pd.DataFrame([
            {
                "site": "linkedin",
                "job_url": "https://linkedin.com/jobs/view/weird1",
                "title": "Python Developer",
                "company": 12345,  # int company name
                "location": ["Remote", "EU"],  # list in location
                "date_posted": 1725530000,  # unix timestamp int
                "job_type": ["contract", "parttime"],  # list in job_type
                "skills": {"python": True, "fastapi": True},  # dict in skills
                "description": "Valid description with Python and backend development.",
            }
        ])
        with patch.object(self.worker, "_execute_jobspy_scrape", return_value=weird_df):
            # Must not raise unhandled exception
            try:
                jobs = await self.worker.fetch_jobs(query="Python")
                self.assertIsInstance(jobs, list)
            except Exception as e:
                self.fail(f"JobSpyWorker crashed on unexpected DataFrame types: {e}")

    async def test_jobspy_malformed_dates(self):
        """Test _parse_published_at handles corrupted date strings and formats."""
        corrupt_dates = [
            "Yesterday",
            "30+ days ago",
            "2026-99-99",
            "not a date",
            {"year": 2026},
            [2026, 9, 1],
            "",
            None,
        ]
        for d in corrupt_dates:
            try:
                res = _parse_published_at(d)
                self.assertTrue(res is None or isinstance(res, datetime))
            except Exception as e:
                self.fail(f"_parse_published_at crashed on input '{d}': {e}")

    # -------------------------------------------------------------------------
    # 4. Special Characters, Unicode & Injections
    # -------------------------------------------------------------------------
    async def test_jobspy_special_characters_and_regex_in_query(self):
        """Test query with regex metacharacters, punctuation, emojis, and SQL injection strings."""
        adversarial_queries = [
            r"[a-z]+.*?(foo|bar)$^\[\](){}+*?|\\",
            "'; DROP TABLE jobs; -- ' OR 1=1",
            "🐍 Python Vývojář 🚀 开发者 (C++/FastAPI)",
            "!!! @@@ ### $$$ %%% ^^^ &&& *** ((( )))",
            "   \t\r\n   ",
            "a" * 1000,  # 1000 char query
            "null\x00byte\x01injection",
        ]
        for q in adversarial_queries:
            with patch.object(self.worker, "_execute_jobspy_scrape", return_value=pd.DataFrame()):
                try:
                    jobs = await self.worker.fetch_jobs(query=q)
                    self.assertEqual(jobs, [])
                except Exception as e:
                    self.fail(f"fetch_jobs crashed on query '{q[:30]}...': {e}")

    async def test_jobspy_extreme_html_and_text_lengths(self):
        """Test huge description with HTML tags, script injection, and null bytes."""
        huge_html = "<div>" + "<script>alert('xss');</script><p>Python Backend</p>" * 500 + "</div>"
        df = pd.DataFrame([
            {
                "site": "indeed",
                "job_url": "https://indeed.com/viewjob?jk=huge",
                "title": "Python Developer " + "🌟" * 50,
                "company": "Safe Corp",
                "description": huge_html,
                "date_posted": "2026-09-01",
            }
        ])
        with patch.object(self.worker, "_execute_jobspy_scrape", return_value=df):
            jobs = await self.worker.fetch_jobs(query="Python")
            self.assertEqual(len(jobs), 1)
            self.assertIn("Python Developer", jobs[0].title)

    # -------------------------------------------------------------------------
    # 5. Concurrency & Stress Testing
    # -------------------------------------------------------------------------
    async def test_jobspy_concurrent_queries_load(self):
        """Simulate 25 concurrent scraping queries under heavy load."""
        df_template = pd.DataFrame([
            {
                "site": "linkedin",
                "job_url": "https://linkedin.com/jobs/view/concurrent",
                "title": "Senior Python Backend Engineer",
                "company": "LoadTest Inc",
                "description": "Python engineering role with cloud microservices.",
                "date_posted": "2026-09-01",
            }
        ])

        with patch.object(self.worker, "_execute_jobspy_scrape", return_value=df_template):
            tasks = [
                self.worker.fetch_jobs(query=f"Python {i}", limit=5, market="global" if i % 2 == 0 else "cz")
                for i in range(25)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            self.assertEqual(len(results), 25)
            for i, res in enumerate(results):
                self.assertFalse(isinstance(res, Exception), f"Concurrent query {i} failed with {res}")
                self.assertEqual(len(res), 1)


    async def test_jobspy_silent_data_drop_on_corrupt_row(self):
        """Demonstrate that lack of per-row error isolation drops all subsequent valid jobs."""
        df_batch = pd.DataFrame([
            {"site": "linkedin", "job_url": "https://linkedin.com/jobs/view/1", "title": "Job 1", "company": "C1", "min_amount": 1000},
            {"site": "linkedin", "job_url": "https://linkedin.com/jobs/view/2", "title": "Job 2", "company": "C2", "min_amount": "1000"},  # Corrupt string
            {"site": "linkedin", "job_url": "https://linkedin.com/jobs/view/3", "title": "Job 3", "company": "C3", "min_amount": 1000},
            {"site": "linkedin", "job_url": "https://linkedin.com/jobs/view/4", "title": "Job 4", "company": "C4", "min_amount": 1000},
        ])
        with patch.object(self.worker, "_execute_jobspy_scrape", return_value=df_batch):
            jobs = await self.worker.fetch_jobs(query="Python")
            # Currently only 1 job is returned instead of 3 valid jobs because row 2 aborted the loop
            self.assertLess(len(jobs), 3, "Vulnerability confirmed: corrupt row aborts entire remaining batch")


class TestDiscordAlertsAdversarialResilience(unittest.IsolatedAsyncioTestCase):
    """Adversarial stress-testing of Discord Alert Engine."""

    WEBHOOK_URL = "https://discord.com/api/webhooks/12345/testtoken"

    async def test_discord_type_safety_exception_escape(self):
        """Verify that passing None or string match_score never escapes exceptions and returns False safely."""
        res_none = await send_discord_high_match_alert(
            job_title="Dev", company="C", match_score=None, webhook_url=self.WEBHOOK_URL
        )
        self.assertFalse(res_none)

        res_str = await send_discord_high_match_alert(
            job_title="Dev", company="C", match_score="85", webhook_url=self.WEBHOOK_URL
        )
        self.assertFalse(res_str)


    # -------------------------------------------------------------------------
    # 1. Exact 84% vs 85% Boundary & Range Extremes
    # -------------------------------------------------------------------------
    async def test_discord_boundary_84_vs_85(self):
        """Strict verification of 84% (rejected) vs 85% (triggered) boundary."""
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.text = ""

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            # 84 -> must NOT send
            res_84 = await send_discord_high_match_alert(
                job_title="Dev", company="C", match_score=84, webhook_url=self.WEBHOOK_URL
            )
            self.assertFalse(res_84)
            mock_post.assert_not_called()

            # 84.9 -> must NOT send
            res_84_9 = await send_discord_high_match_alert(
                job_title="Dev", company="C", match_score=84.9, webhook_url=self.WEBHOOK_URL
            )
            self.assertFalse(res_84_9)
            mock_post.assert_not_called()

            # 85 -> MUST send
            res_85 = await send_discord_high_match_alert(
                job_title="Dev", company="C", match_score=85, webhook_url=self.WEBHOOK_URL
            )
            self.assertTrue(res_85)
            self.assertEqual(mock_post.call_count, 1)

            # 85.0 -> MUST send
            mock_post.reset_mock()
            res_85_0 = await send_discord_high_match_alert(
                job_title="Dev", company="C", match_score=85.0, webhook_url=self.WEBHOOK_URL
            )
            self.assertTrue(res_85_0)
            self.assertEqual(mock_post.call_count, 1)

            # 100 -> MUST send
            mock_post.reset_mock()
            res_100 = await send_discord_high_match_alert(
                job_title="Dev", company="C", match_score=100, webhook_url=self.WEBHOOK_URL
            )
            self.assertTrue(res_100)
            self.assertEqual(mock_post.call_count, 1)

    async def test_discord_score_out_of_bounds_and_invalid_types(self):
        """Test negative scores, scores > 100, None, or string score inputs."""
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.text = ""

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            # Negative score
            res_neg = await send_discord_high_match_alert(
                job_title="Dev", company="C", match_score=-10, webhook_url=self.WEBHOOK_URL
            )
            self.assertFalse(res_neg)
            mock_post.assert_not_called()

            # Zero score
            res_zero = await send_discord_high_match_alert(
                job_title="Dev", company="C", match_score=0, webhook_url=self.WEBHOOK_URL
            )
            self.assertFalse(res_zero)
            mock_post.assert_not_called()

    # -------------------------------------------------------------------------
    # 2. Webhook URL Edge Cases & Missing Config
    # -------------------------------------------------------------------------
    async def test_discord_missing_or_malformed_urls(self):
        """Test empty string, spaces, invalid schemes, and None webhook URLs."""
        invalid_urls = [
            None,
            "",
            "   ",
            "\t\n",
            "not-a-url",
            "ftp://discord.com/webhook",
            "file:///etc/passwd",
            "javascript:void(0)",
            "http://",
            "https://",
        ]
        with patch.dict(os.environ, {}, clear=True):
            for bad_url in invalid_urls:
                res = await send_discord_high_match_alert(
                    job_title="Dev",
                    company="C",
                    match_score=90,
                    webhook_url=bad_url,
                )
                self.assertFalse(res, f"Expected False for bad url: '{bad_url}'")

    # -------------------------------------------------------------------------
    # 3. Network Failures, Timeouts, Socket Drops
    # -------------------------------------------------------------------------
    async def test_discord_network_exceptions(self):
        """Test graceful degradation under various httpx network exceptions."""
        exceptions_to_test = [
            httpx.TimeoutException("Read timeout"),
            httpx.ConnectTimeout("Connection timed out"),
            httpx.ConnectError("Failed to resolve host"),
            httpx.ReadError("Socket closed prematurely"),
            httpx.RemoteProtocolError("Server disconnected"),
            ConnectionResetError("Connection reset by peer"),
            OSError("Network is unreachable"),
        ]

        for exc in exceptions_to_test:
            with patch("httpx.AsyncClient.post", side_effect=exc):
                res = await send_discord_high_match_alert(
                    job_title="Dev",
                    company="C",
                    match_score=90,
                    webhook_url=self.WEBHOOK_URL,
                )
                self.assertFalse(res, f"Expected graceful False on exception {type(exc).__name__}")

    # -------------------------------------------------------------------------
    # 4. Discord HTTP Status Code Responses (429, 400, 404, 500, 503)
    # -------------------------------------------------------------------------
    async def test_discord_http_error_codes(self):
        """Test Discord HTTP responses: 429 Rate Limit, 400 Bad Request, 404 Not Found, 500 Server Error."""
        error_statuses = [
            (429, '{"message": "You are being rate limited.", "retry_after": 2.5, "global": false}'),
            (400, '{"message": "Invalid Form Body", "code": 50035}'),
            (401, '{"message": "401: Unauthorized", "code": 0}'),
            (404, '{"message": "Unknown Webhook", "code": 10015}'),
            (500, 'Internal Server Error'),
            (502, 'Bad Gateway'),
            (503, 'Service Unavailable'),
            (504, 'Gateway Timeout'),
        ]

        for code, text in error_statuses:
            mock_resp = MagicMock()
            mock_resp.status_code = code
            mock_resp.text = text

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp
                res = await send_discord_high_match_alert(
                    job_title="Lead Architect",
                    company="Cloud Inc",
                    match_score=92,
                    webhook_url=self.WEBHOOK_URL,
                )
                self.assertFalse(res, f"Expected False on HTTP status {code}")

    # -------------------------------------------------------------------------
    # 5. Payload Boundaries & Special Character Stress
    # -------------------------------------------------------------------------
    def test_discord_embed_field_limits_and_special_characters(self):
        """Stress-test embed generator with enormous strings, emojis, unicode, and markdown characters."""
        enormous_title = "Python Engineer " + "🚀" * 300
        enormous_company = "Tech Corp " * 100
        enormous_location = "Prague " * 100
        enormous_salary = "100k " * 100
        enormous_pros = [
            "Pro 1: " + "A" * 500,
            "Pro 2: " + "B" * 500,
            "Pro 3: " + "C" * 500,
            "Pro 4 (should be cut off): " + "D" * 500,
        ]
        tricky_url = "https://example.com/job?title=a(b)c&ref=[test]!*'();:@&=+$,/?%#[]"

        embed = build_discord_embed(
            job_title=enormous_title,
            company=enormous_company,
            location=enormous_location,
            salary=enormous_salary,
            match_score=95,
            pros=enormous_pros,
            source_url=tricky_url,
        )

        self.assertIn("🎯", embed["title"])
        self.assertEqual(embed["color"], 0x22c55e)
        self.assertEqual(len(embed["fields"]), 6)

        # Check PROs count is capped at 3
        pros_field = next(f for f in embed["fields"] if "PROs" in f["name"])
        self.assertEqual(pros_field["value"].count("•"), 3)
        self.assertNotIn("Pro 4", pros_field["value"])

    async def test_discord_concurrent_alert_flood(self):
        """Simulate 20 concurrent high-match alerts triggering simultaneously."""
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.text = ""

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            tasks = [
                send_discord_high_match_alert(
                    job_title=f"Position {i}",
                    company=f"Company {i}",
                    match_score=85 + (i % 15),
                    webhook_url=self.WEBHOOK_URL,
                )
                for i in range(20)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            self.assertEqual(len(results), 20)
            self.assertTrue(all(r is True for r in results))
            self.assertEqual(mock_post.call_count, 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
