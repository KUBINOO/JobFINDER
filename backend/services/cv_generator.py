import os
import re
import io
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from sqlmodel import Session, select
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa, default
import fitz

from models import Application, JobPosting, User, UserPreferences
from utils.pdf_parser import extract_text_from_pdf

logger = logging.getLogger(__name__)

# Registrace písem pro reportlab / xhtml2pdf
_FONTS_INITIALIZED = False

def init_pdf_fonts():
    """Zaregistruje TrueType písma s plnou podporou UTF-8 pro generování PDF."""
    global _FONTS_INITIALIZED
    if _FONTS_INITIALIZED:
        return

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping

    # Zkusíme najít systémový Arial na Windows nebo DejaVu na Linuxu
    font_candidates = [
        ("ArialCustom", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("ArialCustom", "C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/calibrib.ttf"),
        ("ArialCustom", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("ArialCustom", "/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf")
    ]

    for font_name, regular_path, bold_path in font_candidates:
        if os.path.exists(regular_path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, regular_path))
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(f"{font_name}-Bold", bold_path))
                    addMapping(font_name, 1, 0, f"{font_name}-Bold")
                addMapping(font_name, 0, 0, font_name)
                default.DEFAULT_FONT[font_name.lower()] = font_name
                default.DEFAULT_FONT[f"{font_name.lower()}-bold"] = f"{font_name}-Bold"
                _FONTS_INITIALIZED = True
                logger.info(f"Úspěšně zaregistrováno písmo {font_name} z {regular_path}")
                break
            except Exception as e:
                logger.warning(f"Nepodařilo se zaregistrovat písmo {font_name}: {e}")

    _FONTS_INITIALIZED = True


def is_czech_content(text: str) -> bool:
    """Detekuje, zda je inzerát či text v češtině."""
    lower = text.lower()
    cz_keywords = [
        "požadavky", "hledáme", "vývojář", "zkušenosti", "nabízíme", "náplň práce",
        "praxe", "tým", "společnost", "pozice", "odpovědnost", "znalost", "výhodou",
        "praha", "brno", "česká", "práce", "úvazek", "inženýr"
    ]
    matches = sum(1 for kw in cz_keywords if kw in lower)
    return matches >= 2


def extract_job_technologies(job_text: str) -> Dict[str, List[str]]:
    """
    Analyzuje text inzerátu a extrahuje detekované technologie a klíčová slova
    rozdělená do logických kategorií pro ATS optimalizaci.
    """
    tech_catalog = {
        "backend": [
            "Python", "FastAPI", "Django", "Flask", "asyncio", "REST API", "GraphQL",
            "SQLAlchemy", "SQLModel", "Pydantic", "Celery", "Redis", "Kafka", "RabbitMQ",
            "C#", ".NET", "Java", "Spring Boot", "Go", "Golang", "Rust", "Node.js", "Express"
        ],
        "data": [
            "Pandas", "NumPy", "SciPy", "SQL", "PostgreSQL", "SQLite", "MongoDB",
            "MySQL", "Elasticsearch", "ETL", "Scraping", "BeautifulSoup", "Selectolax",
            "Playwright", "Selenium", "PowerBI", "Data Mining", "PyTorch", "TensorFlow"
        ],
        "devops": [
            "Docker", "Kubernetes", "Linux", "Git", "GitHub", "GitLab", "CI/CD",
            "AWS", "GCP", "Azure", "Terraform", "Nginx", "Postman", "Bash"
        ],
        "frontend": [
            "JavaScript", "TypeScript", "React", "Next.js", "Vue", "HTML5", "CSS3",
            "Tailwind CSS", "Vite"
        ]
    }

    found: Dict[str, List[str]] = {cat: [] for cat in tech_catalog}
    all_found: List[str] = []
    lower_text = job_text.lower()

    for category, items in tech_catalog.items():
        for item in items:
            pattern = r'\b' + re.escape(item.lower()) + r'(?:u|em|e|a|ovi|s|es)?\b'
            if re.search(pattern, lower_text):
                found[category].append(item)
                all_found.append(item)

    found["all"] = all_found
    return found


def get_candidate_master_profile(session: Session, user: Optional[User]) -> Dict[str, Any]:
    """
    Získá kompletní profil kandidáta z databáze a master CV (cvčko.pdf).
    """
    user_prefs = session.get(UserPreferences, 1)

    candidate_name = (user_prefs and user_prefs.full_name) or (user and f"{user.first_name} {user.last_name}") or "Jakub Slavík"
    candidate_email = (user and user.email) or (user_prefs and user_prefs.smtp_email) or "kubaslavik2411@gmail.com"
    candidate_phone = (user_prefs and user_prefs.phone_number) or "+420 774 943 349"
    candidate_linkedin = (user_prefs and user_prefs.linkedin_url) or "linkedin.com/in/jakub-slavik"
    if candidate_linkedin.startswith("http"):
        candidate_linkedin = candidate_linkedin.replace("https://", "").replace("http://", "").rstrip("/")

    candidate_github = "github.com/KUBINOO"
    candidate_location = "Praha / Varnsdorf, ČR"

    # Načtení textu ze souboru cvčko.pdf
    cv_text = ""
    cv_path = user_prefs.cv_file_path if user_prefs else None
    if not cv_path or not os.path.exists(cv_path):
        uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
        if os.path.exists(uploads_dir):
            pdf_candidates = [
                os.path.join(uploads_dir, "cvčko.pdf"),
                os.path.join(uploads_dir, "cvcko.pdf")
            ]
            for c in pdf_candidates:
                if os.path.exists(c):
                    cv_path = c
                    break

            if not cv_path:
                pdfs = [os.path.join(uploads_dir, f) for f in os.listdir(uploads_dir) if f.lower().endswith(".pdf") and not f.startswith("cv_tailored")]
                if pdfs:
                    pdfs.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                    cv_path = pdfs[0]

    if cv_path and os.path.exists(cv_path):
        try:
            cv_text = extract_text_from_pdf(cv_path)
            logger.info(f"Načten text z CV: {cv_path} ({len(cv_text)} znaků)")
        except Exception as e:
            logger.warning(f"Chyba při čtení CV: {e}")

    # Master zkušenosti kandidáta
    master_experiences = [
        {
            "id": "quant",
            "title": "Quant Investment Framework",
            "role": "Vývojář v Pythonu | Datová analýza & Algoritmické modelování",
            "organization": "Samostatný inženýrský projekt",
            "period": "Listopad 2025 – současnost",
            "location": "Praha, ČR",
            "base_bullets": [
                {
                    "star": "S/T",
                    "text": "Návrh a realizace modulární analytické platformy v Pythonu pro screening a kvantitativní hodnocení akcií z indexu S&P 500."
                },
                {
                    "star": "A",
                    "text": "Implementace asynchronního stahování dat přes Yahoo Finance API a REST endpointy, aplikace Markowitzova modelu optimalizace portfolia (SciPy) a strategie Smart DCA."
                },
                {
                    "star": "R",
                    "text": "Zrychlení zpracování historických cenových řad o 65 % a dosažení 99,8% stability pipeline při souběžném dotazování stovek aktiv."
                }
            ]
        },
        {
            "id": "klub",
            "title": "Klub Investorů VŠE",
            "role": "Člen Development oddělení | IT & Software infrastruktura",
            "organization": "Klub Investorů FIS VŠE",
            "period": "Duben 2026 – současnost",
            "location": "Praha, ČR",
            "base_bullets": [
                {
                    "star": "S/T",
                    "text": "Vývoj a technologická podpora interních systémů největšího studentského investičního klubu v ČR."
                },
                {
                    "star": "A",
                    "text": "Nasazení moderního technologického stacku v Pythonu pro automatizaci sběru dat, integraci s webovými API a správu členské základny."
                },
                {
                    "star": "R",
                    "text": "Snížení manuální administrativy o 45 % a zajištění vysoké spolehlivosti softwarových služeb pro více než 500 aktivních členů."
                }
            ]
        },
        {
            "id": "eshop",
            "title": "Správa e-shopu La-Vin.cz",
            "role": "Administrátor e-shopu | Správa digitálních dat a katalogu",
            "organization": "La-Vin.cz",
            "period": "2024 – 2025",
            "location": "Praha, ČR",
            "base_bullets": [
                {
                    "star": "S/T",
                    "text": "Kompletní správa provozu internetového obchodu včetně zalistování nových produktů a synchronizace skladových zásob."
                },
                {
                    "star": "A",
                    "text": "Automatizace datových exportů a importů, validace konzistence produktového portfolia a příprava marketingových digitálních podkladů."
                },
                {
                    "star": "R",
                    "text": "Zkrácení doby publikace nového sortimentu o 40 % a optimalizace vizibility značky v online prostoru."
                }
            ]
        }
    ]

    # Master vzdělání
    master_education = [
        {
            "institution": "Vysoká škola ekonomická v Praze (VŠE FIS)",
            "degree_field": "Bakalářské studium: Aplikovaná informatika",
            "period": "2025 – současnost",
            "location": "Praha, ČR",
            "details": "Relevantní předměty: Matematika pro informatiky, Datové minimum, Algoritmizace a programování, Databázové systémy"
        },
        {
            "institution": "Biskupské gymnázium Varnsdorf",
            "degree_field": "Všeobecné gymnázium – Absolvoval s vyznamenáním",
            "period": "2017 – 2025",
            "location": "Varnsdorf, ČR",
            "details": "Hlavní organizátor a koordinátor ročníkových aktivit a maturitního plesu (vedení týmu, logistika)"
        }
    ]

    return {
        "name": candidate_name,
        "email": candidate_email,
        "phone": candidate_phone,
        "location": candidate_location,
        "linkedin": candidate_linkedin,
        "github": candidate_github,
        "cv_text": cv_text,
        "experiences": master_experiences,
        "education": master_education,
        "languages": "Čeština (Rodilý mluvčí), Angličtina (B2/C1 – plynná komunikace v IT), Němčina (A1/A2)",
        "availability": "Dle dohody (HPP / IČO / Stáž / Part-time), nástup možný ihned"
    }


def formulate_tailored_cv_content(
    candidate: Dict[str, Any],
    job_title: str,
    company: str,
    job_desc: str,
    pros: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Sestaví dynamický obsah životopisu na míru danému inzerátu:
    - Vybere a zvýrazní relevantní tech stack v první řadě dovedností
    - Přeformuluje odrážky zkušeností do formátu STAR s důrazem na klíčová slova inzerátu
    - Vytvoří cílené profesní shrnutí přímo pro danou firmu a pozici
    """
    is_cz = is_czech_content(f"{job_title} {job_desc}")
    detected = extract_job_technologies(f"{job_title} {job_desc}")
    all_detected = detected.get("all", [])

    # Cílové technologie vytažené z inzerátu a seřazené
    target_tech_list: List[str] = []
    # Nejprve technologie nalezené v inzerátu
    for t in all_detected:
        if t not in target_tech_list:
            target_tech_list.append(t)

    # Pokud inzerát zmiňuje málo technologií, doplníme základní relevantní stack
    default_backend_stack = ["Python", "FastAPI", "SQL", "PostgreSQL", "Docker", "asyncio"]
    for t in default_backend_stack:
        if len(target_tech_list) < 6 and t not in target_tech_list:
            target_tech_list.append(t)

    target_technologies_str = ", ".join(target_tech_list[:8])

    # Seskupení zbývajících dovedností
    backend_skills = "Python (FastAPI, Flask), asyncio, REST API, SQLModel, SQLAlchemy, microservices"
    database_devops_skills = "PostgreSQL, SQLite, MongoDB, Docker, Git/GitHub, Linux, CI/CD"
    other_skills = "JavaScript, React, Pandas, NumPy, SciPy, BeautifulSoup, PowerBI"

    # Profesní profil ušitý na míru pozici
    lead_techs = ", ".join(target_tech_list[:3]) if target_tech_list else "Python a FastAPI"
    if is_cz:
        tailored_summary = (
            f"Cílevědomý softwarový inženýr se zaměřením na backendový vývoj, asynchronní architektury a datové pipeline. "
            f"V kontextu pozice {job_title} ve společnosti {company} nabízím praktické zkušenosti s technologiemi {lead_techs}, "
            f"návrhem škálovatelných služeb a automatizací. Důraz na vysokou modularitu, čistý a testovaný kód, měřitelné výsledky a rychlou orientaci v moderních systémech."
        )
    else:
        tailored_summary = (
            f"Driven software engineer specializing in backend systems, asynchronous pipelines, and data-intensive workflows. "
            f"Targeting the {job_title} role at {company}, I bring hands-on experience in {lead_techs}, scalable service design, and pipeline optimization. "
            f"Committed to clean architecture, automated test suites, measurable performance impact, and rapid technical adaptation."
        )

    # Přeformulování zkušeností do formátu STAR s důrazem na požadavky inzerátu
    tailored_experiences = []
    matched_tech_1 = target_tech_list[0] if len(target_tech_list) > 0 else "Python"
    matched_tech_2 = target_tech_list[1] if len(target_tech_list) > 1 else "FastAPI"
    matched_tech_3 = target_tech_list[2] if len(target_tech_list) > 2 else "Docker"

    for exp in candidate["experiences"]:
        exp_id = exp["id"]
        star_bullets = []

        if exp_id == "quant":
            star_bullets = [
                {
                    "label": "S/T (Výchozí výzva)",
                    "text": f"Návrh robustní analytické architektury pro paralelní screening aktiv S&P 500 a zpracování nestrukturovaných finančních dat s důrazem na stack {matched_tech_1}."
                },
                {
                    "label": "A (Inženýrské řešení)",
                    "text": f"Implementace modulárních asynchronních služeb s využitím {matched_tech_1}, Pandas a SciPy; napojení na REST API a nasazení kontejnerizovaných postupů ({matched_tech_3})."
                },
                {
                    "label": "R (Kvantifikovaný výsledek)",
                    "text": "Zkrácení doby odezvy datové pipeline o 65 %, dosažení 99,8% spolehlivosti při vysoké zátěži a úspěšná implementace Markowitzova optimalizačního modelu."
                }
            ]
        elif exp_id == "klub":
            star_bullets = [
                {
                    "label": "S/T (Zadání)",
                    "text": "Modernizace a škálování softwarové infrastruktury největšího studentského investičního klubu v ČR pro stovky aktivních uživatelů."
                },
                {
                    "label": "A (Realizace)",
                    "text": f"Vývoj backendových modulů v {matched_tech_1} ({matched_tech_2}), automatizace synchronizace databází a zavedení verzování přes Git s CI/CD kontrolami."
                },
                {
                    "label": "R (Přínos)",
                    "text": "Eliminace manuální administrativy o 45 %, zrychlení odbavení interních požadavků a spolehlivý provoz pro více než 500 členů organizace."
                }
            ]
        elif exp_id == "eshop":
            star_bullets = [
                {
                    "label": "S/T (Zadání)",
                    "text": "Zajištění správy digitálního katalogu e-shopu a zefektivnění procesů zalistování produktových položek a aktualizace cen."
                },
                {
                    "label": "A (Realizace)",
                    "text": "Vytvoření automatizovaných skriptů pro kontrolu datové integrity a export produktových feedů s přímou vazbou na skladové hospodářství."
                },
                {
                    "label": "R (Přínos)",
                    "text": "Zrychlení publikace nových produktů o 40 % a minimalizace chybovosti v dostupnosti sortimentu."
                }
            ]

        tailored_experiences.append({
            "title": exp["title"],
            "organization": exp["organization"],
            "period": exp["period"],
            "location": exp["location"],
            "star_bullets": star_bullets
        })

    return {
        "candidate": {
            "name": candidate["name"],
            "email": candidate["email"],
            "phone": candidate["phone"],
            "location": candidate["location"],
            "linkedin": candidate["linkedin"],
            "github": candidate["github"],
        },
        "job": {
            "title": job_title,
            "company": company,
        },
        "tailored_summary": tailored_summary,
        "target_technologies": target_technologies_str,
        "backend_skills": backend_skills,
        "database_devops_skills": database_devops_skills,
        "other_skills": other_skills,
        "experiences": tailored_experiences,
        "education": candidate["education"],
        "languages": candidate["languages"],
        "availability": candidate["availability"]
    }


def compile_cv_to_pdf(render_data: Dict[str, Any], template_path: Optional[str] = None) -> Tuple[bytes, fitz.Document]:
    """
    Zkompiluje HTML šablonu do PDF pomocí xhtml2pdf a aplikuje dynamický
    kompaktační cyklus, který garantuje striktně 1 stránku A4 a validní strojově čitelný text.
    """
    init_pdf_fonts()

    if not template_path:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(base_dir, "templates", "cv_template.html")

    template_dir = os.path.dirname(template_path)
    template_name = os.path.basename(template_path)

    env = Environment(loader=FileSystemLoader(template_dir))
    tmpl = env.get_template(template_name)

    # Kaskáda kompaktačních úrovní pro zaručení 1 stránky A4
    compaction_levels = [
        # Úroveň 0: Standardní vzdušné rozvržení
        {
            "base_font_size": "8.8pt",
            "name_font_size": "15pt",
            "heading_font_size": "9.5pt",
            "line_height": "1.22",
            "margin_top": "7mm",
            "margin_bottom": "7mm",
            "margin_left": "10mm",
            "margin_right": "10mm",
            "section_margin_top": "5pt",
            "section_margin_bottom": "3pt",
            "entry_margin_bottom": "3.5pt",
            "bullet_margin_bottom": "1.5pt",
            "max_bullets_per_exp": 3,
        },
        # Úroveň 1: Mírné zmenšení písma a mezer
        {
            "base_font_size": "8.4pt",
            "name_font_size": "14pt",
            "heading_font_size": "9.0pt",
            "line_height": "1.18",
            "margin_top": "6mm",
            "margin_bottom": "6mm",
            "margin_left": "9mm",
            "margin_right": "9mm",
            "section_margin_top": "4pt",
            "section_margin_bottom": "2.5pt",
            "entry_margin_bottom": "2.8pt",
            "bullet_margin_bottom": "1.2pt",
            "max_bullets_per_exp": 3,
        },
        # Úroveň 2: Kompaktní rozvržení
        {
            "base_font_size": "8.0pt",
            "name_font_size": "13pt",
            "heading_font_size": "8.6pt",
            "line_height": "1.15",
            "margin_top": "5mm",
            "margin_bottom": "5mm",
            "margin_left": "8mm",
            "margin_right": "8mm",
            "section_margin_top": "3.5pt",
            "section_margin_bottom": "2pt",
            "entry_margin_bottom": "2.2pt",
            "bullet_margin_bottom": "1.0pt",
            "max_bullets_per_exp": 3,
        },
        # Úroveň 3: Striktní kompakce s redukcí odrážek na 2 klíčové na zkušenost
        {
            "base_font_size": "7.6pt",
            "name_font_size": "12pt",
            "heading_font_size": "8.2pt",
            "line_height": "1.12",
            "margin_top": "4.5mm",
            "margin_bottom": "4.5mm",
            "margin_left": "8mm",
            "margin_right": "8mm",
            "section_margin_top": "3pt",
            "section_margin_bottom": "1.5pt",
            "entry_margin_bottom": "1.8pt",
            "bullet_margin_bottom": "0.8pt",
            "max_bullets_per_exp": 2,
        },
    ]

    last_pdf_bytes: Optional[bytes] = None
    last_doc: Optional[fitz.Document] = None

    for level_idx, config in enumerate(compaction_levels):
        merged_data = dict(render_data)
        merged_data.update(config)

        # Oříznutí počtu odrážek pokud je v konfiguraci omezení
        max_bullets = config.get("max_bullets_per_exp", 3)
        if "experiences" in merged_data:
            compacted_exps = []
            for exp in merged_data["experiences"]:
                exp_copy = dict(exp)
                if "star_bullets" in exp_copy and len(exp_copy["star_bullets"]) > max_bullets:
                    exp_copy["star_bullets"] = exp_copy["star_bullets"][:max_bullets]
                compacted_exps.append(exp_copy)
            merged_data["experiences"] = compacted_exps

        rendered_html = tmpl.render(**merged_data)

        # Kompilace přes xhtml2pdf do paměťového bufferu
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(
            src=rendered_html,
            dest=pdf_buffer,
            encoding="utf-8"
        )

        if pisa_status.err:
            logger.warning(f"Kompilace xhtml2pdf vykázala varování (úroveň {level_idx})")

        pdf_bytes = pdf_buffer.getvalue()
        last_pdf_bytes = pdf_bytes

        # Programatické ověření pomocí PyMuPDF (fitz)
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            last_doc = doc
            page_count = doc.page_count
            selectable_text = doc[0].get_text() if page_count > 0 else ""

            logger.info(
                f"Kompilace úroveň {level_idx}: {page_count} stran, "
                f"{len(selectable_text.strip())} znaků selektovatelného textu, "
                f"velikost PDF {len(pdf_bytes)} bajtů"
            )

            # Kontrola kritérií: validní PDF, přesně 1 strana, selektovatelný text > 200 znaků
            if (
                pdf_bytes.startswith(b"%PDF-")
                and page_count == 1
                and len(selectable_text.strip()) > 200
            ):
                logger.info(f"✅ Životopis úspěšně zkompilován a ověřen na úroveň {level_idx} (1 strana A4).")
                return pdf_bytes, doc
        except Exception as e:
            logger.error(f"Chyba při ověřování PDF pomocí fitz: {e}")

    if last_pdf_bytes and last_doc:
        return last_pdf_bytes, last_doc

    raise RuntimeError("Nepodařilo se vygenerovat validní PDF životopis.")


def sanitize_filename_part(text: str) -> str:
    """Odstraní diakritiku a nepovolené znaky ze jména firmy/souboru."""
    import unicodedata
    normalized = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    cleaned = re.sub(r'[^a-zA-Z0-9_\-]', '', normalized.replace(" ", "_"))
    return cleaned[:30] or "Company"


def generate_tailored_cv_for_application(
    session: Session,
    application_id: int,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Vygeneruje dynamický 1-stránkový ATS životopis na míru dané žádosti o práci.
    Uloží výsledek do složky uploads/ a aktualizuje `application.tailored_cv_path`.
    """
    application = session.get(Application, application_id)
    if not application:
        raise ValueError(f"Žádost s ID {application_id} nebyla nalezena.")

    job = application.job_posting
    user = application.user

    job_title = (job and job.title) or "Software Engineer"
    company = (job and job.company_name) or "Hiring Company"
    job_desc = (job and job.description) or ""

    # Získání master profilu kandidáta
    candidate_profile = get_candidate_master_profile(session, user)

    # Příprava PROs z databáze
    pros_list: List[str] = []
    if application.pros:
        try:
            pros_list = json.loads(application.pros)
        except Exception:
            pros_list = [application.pros]

    # Sestavení tailored obsahu (STAR odrážky + klíčová slova inzerátu)
    render_data = formulate_tailored_cv_content(
        candidate=candidate_profile,
        job_title=job_title,
        company=company,
        job_desc=job_desc,
        pros=pros_list
    )

    # Zkompilování do 1-stránkového A4 PDF s verifikací
    pdf_bytes, doc = compile_cv_to_pdf(render_data)

    # Příprava výstupního souboru
    if not output_dir:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(base_dir, "uploads")
    os.makedirs(output_dir, exist_ok=True)

    pdf_filename = f"cv_tailored_{application_id}.pdf"
    pdf_abs_path = os.path.join(output_dir, pdf_filename)

    with open(pdf_abs_path, "wb") as f:
        f.write(pdf_bytes)

    # Programatická kontrola uloženého souboru přes fitz
    with fitz.open(pdf_abs_path) as verified_doc:
        assert verified_doc.page_count == 1, f"Očekávána 1 strana, ale získáno {verified_doc.page_count}"
        extracted_text = verified_doc[0].get_text().strip()
        assert len(extracted_text) > 200, "Text v PDF není dostatečně selektovatelný"

    # Aktualizace databáze
    relative_path = os.path.join("uploads", pdf_filename).replace("\\", "/")
    application.tailored_cv_path = relative_path
    session.add(application)
    session.commit()
    session.refresh(application)

    company_slug = sanitize_filename_part(company)
    download_filename = f"CV_Jakub_Slavik_{company_slug}.pdf"

    logger.info(f"✅ ATS CV úspěšně vygenerováno pro přihlášku {application_id} -> {pdf_abs_path}")

    return {
        "status": "generated",
        "file_path": pdf_abs_path,
        "page_count": 1,
        "filename": download_filename,
        "relative_path": relative_path
    }
