import re
import unicodedata
from typing import List, Optional, Set

DOMAIN_CLUSTERS = {
    "data": {
        "data", "dwh", "etl", "analytics", "bi", "database", "bigdata", "spark", 
        "sql", "dbt", "databricks", "snowflake", "dataops", "lakehouse", "hadoop",
        "data-science", "data-engineering"
    },
    "qa": {
        "qa", "tester", "test", "testing", "quality", "sdet", "automation"
    },
    "devops": {
        "devops", "sre", "infrastructure", "infra", "platform", "cloud", 
        "sysadmin", "kubernetes", "k8s", "terraform"
    },
    "security": {
        "security", "infosec", "cyber", "cybersecurity", "soc", "penetration"
    },
    "frontend": {
        "frontend", "front-end", "react", "vue", "angular", "ui", "javascript", "typescript", "css", "html", "web"
    },
    "backend": {
        "backend", "back-end", "golang", "java", "dotnet", "c#", "rust", "php", "ruby", "django", "fastapi", "spring"
    },
    "mobile": {
        "ios", "android", "flutter", "swift", "kotlin", "mobile", "react-native"
    },
    "design": {
        "designer", "ux", "ui", "graphic", "art", "product design"
    },
    "product": {
        "product manager", "product owner", "po", "pm", "cpo"
    },
    "content": {
        "copywriter", "content", "writer", "marketing", "seo", "social media", "reviewer", "editor"
    },
    "sales": {
        "sales", "account executive", "bdr", "sdr", "business development", "prodej"
    },
    "hr": {
        "recruiter", "talent", "hr", "people ops", "headhunter"
    },
    "finance": {
        "accountant", "accounting", "finance", "financial", "auditor", "billing", "bookkeeper", "účetní"
    }
}

ROLE_SYNONYMS = {
    "engineer": {"engineer", "developer", "architect", "programmer", "vývojář", "programátor", "inženýr", "swe"},
    "developer": {"engineer", "developer", "architect", "programmer", "vývojář", "programátor", "swe"},
    "programmer": {"engineer", "developer", "architect", "programmer", "vývojář", "programátor"},
    "architect": {"architect", "lead", "principal", "staff"},
    "data": {"data", "dwh", "etl", "analytics", "bi", "bigdata", "spark", "sql", "dbt", "databricks", "database", "lakehouse"},
    "qa": {"qa", "tester", "test", "testing", "quality", "sdet", "automation"},
    "frontend": {"frontend", "front-end", "react", "vue", "angular", "ui", "javascript", "typescript"},
    "backend": {"backend", "back-end", "golang", "java", "python", "dotnet", "rust", "node"},
}

NEGATIVE_ROLE_PATTERNS = [
    # Hospitality / Blue collar / Services
    r"\bhousekeeping\b", r"\bhousekeeper\b", r"\bcleaner\b", r"\bmaid\b",
    r"\bhandyperson\b", r"\bhandyman\b", r"\bjanitor\b", r"\bcook\b", r"\bchef\b",
    r"\bnurse\b", r"\bcaregiver\b", r"\bdriver\b", r"\bcourier\b",
    
    # Clerical / Non-technical office
    r"\bclerk\b", r"\bdata\s+entry\b", r"\bbilling\b", r"\bbookkeeper\b", r"\bbookkeeping\b",
    r"\bpayroll\b", r"\btranscription\b", r"\btranscriptionist\b",
    r"\bassistant\b", r"\bvirtual\s+assistant\b", r"\badministrative\s+assistant\b", r"\breceptionist\b",
    r"\bcustomer\s+service\b", r"\bcustomer\s+support\b", r"\bcall\s+center\b",
    r"\bcontent\s+reviewer\b", r"\bmoderator\b",
    
    # Non-software engineering
    r"\bcosting\s+engineer\b", r"\bcivil\s+engineer\b", r"\bmechanical\s+engineer\b",
    r"\belectrical\s+engineer\b", r"\bstructural\s+engineer\b", r"\bhvac\b",
    
    # Marketing / Sales
    r"\bcopywriter\b", r"\bcopywriting\b", r"\bseo\s+executive\b", r"\bseo\s+specialist\b",
    r"\bsocial\s+media\b", r"\baccount\s+executive\b", r"\bsdr\b", r"\bbdr\b",
]


def normalize_token(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()


def match_word_or_phrase(pattern: str, full_text: str, tokens: Set[str]) -> bool:
    """Zkontroluje výskyt slova nebo fráze se striktními hranicemi slov (žádné 'bi' uvnitř 'billing')."""
    if " " in pattern or "-" in pattern:
        escaped = re.escape(pattern)
        return bool(re.search(r"\b" + escaped + r"\b", full_text))
    return pattern in tokens


def calculate_relevance(
    query: str, 
    title: str, 
    tags: Optional[List[str]] = None, 
    snippet: str = ""
) -> float:
    """
    Vypočítá sémantickou a doménovou shodu inzerátu s hledaným dotazem (0.0 až 1.0).
    Eliminuje falešné shody (např. 'Copywriter', 'Billing Specialist' nebo 'QA Engineer' při hledání 'Data Engineer').
    """
    if not query or not query.strip():
        return 1.0

    q_norm = normalize_token(query)
    t_norm = normalize_token(title)
    if not t_norm:
        return 0.0

    # 1. Kontrola negativních distractorů (pokud je uživatel explicitně nehledá)
    for pat in NEGATIVE_ROLE_PATTERNS:
        if re.search(pat, t_norm) and not re.search(pat, q_norm):
            return 0.0

    q_tokens = set(re.findall(r"\w+", q_norm))
    t_tokens = set(re.findall(r"\w+", t_norm))

    # Odstranit balastní slova z dotazu pro porovnávání
    noise_query = {"remote", "part", "time", "parttime", "full", "fulltime", "job", "position", "pozice"}
    q_words = [w for w in re.split(r"\s+", q_norm) if len(w) >= 2 and w not in noise_query]
    if not q_words:
        q_words = [w for w in re.split(r"\s+", q_norm) if len(w) >= 2]

    # 2. Identifikace domény dotazu a domény titulku
    query_domains = set()
    for d, syns in DOMAIN_CLUSTERS.items():
        if any(match_word_or_phrase(s, q_norm, q_tokens) for s in syns):
            query_domains.add(d)

    title_domains = set()
    for d, syns in DOMAIN_CLUSTERS.items():
        if any(match_word_or_phrase(s, t_norm, t_tokens) for s in syns):
            title_domains.add(d)

    # 3. Kontrola doménového konfliktu v titulku
    # Pokud dotaz specifikoval doménu (např. 'data'), ale titulek patří do JINÉ domény
    # a dotazovanou doménu v titulku VŮBEC nemá -> OKAMŽITÝ REJECT (0.0)
    # (Zabraňuje tomu, aby 'Senior React Full-stack Developer' nebo 'Senior QA Engineer' prošel na dotaz 'Data Engineer')
    if query_domains:
        has_query_domain_in_title = bool(query_domains & title_domains)
        if not has_query_domain_in_title:
            if title_domains:
                # Titulek má jinou, nekompatibilní doménu (např. react, devops, qa, content)
                return 0.0
            # Titulek nemá žádnou rozpoznanou doménu (např. jen 'Lead Engineer')
            # Povolíme pouze slabé skóre, pokud projde přes tagy
            return 0.15

    # 4. Token scoring pro jednotlivá slova dotazu
    matched_score = 0.0
    tag_str = " ".join([normalize_token(t) for t in (tags or [])])
    tag_tokens = set(re.findall(r"\w+", tag_str))
    s_norm = normalize_token(snippet)
    s_tokens = set(re.findall(r"\w+", s_norm))

    for w in q_words:
        syns = ROLE_SYNONYMS.get(w, {w})
        # Plná váha za výskyt v titulku pozice (titulek je autoritativní)
        if any(match_word_or_phrase(s, t_norm, t_tokens) for s in syns):
            matched_score += 1.0
        # Menší váha za výskyt v tagách
        elif tag_tokens and any(match_word_or_phrase(s, tag_str, tag_tokens) for s in syns):
            matched_score += 0.3
        # Minimální váha za výskyt v popisku
        elif s_norm and any(match_word_or_phrase(s, s_norm, s_tokens) for s in syns):
            matched_score += 0.1

    score = matched_score / len(q_words)
    return min(1.0, round(score, 2))
