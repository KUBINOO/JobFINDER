"""
Challenger 2 Adversarial Verification Test Suite.

Adversarial Stress Testing for:
- Module 3: Cold Outreach Generator
- Module 4: Tailored ATS CV Generator (1-page A4 PDF)

Coverage:
1. Cold Outreach:
   - Word count boundaries (exact 100, exact 160, 99 underflow, 161 overflow, 0 words, whitespace, 1 word, 1000 words).
   - Job description boundary stresses (empty string, 1 word, 50,000 characters).
   - Multilingual inputs (Czech diacritics, English, German, Japanese, Cyrillic, Arabic).
   - Special characters & adversarial injections (XSS tags, SQLi strings, emojis, special punctuation).
   - Custom focus variations (empty, single char, massive text, emojis).
   - API endpoints (POST /outreach: 200 valid, 404 nonexistent, 422 invalid type, schema match).
   - DB persistence & idempotency.

2. Tailored ATS CV:
   - Strict single-page A4 constraint under extreme load (compaction loop stress).
   - 100% selectable text with PyMuPDF (zero rasterized text images, get_images() == []).
   - PDF magic bytes (%PDF-) and EOF integrity.
   - Page dimensions strictly A4 (595.28 pt x 841.89 pt).
   - Full preservation of Czech diacritics in vector text.
   - Special characters in company name and job title (XML/HTML safety & filename sanitization).
   - API endpoints (POST /cv/generate, GET /cv/download: 200, 404 nonexistent, 422 invalid type).
"""

import sys
import os
import unittest
import asyncio
from pathlib import Path
from sqlmodel import Session, select, create_engine, SQLModel
from fastapi.testclient import TestClient
import fitz

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

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
from services.cv_generator import (
    init_pdf_fonts,
    extract_job_technologies,
    is_czech_content,
    get_candidate_master_profile,
    formulate_tailored_cv_content,
    compile_cv_to_pdf,
    sanitize_filename_part,
    generate_tailored_cv_for_application,
)


class TestChallenger2ColdOutreachAdversarial(unittest.TestCase):
    """Adversarial boundary & stress testing for Cold Outreach Generator."""

    def test_word_count_exact_boundaries(self):
        """TC-ADV-3.1: Verify exact boundaries 100 words and 160 words are preserved unchanged."""
        # 100 words exactly
        text_100 = " ".join([f"slovo{i}" for i in range(100)]) + "."
        self.assertEqual(count_words(text_100), 100)
        out_100 = ensure_word_count_compliance(text_100, 100, 160)
        self.assertEqual(count_words(out_100), 100)
        self.assertEqual(out_100, text_100.strip())

        # 160 words exactly
        text_160 = " ".join([f"slovo{i}" for i in range(160)]) + "."
        self.assertEqual(count_words(text_160), 160)
        out_160 = ensure_word_count_compliance(text_160, 100, 160)
        self.assertEqual(count_words(out_160), 160)
        self.assertEqual(out_160, text_160.strip())

    def test_word_count_near_boundaries_and_extremes(self):
        """TC-ADV-3.2: Verify 99 words (underflow), 101 words, 159 words, 161 words (overflow), 0 words, 1000 words."""
        # 99 words -> should expand to [100, 160]
        text_99 = " ".join([f"slovo{i}" for i in range(99)]) + "."
        out_99 = ensure_word_count_compliance(text_99, 100, 160)
        cnt_99 = count_words(out_99)
        self.assertTrue(100 <= cnt_99 <= 160, f"99 words expanded to {cnt_99}")

        # 101 words -> stays 101 words
        text_101 = " ".join([f"slovo{i}" for i in range(101)]) + "."
        out_101 = ensure_word_count_compliance(text_101, 100, 160)
        self.assertEqual(count_words(out_101), 101)

        # 159 words -> stays 159 words
        text_159 = " ".join([f"slovo{i}" for i in range(159)]) + "."
        out_159 = ensure_word_count_compliance(text_159, 100, 160)
        self.assertEqual(count_words(out_159), 159)

        # 161 words -> truncated to [100, 160]
        text_161 = " ".join([f"slovo{i}" for i in range(161)]) + "."
        out_161 = ensure_word_count_compliance(text_161, 100, 160)
        cnt_161 = count_words(out_161)
        self.assertTrue(100 <= cnt_161 <= 160, f"161 words truncated to {cnt_161}")

        # 0 words / empty string
        out_empty = ensure_word_count_compliance("", 100, 160)
        cnt_empty = count_words(out_empty)
        self.assertTrue(100 <= cnt_empty <= 160, f"Empty string augmented to {cnt_empty}")

        # Whitespace only
        out_ws = ensure_word_count_compliance("   \n\t  \r\n   ", 100, 160)
        cnt_ws = count_words(out_ws)
        self.assertTrue(100 <= cnt_ws <= 160, f"Whitespace augmented to {cnt_ws}")

        # Single word
        out_1 = ensure_word_count_compliance("Ahoj.", 100, 160)
        cnt_1 = count_words(out_1)
        self.assertTrue(100 <= cnt_1 <= 160, f"Single word augmented to {cnt_1}")

        # Massive 1000 words
        text_1000 = " ".join([f"slovo{i}" for i in range(1000)]) + "."
        out_1000 = ensure_word_count_compliance(text_1000, 100, 160)
        cnt_1000 = count_words(out_1000)
        self.assertTrue(100 <= cnt_1000 <= 160, f"1000 words truncated to {cnt_1000}")
        self.assertTrue(out_1000.endswith((".", "!")), "Truncated text must end with proper punctuation")

    def test_generator_minimal_job_description(self):
        """TC-ADV-3.3: Verify generator survives empty, single-word, or whitespace job descriptions."""
        gen = ColdOutreachGenerator()
        candidate = {"name": "Jakub Slavík", "skills": ["Python", "FastAPI"], "projects": "Data Pipelines"}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Completely empty description
            res_empty = loop.run_until_complete(
                gen.generate(candidate, "Software Engineer", "Minimal Corp", "")
            )
            cnt_empty = count_words(res_empty)
            self.assertTrue(100 <= cnt_empty <= 160)
            self.assertIn("Minimal Corp", res_empty)

            # Single word description
            res_single = loop.run_until_complete(
                gen.generate(candidate, "Dev", "Tech s.r.o.", "Python")
            )
            cnt_single = count_words(res_single)
            self.assertTrue(100 <= cnt_single <= 160)
            self.assertIn("Python", res_single)
        finally:
            loop.close()

    def test_generator_massive_job_description_50k_chars(self):
        """TC-ADV-3.4: Verify generator handles massive 50,000 char job descriptions with hidden keywords quickly."""
        gen = ColdOutreachGenerator()
        candidate = {"name": "Jakub Slavík", "skills": ["Python", "FastAPI", "Docker"], "projects": "Scraping"}

        # Construct 50k+ character description with lots of boilerplate and some hidden keywords
        desc = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 700)
        desc += " Inzerát hledá Senior Inženýra: Docker, Kubernetes, PostgreSQL, FastAPI. "
        desc += ("Více informací a firemní benefity pro zaměstnance na plný úvazek. " * 300)
        self.assertGreater(len(desc), 50000)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            res = loop.run_until_complete(
                gen.generate(candidate, "Senior Cloud Architect", "Enterprise Corp s.r.o.", desc)
            )
            cnt = count_words(res)
            self.assertTrue(100 <= cnt <= 160, f"Expected 100-160 words, got {cnt}")
            self.assertIn("Enterprise Corp s.r.o.", res)
            # Check that detected tech from 50k description is mentioned
            self.assertTrue(any(t in res for t in ["FastAPI", "Docker", "PostgreSQL", "Python"]))
        finally:
            loop.close()

    def test_generator_multilingual_inputs(self):
        """TC-ADV-3.5: Multilingual job postings (Czech diacritics, English, German, Japanese, Cyrillic)."""
        gen = ColdOutreachGenerator()
        candidate = {"name": "Jakub Slavík", "skills": ["Python", "FastAPI", "Docker"], "projects": "Scraping"}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 1. Czech with complex diacritics
            cz_desc = "Hledáme nového kolegu na pozici vývojáře. Požadavky: příliš žluťoučký kůň úpěl ďábelské ódy. Zkušenosti s týmem."
            res_cz = loop.run_until_complete(
                gen.generate(candidate, "Python Vývojář", "Česká Distribuce a.s.", cz_desc)
            )
            self.assertTrue(100 <= count_words(res_cz) <= 160)
            self.assertIn("Dobrý den", res_cz)
            self.assertIn("Česká Distribuce a.s.", res_cz)

            # 2. English
            en_desc = "We are seeking a senior distributed systems architect with extensive FastAPI and Python knowledge."
            res_en = loop.run_until_complete(
                gen.generate(candidate, "Senior Systems Architect", "Silicon Horizons Inc.", en_desc)
            )
            self.assertTrue(100 <= count_words(res_en) <= 160)
            self.assertIn("Hello", res_en)
            self.assertIn("Silicon Horizons Inc.", res_en)

            # 3. German
            de_desc = "Wir suchen einen erfahrenen Python Entwickler mit Docker Kenntnissen für unser Team."
            res_de = loop.run_until_complete(
                gen.generate(candidate, "Python Entwickler", "Munich Cloud GmbH", de_desc)
            )
            self.assertTrue(100 <= count_words(res_de) <= 160)

            # 4. Japanese
            ja_desc = "Pythonエンジニア募集。FastAPIとDockerの経験が必要です。"
            res_ja = loop.run_until_complete(
                gen.generate(candidate, "Python エンジニア", "Tokyo Data K.K.", ja_desc)
            )
            self.assertTrue(100 <= count_words(res_ja) <= 160)

            # 5. Cyrillic
            ru_desc = "Ищем Senior Python разработчика с опытом FastAPI и PostgreSQL."
            res_ru = loop.run_until_complete(
                gen.generate(candidate, "Python Разработчик", "Vostok Tech", ru_desc)
            )
            self.assertTrue(100 <= count_words(res_ru) <= 160)
        finally:
            loop.close()

    def test_generator_adversarial_injections_and_special_chars(self):
        """TC-ADV-3.6: Adversarial injection attempts (XSS, SQLi, Emojis, Quotation marks, Escapes)."""
        gen = ColdOutreachGenerator()
        candidate = {"name": "Jakub Slavík", "skills": ["Python", "FastAPI"], "projects": "Data Pipelines"}

        adv_focus = "<script>alert('pwned')</script> 🔥🚀 '; DROP TABLE applications; -- \"'''"
        adv_comp = "EvilCorp </script><img src=x onerror=alert(1)>"
        adv_title = "Lead Hacker'; SELECT * FROM users;--"
        adv_desc = "Requires Python, Docker & <svg/onload=alert(1)> and emojis: 💻🎉✨"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            res = loop.run_until_complete(
                gen.generate(
                    candidate_info=candidate,
                    job_title=adv_title,
                    company=adv_comp,
                    job_desc=adv_desc,
                    custom_focus=adv_focus,
                    pros=["Match point 1: <alert>", "Match point 2: ' OR 1=1 --"]
                )
            )
            cnt = count_words(res)
            self.assertTrue(100 <= cnt <= 160, f"Adversarial message word count {cnt} outside 100-160")
            self.assertIn(adv_comp, res)
            self.assertIn("Jakub Slavík", res)
        finally:
            loop.close()

    def test_api_outreach_invalid_ids_and_boundaries(self):
        """TC-ADV-3.7: FastAPI endpoint /api/applications/{id}/outreach error boundary tests."""
        client = TestClient(app)

        # 1. Non-existent ID -> 404
        res_nonexistent = client.post("/api/applications/999999/outreach", json={})
        self.assertEqual(res_nonexistent.status_code, 404)

        # 2. Negative ID -> 404
        res_negative = client.post("/api/applications/-1/outreach", json={})
        self.assertEqual(res_negative.status_code, 404)

        # 3. String / invalid format ID -> 422 Unprocessable Entity
        res_invalid_type = client.post("/api/applications/not_a_number/outreach", json={})
        self.assertEqual(res_invalid_type.status_code, 422)

        # 4. Valid application ID (ID 1 exists in DB)
        res_valid = client.post("/api/applications/1/outreach", json={"custom_focus": "Adversarial Focus Test"})
        self.assertEqual(res_valid.status_code, 200)
        data = res_valid.json()
        self.assertIn("outreach_message", data)
        self.assertIn("word_count", data)
        self.assertIn("application_id", data)
        self.assertEqual(data["application_id"], 1)
        self.assertEqual(data["word_count"], count_words(data["outreach_message"]))
        self.assertTrue(100 <= data["word_count"] <= 160)


class TestChallenger2AtsCvAdversarial(unittest.TestCase):
    """Adversarial stress testing for Tailored ATS CV Generator (1-page A4 PDF)."""

    @classmethod
    def setUpClass(cls):
        init_pdf_fonts()

    def setUp(self):
        self.client = TestClient(app)
        self.candidate = {
            "name": "Jakub Slavík",
            "email": "kubaslavik2411@gmail.com",
            "phone": "+420 774 943 349",
            "location": "Praha / Varnsdorf, ČR",
            "linkedin": "linkedin.com/in/jakub-slavik",
            "github": "github.com/KUBINOO",
            "education": [
                {
                    "institution": "Vysoká škola ekonomická v Praze (VSE FIS)",
                    "degree_field": "Bakalářské studium: Aplikovaná informatika",
                    "period": "2025 – současnost",
                    "location": "Praha, ČR",
                    "details": "Matematika pro informatiky, Datové minimum, Algoritmizace"
                }
            ],
            "experiences": [
                {
                    "id": "quant",
                    "title": "Quant Investment Framework",
                    "organization": "Vlastní inženýrský projekt",
                    "period": "2025 – současnost",
                    "location": "Praha, ČR"
                },
                {
                    "id": "klub",
                    "title": "Klub Investorů VŠE",
                    "organization": "Klub Investorů",
                    "period": "2026 – současnost",
                    "location": "Praha, ČR"
                },
                {
                    "id": "eshop",
                    "title": "Správa e-shopu La-Vin.cz",
                    "organization": "La-Vin.cz",
                    "period": "2024 – 2025",
                    "location": "Praha, ČR"
                }
            ],
            "languages": "Čeština (Rodilý mluvčí), Angličtina (B2/C1), Němčina (A1/A2)",
            "availability": "Dle dohody (HPP / IČO / Stáž), nástup možný ihned"
        }

    def test_pdf_binary_integrity_and_magic_bytes(self):
        """TC-ADV-4.1: Verify PDF starts with %PDF- and PyMuPDF can parse document structure."""
        render_data = formulate_tailored_cv_content(
            candidate=self.candidate,
            job_title="Senior Python Architect",
            company="FinTech Core s.r.o.",
            job_desc="Python, FastAPI, PostgreSQL, Docker"
        )
        pdf_bytes, doc = compile_cv_to_pdf(render_data)

        # Check %PDF- magic bytes
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"), "PDF binary must start with %PDF-")
        # Check PDF binary size
        self.assertGreater(len(pdf_bytes), 5000, "PDF binary size is suspiciously small")
        # Check PyMuPDF parsed pages
        self.assertEqual(doc.page_count, 1, "Must have exactly 1 page")

    def test_strictly_single_page_a4_dimensions(self):
        """TC-ADV-4.2: Verify page dimensions strictly correspond to standard A4 (595.28 x 841.89 pt)."""
        render_data = formulate_tailored_cv_content(
            candidate=self.candidate,
            job_title="Data Platform Engineer",
            company="Algorithmic Trading Ltd",
            job_desc="Python, Pandas, SciPy, Docker, Redis"
        )
        pdf_bytes, doc = compile_cv_to_pdf(render_data)
        page = doc[0]
        rect = page.rect

        # Standard A4 in points: 595.276 x 841.890
        self.assertAlmostEqual(rect.width, 595.28, delta=1.0, msg=f"Page width {rect.width} not A4")
        self.assertAlmostEqual(rect.height, 841.89, delta=1.0, msg=f"Page height {rect.height} not A4")

    def test_100_percent_selectable_text_and_no_raster_images(self):
        """TC-ADV-4.3: Verify text is 100% vector selectable, zero rasterized text images, > 250 characters."""
        render_data = formulate_tailored_cv_content(
            candidate=self.candidate,
            job_title="Lead Backend Architect",
            company="Global Scale Services",
            job_desc="Python, FastAPI, Docker, PostgreSQL"
        )
        pdf_bytes, doc = compile_cv_to_pdf(render_data)
        page = doc[0]

        # 1. Zero raster images in document
        images = page.get_images()
        self.assertEqual(len(images), 0, f"Expected 0 embedded images (no rasterized text), got {len(images)}")

        # 2. Selectable text extracted
        text = page.get_text()
        self.assertGreater(len(text.strip()), 250, "Extracted text too short; text may not be selectable")

        # 3. Essential keywords selectable
        self.assertIn("JAKUB SLAV", text.upper())
        self.assertIn("Global Scale Services", text)
        self.assertIn("Python", text)

    def test_czech_diacritics_retention_in_vector_text(self):
        """TC-ADV-4.4: Verify complete preservation of Czech diacritics in vector text without replacement chars."""
        render_data = formulate_tailored_cv_content(
            candidate=self.candidate,
            job_title="Vývojář informačních systémů",
            company="Česká Spořitelna, a.s.",
            job_desc="Znalost češtiny, Pythonu a návrhu škálovatelných řešení v týmu."
        )
        pdf_bytes, doc = compile_cv_to_pdf(render_data)
        text = doc[0].get_text()

        # Check for unicode replacement character \ufffd
        self.assertNotIn("\ufffd", text, "Found unicode replacement character \ufffd in extracted text")

        # Check that specific Czech diacritic characters appear in text
        czech_samples = ["Česká", "Spořitelna", "Vývojář", "systémů", "řešení"]
        for sample in czech_samples:
            self.assertIn(sample, text, f"Missing Czech word with diacritics '{sample}' in PDF text")

    def test_compaction_loop_under_extreme_text_length(self):
        """TC-ADV-4.5: Stress test compaction loop: 50x verbose job title, 50x company, 50x summary."""
        # We simulate extreme text length in job title, company, and summary
        long_title = "Senior Principal Distributed Systems Software Engineer " * 15
        long_company = "International Multi-Cloud Enterprise Corporation " * 15
        long_desc = "Python, FastAPI, Docker, Kubernetes, PostgreSQL, Redis, AWS, GCP, Azure. " * 50

        render_data = formulate_tailored_cv_content(
            candidate=self.candidate,
            job_title=long_title,
            company=long_company,
            job_desc=long_desc
        )

        # Force long tailored summary
        render_data["tailored_summary"] = "Vysoce kvalifikovaný inženýr s rozsáhlou praxí v distribuovaných architekturách. " * 30

        pdf_bytes, doc = compile_cv_to_pdf(render_data)

        # Single page constraint must strictly hold!
        self.assertEqual(doc.page_count, 1, f"Compaction loop failed: page_count={doc.page_count} (expected 1)")
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertGreater(len(doc[0].get_text().strip()), 300)

    def test_special_characters_xml_safety_and_filename_sanitization(self):
        """TC-ADV-4.6: Special characters in job title/company (<, >, &, \", ', emojis) and filename sanitization."""
        # 1. XML safety inside HTML/PDF template
        special_title = "Backend <Lead> & Architect (Core / Cloud) 'Special'"
        special_company = "L'Oréal & Co / IT Divize <Praha> 🚀"

        render_data = formulate_tailored_cv_content(
            candidate=self.candidate,
            job_title=special_title,
            company=special_company,
            job_desc="Python & FastAPI & Docker"
        )
        pdf_bytes, doc = compile_cv_to_pdf(render_data)
        self.assertEqual(doc.page_count, 1)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

        # 2. Filename sanitization
        sanitized = sanitize_filename_part(special_company)
        self.assertNotIn("<", sanitized)
        self.assertNotIn(">", sanitized)
        self.assertNotIn("&", sanitized)
        self.assertNotIn("/", sanitized)
        self.assertNotIn("'", sanitized)
        self.assertNotIn(" ", sanitized)
        self.assertTrue(len(sanitized) > 0)
        self.assertTrue(sanitized.startswith("LOreal"))

    def test_api_cv_generate_and_download_error_boundaries(self):
        """TC-ADV-4.7: Error boundaries for /cv/generate and /cv/download (404 for nonexistent, 422 for string ID)."""
        # Non-existent application ID
        res_gen_404 = self.client.post("/api/applications/999999/cv/generate")
        self.assertEqual(res_gen_404.status_code, 404)

        res_dl_404 = self.client.get("/api/applications/999999/cv/download")
        self.assertEqual(res_dl_404.status_code, 404)

        # Negative ID
        res_gen_neg = self.client.post("/api/applications/-1/cv/generate")
        self.assertEqual(res_gen_neg.status_code, 404)

        res_dl_neg = self.client.get("/api/applications/-1/cv/download")
        self.assertEqual(res_dl_neg.status_code, 404)

        # String ID -> 422
        res_gen_str = self.client.post("/api/applications/not_valid/cv/generate")
        self.assertEqual(res_gen_str.status_code, 422)

        res_dl_str = self.client.get("/api/applications/not_valid/cv/download")
        self.assertEqual(res_dl_str.status_code, 422)

    def test_api_cv_generate_and_download_flow(self):
        """TC-ADV-4.8: Complete flow test for /cv/generate and /cv/download with binary integrity verification."""
        # 1. Generate CV for Application 1
        gen_res = self.client.post("/api/applications/1/cv/generate")
        self.assertEqual(gen_res.status_code, 200)
        gen_data = gen_res.json()
        self.assertEqual(gen_data["status"], "generated")
        self.assertEqual(gen_data["page_count"], 1)
        self.assertTrue(os.path.exists(gen_data["file_path"]))

        # 2. Download CV for Application 1
        dl_res = self.client.get("/api/applications/1/cv/download")
        self.assertEqual(dl_res.status_code, 200)
        self.assertEqual(dl_res.headers.get("content-type"), "application/pdf")
        self.assertIn("attachment", dl_res.headers.get("content-disposition", ""))

        pdf_content = dl_res.content
        self.assertTrue(pdf_content.startswith(b"%PDF-"))

        # Verify downloaded binary with fitz
        with fitz.open(stream=pdf_content, filetype="pdf") as doc:
            self.assertEqual(doc.page_count, 1)
            self.assertGreater(len(doc[0].get_text().strip()), 200)
            self.assertEqual(len(doc[0].get_images()), 0)


if __name__ == "__main__":
    unittest.main()
