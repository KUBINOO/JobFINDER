import re
import hashlib
import unicodedata
from typing import List, Optional, Tuple, Set
from selectolax.parser import HTMLParser

from schemas_v2 import (
    RawJobPayload, 
    JobListing, 
    EmploymentType, 
    RemotePolicy, 
    TimezoneRegion, 
    Compensation
)
from scrapers.cleaner import DOMCleaner


def normalize_string(text: str) -> str:
    """Odstraní diakritiku, převede na malá písmena a zbaví se nadbytečných mezer."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def clean_company_name(name: str) -> str:
    """Odstraní právní formy a generické přípony firem pro spolehlivou deduplikaci."""
    n = normalize_string(name)
    legal_suffixes = [
        " inc.", " inc", " llc", " ltd.", " ltd", " s.r.o.", " sro", " a.s.", " as",
        " gmbh", " corp.", " corp", " co.", " co", " bv", " pte"
    ]
    for suf in legal_suffixes:
        if n.endswith(suf):
            n = n[:-len(suf)].strip()
    return re.sub(r"[^\w\s]", "", n).strip()


def clean_title_tokens(title: str) -> str:
    """Sjednotí tokeny názvu pozice pro fuzzy porovnání s vyloučením modalit jako remote/part-time."""
    t = normalize_string(title)
    # Odstranit závorky a jejich obsah (např. (m/w/d), (remote), (100% remote))
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"\[.*?\]", "", t)

    noise_words = {
        "part", "time", "parttime", "full", "fulltime", "remote", "contract", 
        "contractor", "freelance", "hybrid", "onsite", "hiring", "urgent",
        "mwd", "fmd", "dmf", "100"
    }

    words = [w for w in re.findall(r"\w+", t) if len(w) >= 2 and w not in noise_words]
    if not words:
        words = [w for w in re.findall(r"\w+", t) if len(w) >= 2]

    return " ".join(sorted(words))


class NormalizationAgent:
    """
    Agent 3: Normalization & Deduplication Agent
    - Čistí HTML popisky na čistý čitelný text
    - Klasifikuje typ úvazku (Part-time, Contract, Full-time)
    - Validuje časové pásmo (EMEA, Worldwide, detekce US-only restrikcí)
    - Provádí deduplikaci napříč různými portály
    """

    EXCLUDED_PATTERNS = [
        r"\bus\s+only\b",
        r"\bunited\s+states\s+only\b",
        r"\bus\s+citizenship\b",
        r"\bus\s+citizen\b",
        r"\bnorth\s+america\s+only\b",
        r"\bcanada\s+only\b",
        r"\bpst\s+time\s*zone\b",
        r"\best\s+core\s+hours\b",
        r"\blatam\s+only\b",
        r"\bmust\s+be\s+located\s+in\s+the\s+us\b",
        r"\bmust\s+reside\s+in\s+the\s+us\b",
        r"\bno\s+c2c\b",
    ]

    EMEA_PATTERNS = [
        r"\bemea\b",
        r"\beurope\b",
        r"\beu\s+only\b",
        r"\bcet\b",
        r"\butc\+[0-3]\b",
        r"\bczech(ia)?\b",
        r"\bcesk[aá]\b",
        r"\bčesk[aá]\b",
        r"\bprague\b",
        r"\bpraha\b",
        r"\bbrno\b",
        r"\bostrava\b",
        r"\bplzen\b",
        r"\bgermany\b",
        r"\buk\b",
        r"\blondon\b",
        r"\bberlin\b",
    ]

    WORLDWIDE_PATTERNS = [
        r"\bworldwide\b",
        r"\banywhere\b",
        r"\bglobal\b",
        r"\btimezone\s+agnostic\b",
        r"\basync\b",
        r"\bwork\s+from\s+anywhere\b",
    ]

    PART_TIME_PATTERNS = [
        r"\bpart[\s-]time\b",
        r"\bzkr[aá]cen[yý]\b",
        r"\bcontractor\b",
        r"\bfreelance\b",
        r"\bhourly\b",
        r"\bstudent\b",
        r"\bwerkstudent\b",
        r"\bintern(ship)?\b",
        r"\b15-20\s*h\b",
        r"\b20-30\s*h\b",
        r"\bbrig[aá]d\b",
    ]

    def __init__(self, timezone_preference: str = "EMEA_ONLY"):
        self.timezone_preference = timezone_preference.upper()

    def sanitize_html(self, raw_html_or_text: str) -> str:
        """Vyčistí HTML tagy a zanechá čistý text se zachovanými odstavci."""
        if not raw_html_or_text:
            return ""
        if "<" in raw_html_or_text and ">" in raw_html_or_text:
            try:
                tree = HTMLParser(raw_html_or_text)
                DOMCleaner.clean_tree(tree)
                text = DOMCleaner.extract_clean_text(tree)
                if text and len(text) >= 50:
                    return text
            except Exception:
                pass
        # Fallback: odstranit běžné HTML tagy regulárním výrazem
        clean = re.sub(r"<[^>]+>", " ", raw_html_or_text)
        return re.sub(r"\s+", " ", clean).strip()

    def classify_employment_type(self, title: str, description: str, tags: List[str]) -> EmploymentType:
        combined = f"{title} {' '.join(tags)} {description[:1000]}".lower()
        if "intern" in combined or "staz" in combined or "stáž" in combined:
            return EmploymentType.INTERNSHIP
        for pat in self.PART_TIME_PATTERNS:
            if re.search(pat, combined):
                return EmploymentType.PART_TIME
        if "contract" in combined or "b2b" in combined or "freelance" in combined or "ičo" in combined:
            return EmploymentType.CONTRACTOR_B2B
        return EmploymentType.FULL_TIME

    def classify_timezone(self, location: str, text: str) -> Tuple[TimezoneRegion, bool]:
        """
        Určí časové pásmo a zda je nabídka kompatibilní s uživatelovými preferencemi (CET / EMEA).
        Vrací (TimezoneRegion, is_compatible).
        """
        combined = f"{location} {text[:2000]}".lower()

        # 1. Kontrola striktního vyloučení (např. US Only)
        for pat in self.EXCLUDED_PATTERNS:
            if re.search(pat, combined):
                return TimezoneRegion.AMERICAS, False

        # 2. Kontrola EMEA / Evropa
        for pat in self.EMEA_PATTERNS:
            if re.search(pat, combined):
                return TimezoneRegion.EMEA, True

        # 3. Kontrola Worldwide / Async
        for pat in self.WORLDWIDE_PATTERNS:
            if re.search(pat, combined):
                return TimezoneRegion.WORLDWIDE, True

        # Pokud není nic specifikováno a jde o remote portál, považujeme za Worldwide
        if "remote" in combined or not location or location.lower() == "worldwide":
            return TimezoneRegion.WORLDWIDE, True

        return TimezoneRegion.UNKNOWN, (self.timezone_preference != "EMEA_ONLY")

    def generate_canonical_id(self, company: str, title: str, source_url: str) -> str:
        """Vytvoří deterministický hash pro detekci křížových duplicit."""
        comp_norm = clean_company_name(company)
        title_tokens = clean_title_tokens(title)
        
        # Pokud máme čistou firmu i titulek, hashuje se z nich
        if comp_norm and len(title_tokens) >= 3:
            key = f"{comp_norm}::{title_tokens}"
        else:
            # Fallback na normalizovanou URL bez parametrů
            clean_url = source_url.split("?")[0].rstrip("/")
            key = clean_url

        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def normalize_and_deduplicate(
        self, 
        raw_items: List[RawJobPayload],
        query: str = "",
        part_time_only: bool = False
    ) -> List[JobListing]:
        """
        Zprocesuje seznam surových inzerátů:
        1. Sanitizuje texty.
        2. Prověří sémantickou relevanci vůči hledanému dotazu.
        3. Prověří Timezone / Remote kompatibilitu.
        4. Odstraní duplicity podle canonical_id.
        5. Seřadí výsledky podle relevance (nejrelevantnější první).
        """
        from agents.relevance import calculate_relevance

        scored_listings: List[tuple[float, JobListing]] = []
        seen_canonical_ids: Set[str] = set()

        for item in raw_items:
            clean_desc = self.sanitize_html(item.description)
            is_cz_portal = any(p in item.source_portal.lower() for p in ["jobs.cz", "prace.cz", "startupjobs", "czech"])
            if not is_cz_portal and len(clean_desc) < 50:
                # Inzeráty s příliš krátkým popisem z globálních API vyřazujeme (Quality Gate)
                continue

            # Sémantická relevance vůči dotazu uživatele (např. Data Engineer)
            rel_score = 1.0
            if query.strip():
                rel_score = calculate_relevance(query, item.title, item.raw_tags, clean_desc)
                # Vyřadíme inzeráty, které vůbec neodpovídají zadané profesi
                if rel_score < 0.45:
                    continue

            # Timezone kontrola
            raw_loc = item.raw_location or ""
            tz_region, is_tz_compatible = self.classify_timezone(raw_loc, f"{item.title} {clean_desc}")

            if self.timezone_preference == "EMEA_ONLY" and not is_tz_compatible:
                # Zahazujeme inzeráty vyžadující přítomnost v USA/Kanadě apod.
                continue

            # Employment type
            emp_type = self.classify_employment_type(item.title, clean_desc, item.raw_tags)
            if part_time_only and emp_type not in (EmploymentType.PART_TIME, EmploymentType.CONTRACTOR_B2B, EmploymentType.INTERNSHIP):
                # Pokud uživatel explicitně chce pouze part-time / contract, full-time přeskočíme
                continue

            # Canonical deduplikace
            canon_id = self.generate_canonical_id(item.company_name, item.title, item.source_url)
            if canon_id in seen_canonical_ids:
                continue

            seen_canonical_ids.add(canon_id)

            listing = JobListing(
                canonical_id=canon_id,
                source_portal=item.source_portal,
                source_url=item.source_url,
                apply_url=item.apply_url or item.source_url,
                title=item.title,
                company_name=item.company_name,
                description_raw=clean_desc,
                published_at=item.published_at,
                employment_type=emp_type,
                remote_policy=RemotePolicy.FULLY_REMOTE,
                timezone_region=tz_region,
                allowed_countries=[raw_loc] if raw_loc else ["Worldwide"],
                extracted_skills=item.raw_tags
            )

            scored_listings.append((rel_score, listing))

        # Seřadit podle skóre relevance sestupně (nejlepší shoda nahoře)
        scored_listings.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_listings]
