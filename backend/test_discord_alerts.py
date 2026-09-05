import sys
import os
import json
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from services.discord_service import (
    send_discord_high_match_alert,
    build_discord_embed,
    format_discord_alert_payload,
    format_pros_bullets,
    DISCORD_EMBED_COLOR_GREEN,
    DEFAULT_MIN_MATCH_SCORE,
)
from schemas import JobMatchingResult
from models import Application, JobPosting, User


class TestDiscordEmbedFormatting(unittest.TestCase):
    """Testy formátování Embed karty pro Discord Webhook."""

    def test_embed_structure_matches_all_required_fields(self):
        """Ověření, že embed obsahuje všechna povinná pole: title, company, location, salary, 3 PROs, link."""
        title = "Senior Python Developer"
        company = "Acme Cloud AI"
        location = "Praha / Remote (EU)"
        salary = "120 000 - 150 000 CZK"
        match_score = 92
        pros = [
            "Expertíza v Pythonu a moderním FastAPI stacku",
            "Praxe s architekturou distribuovaných systémů",
            "100% remote kompatibilita v rámci CET pásma",
            "Tato 4. odrážka by měla být oříznuta",
        ]
        source_url = "https://jobs.cz/r/senior-python-dev-12345"

        embed = build_discord_embed(
            job_title=title,
            company=company,
            location=location,
            salary=salary,
            match_score=match_score,
            pros=pros,
            source_url=source_url,
        )

        # 1. Barva: zelená 0x22c55e (2278750)
        self.assertEqual(embed["color"], DISCORD_EMBED_COLOR_GREEN)
        self.assertEqual(embed["color"], 0x22c55e)

        # 2. Název a přímý link
        self.assertIn(title, embed["title"])
        self.assertEqual(embed["url"], source_url)

        # 3. Kontrola polí (fields)
        fields = {f["name"]: f["value"] for f in embed["fields"]}

        # Společnost
        company_field = next((v for k, v in fields.items() if "společnost" in k.lower() or "company" in k.lower()), None)
        self.assertIsNotNone(company_field)
        self.assertEqual(company_field, company)

        # Lokalita / Remote
        loc_field = next((v for k, v in fields.items() if "lokalita" in k.lower() or "remote" in k.lower() or "location" in k.lower()), None)
        self.assertIsNotNone(loc_field)
        self.assertEqual(loc_field, location)

        # Platové rozpětí
        sal_field = next((v for k, v in fields.items() if "plat" in k.lower() or "salary" in k.lower()), None)
        self.assertIsNotNone(sal_field)
        self.assertEqual(sal_field, salary)

        # Match Score
        score_field = next((v for k, v in fields.items() if "score" in k.lower() or "match" in k.lower()), None)
        self.assertIsNotNone(score_field)
        self.assertIn(f"{match_score} %", score_field)

        # 3 PROs (formátované odrážky, max 3)
        pros_field = next((v for k, v in fields.items() if "pros" in k.lower() or "výhody" in k.lower()), None)
        self.assertIsNotNone(pros_field)
        self.assertIn("• Expertíza v Pythonu", pros_field)
        self.assertIn("• Praxe s architekturou", pros_field)
        self.assertIn("• 100% remote", pros_field)
        self.assertNotIn("Tato 4. odrážka", pros_field, "PROs nesmí obsahovat více než 3 odrážky")

        # Přímý odkaz
        link_field = next((v for k, v in fields.items() if "odkaz" in k.lower() or "link" in k.lower()), None)
        self.assertIsNotNone(link_field)
        self.assertIn(source_url, link_field)

    def test_embed_formatting_with_missing_optional_fields(self):
        """Ověření, že chybějící lokalita nebo plat nezpůsobí pád a mají elegantní výchozí hodnoty."""
        embed = build_discord_embed(
            job_title="DevOps Engineer",
            company="Tech Corp",
            location=None,
            salary=None,
            match_score=88,
            pros=[],
            source_url="https://example.com/job",
        )

        fields = {f["name"]: f["value"] for f in embed["fields"]}
        loc_field = next(v for k, v in fields.items() if "lokalita" in k.lower())
        sal_field = next(v for k, v in fields.items() if "plat" in k.lower())

        self.assertIn("neuvedena", loc_field.lower())
        self.assertIn("neuvedeno", sal_field.lower())

    def test_format_pros_bullets_limit_and_fallback(self):
        """Ověření limitu 3 odrážek a fallbacku při prázdném seznamu."""
        # Prázdné PROs
        empty_bullets = format_pros_bullets([])
        self.assertTrue(empty_bullets.startswith("•"))

        None_bullets = format_pros_bullets(None)
        self.assertTrue(None_bullets.startswith("•"))

        # Více než 3 PROs
        many_pros = ["Bod 1", "Bod 2", "Bod 3", "Bod 4", "Bod 5"]
        res = format_pros_bullets(many_pros)
        bullet_count = res.count("•")
        self.assertEqual(bullet_count, 3)
        self.assertIn("Bod 1", res)
        self.assertIn("Bod 2", res)
        self.assertIn("Bod 3", res)
        self.assertNotIn("Bod 4", res)


class TestDiscordAlertAsyncFunction(unittest.IsolatedAsyncioTestCase):
    """Asynchronní testy funkce send_discord_high_match_alert."""

    async def test_alert_sent_when_score_gte_85_with_valid_webhook(self):
        """Ověření, že alert je úspěšně odeslán při score >= 85 s platným webhookem."""
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.text = ""

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            # Hraniční test: score = 85
            result_85 = await send_discord_high_match_alert(
                job_title="Fullstack Developer",
                company="Startup Labs",
                location="Prague",
                salary="90 000 CZK",
                match_score=85,
                pros=["React", "TypeScript", "Node.js"],
                source_url="https://startupjobs.cz/nabidka/1",
                webhook_url="https://discord.com/api/webhooks/12345/testtoken",
            )
            self.assertTrue(result_85)
            self.assertEqual(mock_post.call_count, 1)

            # Test s vyšším skóre: score = 95
            result_95 = await send_discord_high_match_alert(
                job_title="Lead Architect",
                company="Global Cloud",
                location="Fully Remote",
                salary="$140 000",
                match_score=95,
                pros=["Architecture", "Python", "Scale"],
                source_url="https://remoteok.com/j/99",
                webhook_url="https://discord.com/api/webhooks/12345/testtoken",
            )
            self.assertTrue(result_95)
            self.assertEqual(mock_post.call_count, 2)

    async def test_not_sent_when_score_lt_85(self):
        """Ověření, že alert NENÍ odeslán, pokud je match_score < 85."""
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            # Hraniční test: score = 84
            res_84 = await send_discord_high_match_alert(
                job_title="Junior Tester",
                company="QA Studio",
                location="Brno",
                salary="45 000 CZK",
                match_score=84,
                pros=["Manual QA"],
                source_url="https://jobs.cz/test-84",
                webhook_url="https://discord.com/api/webhooks/12345/testtoken",
            )
            self.assertFalse(res_84)
            mock_post.assert_not_called()

            # Nízké skóre: score = 50
            res_50 = await send_discord_high_match_alert(
                job_title="Java Developer",
                company="Legacy Bank",
                location="Ostrava",
                salary="60 000 CZK",
                match_score=50,
                pros=[],
                source_url="https://jobs.cz/test-50",
                webhook_url="https://discord.com/api/webhooks/12345/testtoken",
            )
            self.assertFalse(res_50)
            mock_post.assert_not_called()

    async def test_graceful_skip_with_missing_or_empty_webhook(self):
        """Ověření bezpečného přeskočení bez výjimky při chybějící nebo prázdné webhook URL."""
        # 1. Webhook None a v env nic
        with patch.dict(os.environ, {}, clear=True):
            res_none = await send_discord_high_match_alert(
                job_title="Data Scientist",
                company="AI Alpha",
                location="Remote",
                salary="100k",
                match_score=90,
                pros=["Python", "PyTorch"],
                source_url="https://jobs.cz/ds",
                webhook_url=None,
            )
            self.assertFalse(res_none)

        # 2. Webhook prázdný string ""
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": ""}):
            res_empty = await send_discord_high_match_alert(
                job_title="Data Scientist",
                company="AI Alpha",
                location="Remote",
                salary="100k",
                match_score=90,
                pros=["Python", "PyTorch"],
                source_url="https://jobs.cz/ds",
                webhook_url="",
            )
            self.assertFalse(res_empty)

        # 3. Webhook jen mezery "   "
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "   "}):
            res_spaces = await send_discord_high_match_alert(
                job_title="Data Scientist",
                company="AI Alpha",
                location="Remote",
                salary="100k",
                match_score=90,
                pros=["Python", "PyTorch"],
                source_url="https://jobs.cz/ds",
                webhook_url="   ",
            )
            self.assertFalse(res_spaces)

        # 4. Neplatný formát bez http/https protokolu
        res_invalid = await send_discord_high_match_alert(
            job_title="Data Scientist",
            company="AI Alpha",
            location="Remote",
            salary="100k",
            match_score=90,
            pros=["Python", "PyTorch"],
            source_url="https://jobs.cz/ds",
            webhook_url="not-a-valid-url",
        )
        self.assertFalse(res_invalid)

    async def test_network_failure_resilience(self):
        """Ověření, že výpadek sítě, timeout ani HTTP chyba neshodí aplikaci a vrátí False."""
        import httpx

        # Timeout výjimka
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Connection timed out")):
            res_timeout = await send_discord_high_match_alert(
                job_title="Cloud Engineer",
                company="AWS Partner",
                location="Remote",
                salary=None,
                match_score=90,
                pros=["Terraform"],
                source_url="https://example.com",
                webhook_url="https://discord.com/api/webhooks/123/abc",
            )
            self.assertFalse(res_timeout)

        # Síťová chyba (ConnectError)
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Failed to resolve host")):
            res_conn = await send_discord_high_match_alert(
                job_title="Cloud Engineer",
                company="AWS Partner",
                location="Remote",
                salary=None,
                match_score=90,
                pros=["Terraform"],
                source_url="https://example.com",
                webhook_url="https://discord.com/api/webhooks/123/abc",
            )
            self.assertFalse(res_conn)

        # HTTP status 500
        mock_500 = MagicMock()
        mock_500.status_code = 500
        mock_500.text = "Internal Server Error"
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_500
            res_500 = await send_discord_high_match_alert(
                job_title="Cloud Engineer",
                company="AWS Partner",
                location="Remote",
                salary=None,
                match_score=90,
                pros=["Terraform"],
                source_url="https://example.com",
                webhook_url="https://discord.com/api/webhooks/123/abc",
            )
            self.assertFalse(res_500)


class TestCzechJobSchemaPros(unittest.TestCase):
    """Testy rozšíření schématu JobMatchingResult o PROs pro české pozice."""

    def test_job_matching_result_schema_supports_pros_and_cons(self):
        """Ověření, že JobMatchingResult přijímá pros i cons a má bezpečné výchozí prázdné seznamy."""
        # Se zadanými PROs a CONs
        res_full = JobMatchingResult(
            match_score=88,
            match_reason="Výborný profil pro Python",
            pros=["Znalost FastAPI", "Zkušenost s PostgreSQL", "Vysokoškolské vzdělání"],
            cons=["Chybí zkušenost s Kubernetes"],
        )
        self.assertEqual(res_full.match_score, 88)
        self.assertEqual(len(res_full.pros), 3)
        self.assertEqual(len(res_full.cons), 1)

        # Bez zadaných PROs/CONs (zpětná kompatibilita)
        res_default = JobMatchingResult(
            match_score=75,
            match_reason="Průměrná shoda",
        )
        self.assertEqual(res_default.match_score, 75)
        self.assertEqual(res_default.pros, [])
        self.assertEqual(res_default.cons, [])

    def test_job_matching_result_json_serialization(self):
        """Ověření validace z JSON řetězce (simulace výstupu z LLM)."""
        json_data = json.dumps({
            "match_score": 90,
            "match_reason": "Perfektní fit pro roli",
            "pros": ["Výborný Python", "Skvělá komunikace", "Znalost AI"],
            "cons": []
        })
        model = JobMatchingResult.model_validate_json(json_data)
        self.assertEqual(model.match_score, 90)
        self.assertEqual(len(model.pros), 3)


class TestOrchestratorDiscordHook(unittest.IsolatedAsyncioTestCase):
    """Testy napojení triggeru na orchestrator.py."""

    async def test_trigger_discord_alert_on_high_match(self):
        """Ověření, že _trigger_discord_alert_if_high_match předá správná data."""
        from orchestrator import _trigger_discord_alert_if_high_match

        job = JobPosting(
            id=10,
            source_url="https://jobs.cz/position-10",
            title="Senior Backend Python Engineer",
            company_name="InnovateTech",
            remote_policy="FULLY_REMOTE",
            salary_info="130 000 CZK",
        )
        app = Application(
            id=10,
            user_id=1,
            job_id=10,
            match_score=92,
            match_reason="Silný soulad se stackem",
            pros=json.dumps(["Python 3.12", "FastAPI", "SQLModel"]),
        )
        app.job_posting = job

        with patch("services.discord_service.send_discord_high_match_alert", new_callable=AsyncMock) as mock_alert:
            mock_alert.return_value = True
            result = await _trigger_discord_alert_if_high_match(app)
            self.assertTrue(result)
            mock_alert.assert_called_once()
            _, kwargs = mock_alert.call_args
            self.assertEqual(kwargs["job_title"], "Senior Backend Python Engineer")
            self.assertEqual(kwargs["company"], "InnovateTech")
            self.assertEqual(kwargs["match_score"], 92)
            self.assertEqual(len(kwargs["pros"]), 3)
            self.assertIn("Python 3.12", kwargs["pros"])

    async def test_orchestrator_skips_alert_on_low_match(self):
        """Ověření, že při match_score < 85 se alert nevolá."""
        from orchestrator import _run_matching

        # Nastavíme mock session a application
        job = JobPosting(
            id=11,
            source_url="https://jobs.cz/position-11",
            title="Junior Dev",
            company_name="Small Firm",
            source_portal="Jobs.cz",
        )
        app = Application(
            id=11,
            user_id=1,
            job_id=11,
            match_score=70,
            pros=json.dumps(["Základy"]),
        )
        app.job_posting = job

        mock_session = MagicMock()

        # Mockneme _get_llm_setup a JobMatcher
        with patch("orchestrator._get_llm_setup", return_value=("Context", "gpt-4o", "key", None, "formal")), \
             patch("orchestrator.JobMatcher") as mock_matcher_cls, \
             patch("orchestrator._trigger_discord_alert_if_high_match", new_callable=AsyncMock) as mock_trigger:
            
            mock_matcher = MagicMock()
            mock_matcher.evaluate_match = AsyncMock(return_value=JobMatchingResult(
                match_score=72,
                match_reason="Průměrná shoda",
                pros=["Základy"]
            ))
            mock_matcher_cls.return_value = mock_matcher

            await _run_matching(mock_session, app)

            # Match score 72 < 85 -> trigger alertu nesmí být zavolán
            mock_trigger.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
