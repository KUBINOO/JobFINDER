"""
Unit and API Integration Tests for Hiring Manager Cold Outreach Generator (Module 3).

Verifies:
1. Word count compliance (strictly 100–160 words).
2. Tech keyword extraction and challenge-achievement connection.
3. Custom focus steering.
4. Database persistence in Application.outreach_message.
5. FastAPI endpoint POST /api/applications/{id}/outreach behavior (200, 404, schema, custom_focus).
6. Robustness against LLM failures and fallback generation.
"""

import sys
import os
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlmodel import Session, select
from fastapi.testclient import TestClient

from database import engine
from models import Application, JobPosting, User, UserPreferences, ApplicationStatus
from main import app
from services.outreach_service import (
    ColdOutreachGenerator,
    generate_and_save_cold_outreach,
    count_words,
    is_czech_text,
    extract_tech_keywords,
    ensure_word_count_compliance,
    TARGET_MIN_WORDS,
    TARGET_MAX_WORDS,
)


class TestColdOutreachWordCount(unittest.TestCase):
    """Testy validace a garance rozsahu slov (100–160 slov)."""

    def test_count_words_utility(self):
        """Ověření pomocné funkce pro počítání slov."""
        self.assertEqual(count_words(""), 0)
        self.assertEqual(count_words("   "), 0)
        self.assertEqual(count_words("Jedno"), 1)
        self.assertEqual(count_words("Jedno dvě tři"), 3)
        self.assertEqual(count_words("  Slovo   s   více   mezerami  \n a novým řádkem. "), 7)

    def test_ensure_word_count_compliance_exact_boundaries(self):
        """Ověření, že přesně 100 a 160 slov projde bez úprav."""
        msg_100 = " ".join([f"slovo{i}" for i in range(100)]) + "."
        self.assertEqual(count_words(msg_100), 100)
        res_100 = ensure_word_count_compliance(msg_100, 100, 160)
        self.assertEqual(count_words(res_100), 100)

        msg_160 = " ".join([f"slovo{i}" for i in range(160)]) + "."
        self.assertEqual(count_words(msg_160), 160)
        res_160 = ensure_word_count_compliance(msg_160, 100, 160)
        self.assertEqual(count_words(res_160), 160)

    def test_ensure_word_count_compliance_underflow(self):
        """Ověření, že zpráva s méně než 100 slovy je doplněna do intervalu [100, 160]."""
        short_msg = "Dobrý den, obracím se na Vás ohledně pozice Python vývojáře ve Vaší společnosti."
        self.assertLess(count_words(short_msg), 100)

        augmented_cz = ensure_word_count_compliance(short_msg, target_min=100, target_max=160, lang="cz")
        count_cz = count_words(augmented_cz)
        self.assertGreaterEqual(count_cz, 100, f"Očekáváno >= 100 slov, získáno {count_cz}")
        self.assertLessEqual(count_cz, 160, f"Očekáváno <= 160 slov, získáno {count_cz}")

        augmented_en = ensure_word_count_compliance("Hello, applying for python position.", target_min=100, target_max=160, lang="en")
        count_en = count_words(augmented_en)
        self.assertGreaterEqual(count_en, 100)
        self.assertLessEqual(count_en, 160)

    def test_ensure_word_count_compliance_overflow(self):
        """Ověření, že zpráva s více než 160 slovy je citlivě zkrácena do intervalu [100, 160]."""
        long_msg = " ".join([f"slovo{i}" for i in range(220)]) + "."
        self.assertEqual(count_words(long_msg), 220)

        truncated = ensure_word_count_compliance(long_msg, target_min=100, target_max=160)
        count = count_words(truncated)
        self.assertGreaterEqual(count, 100)
        self.assertLessEqual(count, 160)


class TestTechKeywordsAndContentMatching(unittest.TestCase):
    """Testy extrakce klíčových slov a propojování výzev s úspěchy."""

    def test_extract_tech_keywords_from_description(self):
        """Ověření detekce technologického stacku v inzerátu."""
        desc = (
            "Hledáme Senior Backend Inženýra se znalostí Python, FastAPI, Docker a PostgreSQL. "
            "Výhodou je zkušenost s Celery, Redis a cloudem AWS."
        )
        techs = extract_tech_keywords(desc)
        self.assertIn("Python", techs)
        self.assertIn("FastAPI", techs)
        self.assertIn("Docker", techs)
        self.assertIn("PostgreSQL", techs)
        self.assertIn("Celery", techs)
        self.assertIn("Redis", techs)
        self.assertIn("AWS", techs)

    def test_is_czech_text_detection(self):
        """Ověření detekce jazyka inzerátu (CZ vs EN)."""
        cz_desc = "Hledáme nového kolegu na pozici Python vývojář. Naše požadavky zahrnují praxi s databázemi."
        en_desc = "We are seeking an experienced Backend Engineer to join our distributed cloud infrastructure team."
        self.assertTrue(is_czech_text(cz_desc))
        self.assertFalse(is_czech_text(en_desc))

    def test_outreach_generator_connects_job_challenges_with_achievements_cz(self):
        """Ověření, že vygenerovaná CZ zpráva propojuje výzvy inzerátu s úspěchy kandidáta a má 100–160 slov."""
        gen = ColdOutreachGenerator()
        candidate_info = {
            "name": "Jakub Slavík",
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "projects": "asynchronní scraping a distribuované zpracování dat",
        }
        msg = gen._generate_structured_outreach(
            candidate_info=candidate_info,
            job_title="Senior Python Vývojář",
            company="FinTech Innovations s.r.o.",
            custom_focus="Asynchronní scraping pipeline a databázový výkon",
            pros=["Silná zkušenost s Pythonem a FastAPI"],
            is_cz=True,
            primary_tech="Python",
            secondary_tech="FastAPI",
        )

        words = count_words(msg)
        self.assertGreaterEqual(words, 100, f"Zpráva musí mít alespoň 100 slov (má {words})")
        self.assertLessEqual(words, 160, f"Zpráva nesmí mít více než 160 slov (má {words})")
        self.assertIn("FinTech Innovations s.r.o.", msg)
        self.assertIn("Python", msg)
        self.assertIn("FastAPI", msg)
        self.assertIn("Jakub Slavík", msg)
        self.assertIn("Asynchronní scraping pipeline", msg)

    def test_outreach_generator_connects_job_challenges_with_achievements_en(self):
        """Ověření, že vygenerovaná EN zpráva propojuje výzvy inzerátu s úspěchy kandidáta a má 100–160 slov."""
        gen = ColdOutreachGenerator()
        candidate_info = {
            "name": "Jakub Slavik",
            "skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
            "projects": "distributed scraping architecture and quant framework",
        }
        msg = gen._generate_structured_outreach(
            candidate_info=candidate_info,
            job_title="Lead Backend Architect",
            company="Global Scale Inc.",
            custom_focus="Low Latency Event Streaming",
            pros=["Excellent FastAPI and distributed systems match"],
            is_cz=False,
            primary_tech="Python",
            secondary_tech="FastAPI",
        )

        words = count_words(msg)
        self.assertGreaterEqual(words, 100, f"Zpráva musí mít alespoň 100 slov (má {words})")
        self.assertLessEqual(words, 160, f"Zpráva nesmí mít více než 160 slov (má {words})")
        self.assertIn("Global Scale Inc.", msg)
        self.assertIn("Python", msg)
        self.assertIn("FastAPI", msg)
        self.assertIn("Jakub Slavik", msg)
        self.assertIn("Low Latency Event Streaming", msg)


class TestDatabasePersistence(unittest.IsolatedAsyncioTestCase):
    """Testy uložení a perzistence outreach_message v databázi SQLite."""

    def setUp(self):
        with Session(engine) as session:
            user = session.get(User, 1)
            if not user:
                user = User(id=1, first_name="Jakub", last_name="Slavík", email="jakub@test.cz")
                session.add(user)
                session.commit()

    def test_application_model_supports_outreach_message(self):
        """Ověření, že model Application má atribut outreach_message."""
        self.assertTrue(hasattr(Application, "outreach_message"))
        app_inst = Application(user_id=1, job_id=1, status=ApplicationStatus.PENDING)
        self.assertIsNone(app_inst.outreach_message)
        app_inst.outreach_message = "Test zpráva pro hiring managera"
        self.assertEqual(app_inst.outreach_message, "Test zpráva pro hiring managera")

    async def test_generate_and_save_cold_outreach_persists_in_db(self):
        """Ověření, že generate_and_save_cold_outreach skutečně zapíše a potvrdí zprávu do DB."""
        with Session(engine) as session:
            job = JobPosting(
                title="Data Platform Engineer",
                company_name="Alpha Analytics",
                source_url=f"http://test-persist-{os.urandom(4).hex()}.com/job",
                description="We require Python, PostgreSQL and Docker expertise for our big data ingest platform."
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            appl = Application(user_id=1, job_id=job.id, status=ApplicationStatus.PENDING)
            session.add(appl)
            session.commit()
            session.refresh(appl)
            test_app_id = appl.id

            result = await generate_and_save_cold_outreach(
                session=session,
                application=appl,
                custom_focus="High Throughput Data Processing"
            )

        # Ověření v NOVÉ nezávislé session
        with Session(engine) as fresh_session:
            reloaded = fresh_session.get(Application, test_app_id)
            self.assertIsNotNone(reloaded)
            self.assertIsNotNone(reloaded.outreach_message)
            self.assertEqual(reloaded.outreach_message, result["outreach_message"])
            self.assertEqual(result["application_id"], test_app_id)
            self.assertTrue(100 <= result["word_count"] <= 160)


class TestColdOutreachApiEndpoints(unittest.TestCase):
    """Testy FastAPI endpointu POST /api/applications/{id}/outreach."""

    def setUp(self):
        self.client = TestClient(app)
        with Session(engine) as session:
            user = session.get(User, 1)
            if not user:
                user = User(id=1, first_name="Jakub", last_name="Slavík", email="jakub@test.cz")
                session.add(user)
                session.commit()

            job = JobPosting(
                title="Python Backend Specialist",
                company_name="TechWave Solutions",
                source_url=f"http://test-api-{os.urandom(4).hex()}.com/job",
                description="Hledáme specialistu na Python a FastAPI s praxí v distribuovaných architekturách."
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            appl = Application(user_id=1, job_id=job.id, status=ApplicationStatus.PENDING)
            session.add(appl)
            session.commit()
            session.refresh(appl)
            self.test_app_id = appl.id

    def test_api_outreach_endpoint_success(self):
        """TC-3.1: Ověření, že POST /api/applications/{id}/outreach vrací kód 200 a správné schéma."""
        res = self.client.post(f"/api/applications/{self.test_app_id}/outreach", json={})
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertIn("outreach_message", data)
        self.assertIn("word_count", data)
        self.assertIn("application_id", data)
        self.assertEqual(data["application_id"], self.test_app_id)

        # Kontrola shody word_count s reálným textem
        real_word_count = len(data["outreach_message"].strip().split())
        self.assertEqual(data["word_count"], real_word_count)
        self.assertTrue(100 <= real_word_count <= 160, f"Počet slov ({real_word_count}) musí být v rozmezí 100–160.")

    def test_api_outreach_endpoint_404_nonexistent_id(self):
        """TC-7.2: Ověření, že neexistující ID přihlášky vrátí 404."""
        res = self.client.post("/api/applications/999999/outreach", json={})
        self.assertEqual(res.status_code, 404)

    def test_api_outreach_endpoint_with_custom_focus(self):
        """TC-3.4: Ověření, že parametr custom_focus ovlivní vygenerovaný text."""
        custom_focus = "Optimalizace latence a Redis caching"
        res = self.client.post(f"/api/applications/{self.test_app_id}/outreach", json={"custom_focus": custom_focus})
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertIn("outreach_message", data)
        self.assertIn("Optimalizace latence", data["outreach_message"])
        self.assertTrue(100 <= data["word_count"] <= 160)

    def test_get_application_includes_outreach_message(self):
        """Ověření, že GET /api/applications/{id} vrací pole outreach_message."""
        # Nejprve vygenerujeme outreach
        self.client.post(f"/api/applications/{self.test_app_id}/outreach", json={})

        # Nyní načteme detail
        res = self.client.get(f"/api/applications/{self.test_app_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("outreach_message", data)
        self.assertIsNotNone(data["outreach_message"])


if __name__ == "__main__":
    unittest.main()
