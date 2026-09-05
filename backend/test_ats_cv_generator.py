import os
import io
import re
import unittest
from unittest.mock import patch, MagicMock
from sqlmodel import Session, select, create_engine, SQLModel
from fastapi.testclient import TestClient
import fitz

from models import Application, JobPosting, User, UserPreferences, ApplicationStatus
from services.cv_generator import (
    init_pdf_fonts,
    extract_job_technologies,
    is_czech_content,
    get_candidate_master_profile,
    formulate_tailored_cv_content,
    compile_cv_to_pdf,
    sanitize_filename_part,
    generate_tailored_cv_for_application
)
from main import app


class TestAtsCvTemplateAndFonts(unittest.TestCase):
    """Testy ověřující existenci HTML šablony a správnou inicializaci písem."""

    def test_template_file_exists(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(base_dir, "templates", "cv_template.html")
        self.assertTrue(os.path.exists(template_path), f"Šablona nenalezena na cestě: {template_path}")

    def test_init_pdf_fonts_runs_without_error(self):
        try:
            init_pdf_fonts()
        except Exception as e:
            self.fail(f"init_pdf_fonts vyhodila neočekávanou výjimku: {e}")

    def test_sanitize_filename_part(self):
        raw_company = "Česká spořitelna, a.s. / Divize IT"
        sanitized = sanitize_filename_part(raw_company)
        self.assertNotIn(" ", sanitized)
        self.assertNotIn("/", sanitized)
        self.assertNotIn(",", sanitized)
        self.assertNotIn("Č", sanitized)
        self.assertTrue(len(sanitized) > 0)
        self.assertTrue(sanitized.startswith("Ceska"))


class TestCvContentExtractionAndStarFormulation(unittest.TestCase):
    """Testy extrakce technologií, master profilu a sestavení STAR odrážek."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        self.user = User(
            id=1,
            first_name="Jakub",
            last_name="Slavík",
            email="kubaslavik2411@gmail.com"
        )
        self.user_prefs = UserPreferences(
            id=1,
            full_name="Jakub Slavík",
            phone_number="+420 774 943 349",
            education="Vysoká škola ekonomická v Praze (FIS)",
            industry="IT / Software Engineering",
            linkedin_url="linkedin.com/in/jakub-slavik"
        )
        self.session.add(self.user)
        self.session.add(self.user_prefs)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_extract_job_technologies_detects_backend_and_data(self):
        desc = (
            "Hledáme Senior Python Engineera se znalostí FastAPI, PostgreSQL a Dockeru. "
            "Výhodou je zkušenost s Pandas, Redis a asynchronním zpracováním (asyncio)."
        )
        techs = extract_job_technologies(desc)
        all_techs = techs["all"]
        self.assertIn("Python", all_techs)
        self.assertIn("FastAPI", all_techs)
        self.assertIn("PostgreSQL", all_techs)
        self.assertIn("Docker", all_techs)
        self.assertIn("Pandas", all_techs)
        self.assertIn("Redis", all_techs)

    def test_is_czech_content_detection(self):
        cz_desc = "Hledáme nového kolegu na pozici vývojáře. Nabízíme práci v moderním týmu v Praze."
        en_desc = "We are seeking a senior backend software engineer to join our high-growth platform team."
        self.assertTrue(is_czech_content(cz_desc))
        self.assertFalse(is_czech_content(en_desc))

    def test_get_candidate_master_profile_returns_genuine_data(self):
        profile = get_candidate_master_profile(self.session, self.user)
        self.assertEqual(profile["name"], "Jakub Slavík")
        self.assertIn("@", profile["email"])
        self.assertIn("774", profile["phone"])
        self.assertTrue(len(profile["experiences"]) >= 2)
        self.assertTrue(len(profile["education"]) >= 1)

    def test_formulate_tailored_cv_content_creates_star_bullets(self):
        profile = get_candidate_master_profile(self.session, self.user)
        tailored = formulate_tailored_cv_content(
            candidate=profile,
            job_title="Senior Python / FastAPI Developer",
            company="FinTech Core s.r.o.",
            job_desc="Požadujeme pokročilou znalost Python, FastAPI, Docker, PostgreSQL a REST API.",
            pros=["Silná shoda v Pythonu", "Zkušenosti s REST API"]
        )

        # Kontrola profesního profilu
        summary = tailored["tailored_summary"]
        self.assertIn("FinTech Core s.r.o.", summary)
        self.assertIn("Senior Python / FastAPI Developer", summary)

        # Kontrola cílových technologií
        target_techs = tailored["target_technologies"]
        self.assertIn("Python", target_techs)
        self.assertIn("FastAPI", target_techs)

        # Kontrola STAR odrážek u zkušeností
        experiences = tailored["experiences"]
        self.assertTrue(len(experiences) >= 2)

        for exp in experiences:
            bullets = exp["star_bullets"]
            self.assertTrue(len(bullets) >= 2)
            # Každá odrážka musí mít STAR label (S/T, A nebo R)
            labels = [b["label"] for b in bullets]
            has_star = any("S/T" in l or "A (" in l or "R (" in l for l in labels)
            self.assertTrue(has_star, f"Zkušenost {exp['title']} postrádá STAR label v {labels}")


class TestPdfCompilationAndSinglePageA4Constraint(unittest.TestCase):
    """Testy ověřující kompilaci PDF, dodržení 1 strany A4 a strojovou čitelnost."""

    def setUp(self):
        self.candidate = {
            "name": "Jakub Slavík",
            "email": "kubaslavik2411@gmail.com",
            "phone": "+420 774 943 349",
            "location": "Praha, ČR",
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
                }
            ],
            "languages": "Čeština (Rodilý mluvčí), Angličtina (B2/C1), Němčina (A1/A2)",
            "availability": "Dle dohody (HPP / IČO / Stáž), nástup možný ihned"
        }

    def test_compile_cv_to_pdf_produces_single_page_a4(self):
        render_data = formulate_tailored_cv_content(
            candidate=self.candidate,
            job_title="Backend Developer (FastAPI / Python)",
            company="Tech Innovations s.r.o.",
            job_desc="Hledáme Python backend vývojáře se znalostí FastAPI, PostgreSQL a Dockeru."
        )

        pdf_bytes, doc = compile_cv_to_pdf(render_data)

        # 1. Validní PDF začínající %PDF-
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"), "Vygenerovaný soubor nezačíná hlavičkou %PDF-")

        # 2. Striktně 1 strana A4
        self.assertEqual(doc.page_count, 1, f"Očekávána přesně 1 strana, ale získáno {doc.page_count}")

        # 3. Text je 100% selektovatelný a strojově čitelný (> 200 znaků)
        extracted_text = doc[0].get_text().strip()
        self.assertGreater(len(extracted_text), 200, "Text v PDF není dostatečně selektovatelný")

        # 4. Obsahuje klíčové prvky
        self.assertIn("JAKUB SLAV", extracted_text.upper())
        self.assertIn("Tech Innovations s.r.o.", extracted_text)
        self.assertIn("Python", extracted_text)

    def test_compaction_loop_handles_verbose_content_on_single_page(self):
        # Vytvoříme úmyslně delší data se 3 zkušenostmi a delšími texty
        verbose_candidate = dict(self.candidate)
        verbose_candidate["experiences"] = [
            {
                "id": "quant",
                "title": "Quant Investment Framework",
                "organization": "Inženýrský výzkumný projekt",
                "period": "2025 – současnost",
                "location": "Praha, ČR"
            },
            {
                "id": "klub",
                "title": "Klub Investorů VŠE",
                "organization": "Studentská investiční organizace",
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
        ]

        render_data = formulate_tailored_cv_content(
            candidate=verbose_candidate,
            job_title="Senior Python Software Engineer & Cloud Architect",
            company="Global Enterprise Cloud Systems Corporation",
            job_desc="Hledáme zkušeného inženýra se znalostí Python, FastAPI, Docker, Kubernetes, PostgreSQL, Redis a AWS."
        )

        pdf_bytes, doc = compile_cv_to_pdf(render_data)

        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertEqual(doc.page_count, 1, f"Kompaktační cyklus selhal, page_count={doc.page_count}")
        self.assertGreater(len(doc[0].get_text().strip()), 300)


class TestCvApiEndpoints(unittest.TestCase):
    """Integrační testy pro endpointy POST /cv/generate a GET /cv/download."""

    def setUp(self):
        self.client = TestClient(app)

    def test_generate_cv_endpoint_success(self):
        response = self.client.post("/api/applications/1/cv/generate")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "generated")
        self.assertEqual(data["page_count"], 1)
        self.assertTrue(data["filename"].endswith(".pdf"))
        self.assertTrue(os.path.exists(data["file_path"]))

        # Ověření uloženého souboru pomocí fitz
        with fitz.open(data["file_path"]) as doc:
            self.assertEqual(doc.page_count, 1)
            self.assertGreater(len(doc[0].get_text().strip()), 200)

    def test_download_cv_endpoint_returns_pdf(self):
        # 1. Nejprve zavoláme download
        response = self.client.get("/api/applications/1/cv/download")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-type"), "application/pdf")
        
        # Ověření hlavičky Content-Disposition
        content_disp = response.headers.get("content-disposition", "")
        self.assertIn("attachment", content_disp)
        self.assertIn("filename=", content_disp)
        self.assertTrue(content_disp.endswith('.pdf"'))

        # Ověření binárního obsahu
        pdf_bytes = response.content
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        self.assertEqual(doc.page_count, 1)
        self.assertGreater(len(doc[0].get_text().strip()), 200)

    def test_tailored_cv_path_stored_and_returned_in_get_application(self):
        # Zavoláme generování
        gen_res = self.client.post("/api/applications/1/cv/generate")
        self.assertEqual(gen_res.status_code, 200)

        # Načteme detail přihlášky
        detail_res = self.client.get("/api/applications/1")
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.json()
        self.assertIn("tailored_cv_path", detail)
        self.assertIsNotNone(detail["tailored_cv_path"])
        self.assertTrue(detail["tailored_cv_path"].startswith("uploads/cv_tailored_1"))

    def test_tailored_cv_path_in_get_applications_list(self):
        list_res = self.client.get("/api/applications")
        self.assertEqual(list_res.status_code, 200)
        items = list_res.json()
        self.assertTrue(len(items) > 0)
        app_1 = next((item for item in items if item["id"] == "1"), None)
        self.assertIsNotNone(app_1)
        self.assertIn("tailored_cv_path", app_1)

    def test_generate_cv_nonexistent_application_returns_404(self):
        response = self.client.post("/api/applications/999999/cv/generate")
        self.assertEqual(response.status_code, 404)

    def test_download_cv_nonexistent_application_returns_404(self):
        response = self.client.get("/api/applications/999999/cv/download")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
