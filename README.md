# 💼 JobFinder AI – Automatizovaný asistent hledání práce

**JobFinder AI** je moderní desktopová webová aplikace navržená pro automatizaci a zefektivnění procesu hledání práce. Kombinuje web scraping českých i zahraničních pracovních portálů, inteligentní AI vyhodnocování shody s vaším životopisem a automatizované generování personalizovaných motivačních e-mailů s možností přímého odeslání přes SMTP.

---

## ⚡ 1. Rychlé spuštění (Jedním kliknutím)

Pro běžné používání stačí v kořenové složce **dvojkliknout na soubor:**

👉 **`SPUSTIT_JOBFINDER.bat`**

Tento skript automaticky:
1. Ověří virtuální prostředí Pythonu a závislosti.
2. Nastartuje **Backend (FastAPI)** na `http://localhost:8000`.
3. Nastartuje **Frontend (React / Vite)** na `http://localhost:3000`.
4. Automaticky otevře aplikaci ve vašem výchozím webovém prohlížeči.

> 💡 **Tip:** Klikněte pravým tlačítkem na `SPUSTIT_JOBFINDER.bat` ➔ *Odeslat na* ➔ *Plocha (vytvořit zástupce)* pro spouštění jedním klikem přímo z plochy Windows.

---

## 🌟 2. Hlavní funkce

### 🔍 A. Inteligentní vyhledávání a scraping inzerátů
- **Automatické prohledávání portálů:** Podpora Jobs.cz, Prace.cz, StartupJobs.cz a dalších.
- **Přidání libovolného odkazu:** Možnost vložit přímou URL adresu jakéhokoliv pracovního inzerátu na webu.
- **Automatická extrakce:** Web scraper automaticky stáhne název pozice, firmu, lokalitu a plný text inzerátu.

### 🧠 B. AI Analýza shody (Match Score)
- **Porovnání s životopisem:** AI porovná požadavky inzerátu s vaším nahraným životopisem (CV v PDF) a profilem.
- **Skóre v procentech (0–100 %):** Okamžitý přehled, jak moc se na danou pozici hodíte.
- **Detailní zdůvodnění:** Přehledné shrnutí vašich silných stránek pro danou pozici a případných chybějících dovedností.
- **Hromadné vyhodnocení:** Možnost jedním kliknutím spočítat AI shodu pro všechny nalezené inzeráty najednou.

### ✉️ C. Generování a odesílání e-mailů
- **Personalizované motivační dopisy:** AI vytvoří originální a věcný průvodní e-mail na míru dané firmě a pozici.
- **Podpora tónu komunikace:** Formální, přátelský nebo dynamický tón.
- **Přímé odeslání přes SMTP:** Odeslání e-mailu na kontaktní adresu firmy přímo z aplikace s automatickým připojením vašeho PDF životopisu jako přílohy.

### 📊 D. Kanban Pipeline & Správa žádostí
- Vizuální tabule pro sledování stavu všech vašich žádostí:
  - *Nové žádosti ➔ Připraveno ➔ Odesláno ➔ Pohovor ➔ Nabídka ➔ Zamítnuto*.
- Možnost přesouvat a měnit stavy jednoduchým kliknutím.

### 📜 E. Historie žádostí & Export dat
- Kompletní časová osa a tabulkový audit všech rozpracovaných i odeslaných žádostí.
- Filtrování podle stavu (*Odesláno*, *Pohovory*, *Nabídky*, *Zamítnuto*) a fulltextové vyhledávání.
- **Export do CSV:** Stažení celé historie do formátu CSV pro Excel nebo tabulky.

### 🔒 F. 100% Soukromí a lokální SQLite databáze
- Všechna vaše data (životopis, kontakty, historie e-mailů, poznámky) jsou uložena **pouze lokálně** ve vaší SQLite databázi (`backend/app.db`).
- Nic se neposílá na žádné cizí servery (kromě vámi zvoleného AI API pro analýzu).

---

## 🤖 3. Podporované AI modely

V **Nastavení → AI a Chování** si můžete vybrat svého oblíbeného poskytovatele:

| Poskytovatel | Doporučený model | Vlastnosti |
| :--- | :--- | :--- |
| **Google Gemini** *(Výchozí)* | `gemini-3.7-flash` / `gemini-2.5-flash` | Blesková rychlost, skvělá čeština, štědrý bezplatný limit |
| **OpenAI** | `gpt-4o` / `gpt-4o-mini` | Špičková kvalita stylistiky a argumentace |
| **Anthropic Claude** | `claude-3-5-sonnet` | Vynikající struktura a přirozený jazyk |
| **DeepSeek** | `deepseek-chat` / `deepseek-reasoner` | Výborný poměr cena / výkon |
| **Ollama (Lokální AI)** | `llama3`, `mistral`, `qwen2.5` | 100% offline bez nutnosti API klíčů |

---

## 📧 4. Nastavení odesílání e-mailů (SMTP)

Pro automatické odesílání e-mailů zadejte v **Nastavení → Odesílání (SMTP)** své přihlašovací údaje:

- **Pro Gmail:**
  1. Zapněte si na svém Google účtu *2fázové ověření*.
  2. Vygenerujte si tzv. **Heslo aplikace** (App Password) v sekci Zabezpečení Google účtu.
  3. SMTP Host: `smtp.gmail.com`, Port: `587`.
- **Pro Seznam.cz:**
  - SMTP Host: `smtp.seznam.cz`, Port: `465` (SSL) nebo `587` (TLS).
- **Pro vlastní doménu / Outlook:**
  - Zadejte standardní SMTP server a port vašeho poskytovatele.

---

## 🛠️ 5. Manuální spuštění pro vývojáře

Pokud chcete spouštět frontend a backend odděleně v terminálech:

### Backend:
```bash
cd backend
# Aktivace virtuálního prostředí (Windows PowerShell)
& .venv\Scripts\Activate.ps1
# Spuštění serveru
uvicorn main:app --reload --port 8000
```
- Swagger API dokumentace: [http://localhost:8000/docs](http://localhost:8000/docs)

### Frontend:
```bash
cd frontend
# Instalace balíčků (při prvním spuštění)
npm install
# Spuštění vývojového serveru
npm run dev
```
- Uživatelské rozhraní: [http://localhost:3000](http://localhost:3000)

---

## 📁 6. Struktura projektu

```text
jobfinder/
├── SPUSTIT_JOBFINDER.bat   # Hlavní klikací spouštěč pro Windows
├── start.bat               # Alternativní spouštěcí skript
├── start.ps1               # PowerShell orchestrační skript serverů
├── README.md               # Kompletní dokumentace k projektu
├── backend/
│   ├── app.db              # Lokální SQLite databáze se všemi daty
│   ├── main.py             # FastAPI aplikace a inicializace
│   ├── models.py           # SQLModel databázová schémata
│   ├── database.py         # Připojení k SQLite
│   ├── orchestrator.py     # Logika propojující scraping, AI a odesílání
│   ├── llm_service.py      # Integrace s AI modely (Gemini, OpenAI, Claude...)
│   ├── email_service.py    # SMTP odesílač e-mailů s PDF přílohou
│   ├── scrapers/           # Moduly pro stahování inzerátů z webu
│   ├── routers/            # API endpointy (žádosti, nastavení, nahrávání CV)
│   └── uploads/            # Uložené PDF soubory životopisů
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── Dashboard/  # Hlavní plocha, karty, filtry, Kanban pipeline
    │   │   │   ├── Layout.tsx        # Hlavní layout a navigace
    │   │   │   ├── DetailPanel.tsx   # Panel pro detail inzerátu a generování e-mailu
    │   │   │   ├── HistoryView.tsx   # Přehled historie, audit, statistiky, CSV export
    │   │   │   ├── PipelineBoard.tsx # Kanban tabule
    │   │   │   └── ExploreModal.tsx  # Hromadné vyhledávání na portálech
    │   │   ├── Settings/   # Nastavení profilu, AI klíčů a SMTP
    │   │   └── Onboarding/ # Úvodní průvodce nastavením
    │   └── App.tsx
    ├── package.json
    └── vite.config.ts
```

---

## ❓ 7. Často kladené dotazy (FAQ)

**Otázka: Kde jsou uložena moje data a hesla?**  
*Odpověď:* Vše je uloženo výhradně na vašem počítači v souboru `backend/app.db`. Žádná třetí strana k nim nemá přístup.

**Otázka: Mohu používat aplikaci bez placeného AI účtu?**  
*Odpověď:* Ano! Google Gemini poskytuje bezplatný API klíč pro osobní použití s velmi vysokým limitem dotazů, případně můžete využít lokální modely přes Ollama zdarma.

**Otázka: Jak vymazat historii nebo začít znovu?**  
*Odpověď:* V sekci **Nastavení → Systém a Data** najdete tlačítka pro bezpečné vymazání historie žádostí nebo kompletní restart úvodního průvodce.

<br>
<br>

---
---

<br>

# 🌐 English Documentation & Customization Guide

## 💼 JobFinder AI – Automated Job Search Assistant

**JobFinder AI** is an automated desktop web application designed to streamline job hunting. It features automated job scraping, resume-to-job AI match scoring, personalized cover letter/email generation, Kanban application tracking, and direct email delivery via SMTP.

---

> ### 🌍 Note on Domestic Market vs. Global Customization
> **By default, this repository is configured out-of-the-box for the Czech domestic job market** (scrapers for Czech job boards like *Jobs.cz*, *Prace.cz*, *StartupJobs.cz*, and a Czech user interface and prompts).
> 
> However, **the application architecture is 100% modular and decoupled.** You can easily adapt it for **any country, language, or job board worldwide** (e.g., US, UK, Germany, LinkedIn, Indeed, StepStone, Monster). Below is a step-by-step guide explaining what to modify.

---

## 🛠️ How to Customize for Your Country & Market

### 1. Adding or Modifying Job Scrapers (`backend/scrapers/`)
The scraping system has two main parts:

- **Single Job URL Parser (`backend/scrapers/detail.py`):**
  - Uses `Crawl4AI` and `BeautifulSoup4` with fallback heuristics to extract the title, company name, location, and description from **any URL worldwide** (including corporate career portals, LinkedIn, Indeed, etc.).
  - To support specific regional job boards with customized parsing, simply add a domain-specific extractor function in `backend/scrapers/detail.py`.

- **Multi-Job Search & Exploration (`backend/scrapers/search.py`):**
  - This module powers the *Explore / Search* modal.
  - To add your local job portals (e.g., `Indeed`, `LinkedIn`, `StepStone`, `Monster`):
    1. Open [`backend/scrapers/search.py`](file:///c:/Users/kubas/OneDrive/Desktop/jobfinder/backend/scrapers/search.py).
    2. Add a new scraper method for your portal (e.g., `_search_indeed(query, count)`).
    3. Construct the search URL for your country/region (e.g., `https://www.indeed.com/jobs?q={query}`).
    4. Parse the job cards with BeautifulSoup (CSS classes for title, company, URL).
    5. Register the new source in `search_jobs()` and in the frontend `ExploreModal.tsx`.

---

### 2. Customizing AI Prompts & Output Language
All AI logic resides in [`backend/orchestrator.py`](file:///c:/Users/kubas/OneDrive/Desktop/jobfinder/backend/orchestrator.py) and can also be overridden directly in the **Settings** UI:

- **Language of Generated Emails & Match Analysis:**
  - In `backend/orchestrator.py`, locate `evaluate_single_match()` and `generate_application_email()`.
  - The system prompt instructs the AI: *"Write in Czech..."*. You can change this to English, German, French, Spanish, or any other language.
- **In-App Custom Prompt:**
  - Navigate to **Settings → AI & Behavior → Custom Prompt Instructions**.
  - Enter instructions in English (e.g., *"Always write cover letters in professional US business English, emphasizing quantified achievements and leadership"*). The AI will follow your exact instructions.

---

### 3. Adapting the User Interface (Frontend)
- The frontend is built with **React 18 + Tailwind CSS + TypeScript**.
- All components reside in `frontend/src/components/`:
  - `Dashboard/Layout.tsx` – Navigation, brand header, view mode switch.
  - `Dashboard/DetailPanel.tsx` – Job inspection, AI evaluation card, email generator/editor.
  - `Dashboard/HistoryView.tsx` – Application audit table, status filters, CSV export.
  - `Dashboard/PipelineBoard.tsx` – Kanban board (`Pending`, `Sent`, `Interview`, `Offer`, `Rejected`).
  - `Settings/SettingsLayout.tsx` – Profile info, AI keys, and SMTP configuration.
- To translate or adapt labels, modify the text strings in these components or extract them into an i18n dictionary.

---

### 4. Email / SMTP Delivery
The email delivery service ([`backend/email_service.py`](file:///c:/Users/kubas/OneDrive/Desktop/jobfinder/backend/email_service.py)) supports standard RFC SMTP and works globally with:
- **Gmail / Google Workspace** (`smtp.gmail.com`, port 587) with App Password.
- **Outlook / Office 365** (`smtp.office365.com`, port 587).
- **Yahoo Mail** (`smtp.mail.yahoo.com`, port 587).
- **Custom Domains & SMTP Relays** (SendGrid, Mailgun, Postmark, Amazon SES).
- Automatically attaches your uploaded resume PDF.

---

## ⚡ Quick Start Guide (English)

### Option A: Windows 1-Click Launcher
Simply double-click:
👉 **`SPUSTIT_JOBFINDER.bat`**

### Option B: Cross-Platform Manual Start (macOS / Linux / Windows)

#### 1. Backend (Python FastAPI):
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
- API Docs (Swagger): [http://localhost:8000/docs](http://localhost:8000/docs)

#### 2. Frontend (React / Vite):
```bash
cd frontend
npm install
npm run dev
```
- Web Application: [http://localhost:3000](http://localhost:3000)

---

## 🤖 Supported LLM Providers

| Provider | Recommended Model | Notes |
| :--- | :--- | :--- |
| **Google Gemini** *(Default)* | `gemini-3.7-flash` / `gemini-2.5-flash` | High speed, excellent reasoning, generous free tier API |
| **OpenAI** | `gpt-4o` / `gpt-4o-mini` | Industry standard reasoning and tone formatting |
| **Anthropic Claude** | `claude-3-5-sonnet` | Top-tier nuanced writing and resume analysis |
| **DeepSeek** | `deepseek-chat` / `deepseek-reasoner` | High performance and cost efficiency |
| **Ollama** | `llama3`, `mistral`, `qwen2.5` | 100% offline, private, and local |

---

## 🔒 Privacy & Local Storage
- **100% Local SQLite Database:** All jobs, cover letters, application statuses, and notes are stored locally in `backend/app.db`.
- **Zero Tracking:** No personal information or credentials are sent to any external server except directly to your chosen AI provider API.
