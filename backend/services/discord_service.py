import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

# Discord embed color: Tailwind green-500 (0x22c55e = 2278750)
DISCORD_EMBED_COLOR_GREEN = 0x22c55e
DEFAULT_MIN_MATCH_SCORE = 85
HTTP_TIMEOUT_SECONDS = 10.0


def format_pros_bullets(pros: Optional[List[str]]) -> str:
    """
    Formátuje seznam důvodů shody (PROs) do až 3 přehledných odrážek.
    Pokud žádné PROs nejsou k dispozici, vrací obecnou validní odrážku.
    """
    if not pros:
        return "• Vysoká celková shoda s profilem a preferencemi kandidáta"

    valid_pros: List[str] = [str(p).strip() for p in pros if p and str(p).strip()]
    if not valid_pros:
        return "• Vysoká celková shoda s profilem a preferencemi kandidáta"

    # Maximálně 3 klíčové důvody shody
    top_3 = valid_pros[:3]
    formatted_bullets = []
    for bullet in top_3:
        if not bullet.startswith("•") and not bullet.startswith("-"):
            formatted_bullets.append(f"• {bullet}")
        else:
            # Sjednotit na tečku
            bullet_clean = bullet.lstrip("•- \t")
            formatted_bullets.append(f"• {bullet_clean}")

    return "\n".join(formatted_bullets)


def build_discord_embed(
    job_title: str,
    company: str,
    location: Optional[str] = None,
    salary: Optional[str] = None,
    match_score: int = 0,
    pros: Optional[List[str]] = None,
    source_url: str = "",
) -> Dict[str, Any]:
    """
    Sestaví bohatou Discord Embed kartu se zelenou barvou (0x22c55e)
    a všemi povinnými poli:
    - Název pozice (Title) s přímým odkazem
    - Firma (Company)
    - Lokalita / Remote status
    - Platové rozpětí (pokud je známo)
    - 3 klíčové výhody (PROs formátované do odrážek)
    - Přímý odkaz na inzerát (Direct link)
    - Match score
    """
    clean_title = job_title.strip() if job_title else "Pracovní pozice"
    clean_company = company.strip() if company else "Neznámá společnost"
    clean_location = location.strip() if (location and location.strip()) else "Lokalita neuvedena / Remote"
    clean_salary = salary.strip() if (salary and salary.strip()) else "Neuvedeno"
    clean_url = source_url.strip() if source_url else ""
    pros_text = format_pros_bullets(pros)

    fields = [
        {
            "name": "🏢 Společnost",
            "value": clean_company,
            "inline": True,
        },
        {
            "name": "📍 Lokalita / Remote",
            "value": clean_location,
            "inline": True,
        },
        {
            "name": "💰 Platové rozpětí",
            "value": clean_salary,
            "inline": True,
        },
        {
            "name": "⭐ Match Score",
            "value": f"**{match_score} %**",
            "inline": True,
        },
        {
            "name": "✨ Klíčové výhody (PROs)",
            "value": pros_text,
            "inline": False,
        },
    ]

    if clean_url:
        fields.append({
            "name": "🔗 Přímý odkaz",
            "value": f"[Otevřít nabídku na webu]({clean_url})",
            "inline": False,
        })

    embed = {
        "title": f"🎯 {clean_title}",
        "url": clean_url if clean_url else None,
        "description": f"Byla vyhodnocena nová prémiová pozice s vysokou shodou (**{match_score} %**)!",
        "color": DISCORD_EMBED_COLOR_GREEN,
        "fields": fields,
        "footer": {
            "text": "JobFinder Career Copilot • High-Match Alert",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Vyčistit None hodnoty pro čisté Discord API
    return {k: v for k, v in embed.items() if v is not None}


def format_discord_alert_payload(
    job_title: str,
    company: str,
    location: Optional[str] = None,
    salary: Optional[str] = None,
    match_score: int = 0,
    pros: Optional[List[str]] = None,
    source_url: str = "",
) -> Dict[str, Any]:
    """Vrátí kompletní JSON tělo pro volání Discord Webhooku."""
    return {
        "embeds": [
            build_discord_embed(
                job_title=job_title,
                company=company,
                location=location,
                salary=salary,
                match_score=match_score,
                pros=pros,
                source_url=source_url,
            )
        ]
    }


async def send_discord_high_match_alert(
    job_title: str,
    company: str,
    location: Optional[str] = None,
    salary: Optional[str] = None,
    match_score: int = 0,
    pros: Optional[List[str]] = None,
    source_url: str = "",
    webhook_url: Optional[str] = None,
    min_score: int = DEFAULT_MIN_MATCH_SCORE,
) -> bool:
    """
    Asynchronně odešle bohatou Discord Embed kartu pro nabídky se skóre >= min_score (85 %).

    Resilience:
    - Pokud je skóre < min_score (85 %) nebo neplatné/None, operaci bezpečně přeskočí a vrátí False.
    - Webhook URL čte z parametru nebo z proměnné prostředí DISCORD_WEBHOOK_URL.
    - Pokud URL chybí, je prázdná nebo neplatná, zaloguje INFO/WARNING a vrátí False bez výjimky.
    - Veškeré operace jsou zabaleny v top-level try-except bloku s timeoutem.
    - Nikdy nevyvolává výjimky do volajícího kódu.
    """
    try:
        # 1. Kontrola a validace match_score
        if match_score is None:
            logger.info("Match score je None. Přeskakuji Discord alert.")
            return False

        try:
            score_val = float(match_score)
        except (ValueError, TypeError):
            logger.warning(f"Neplatné match_score ({match_score}). Přeskakuji Discord alert.")
            return False

        if score_val < float(min_score):
            logger.info(
                f"Match score ({score_val} %) je nižší než minimální práh pro Discord alert ({min_score} %). Přeskakuji."
            )
            return False

        # 2. Získání a validace webhook URL
        target_webhook = webhook_url if webhook_url is not None else os.getenv("DISCORD_WEBHOOK_URL")
        if not isinstance(target_webhook, str):
            logger.info(
                "Discord webhook URL není nakonfigurována nebo není řetězec. "
                "Notifikace byla bezpečně přeskočena."
            )
            return False

        target_webhook = target_webhook.strip()
        if not target_webhook:
            logger.info(
                "Discord webhook URL je prázdná. Notifikace byla bezpečně přeskočena."
            )
            return False

        if not (target_webhook.startswith("http://") or target_webhook.startswith("https://")):
            logger.warning(
                f"Neplatný formát Discord webhook URL (očekáván protokol http/https): {target_webhook}. "
                "Notifikace přeskočena."
            )
            return False

        # 3. Příprava payloadu
        payload = format_discord_alert_payload(
            job_title=str(job_title or ""),
            company=str(company or ""),
            location=str(location) if location is not None else None,
            salary=str(salary) if salary is not None else None,
            match_score=int(score_val),
            pros=pros,
            source_url=str(source_url or ""),
        )

        # 4. Odeslání požadavku přes httpx s timeoutem 10s
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(
                target_webhook,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            # Discord webhooks standardně vracejí 204 No Content nebo 200 OK
            if response.status_code in (200, 204):
                logger.info(
                    f"✅ Discord notifikace úspěšně odeslána pro '{job_title}' ({company}) se skóre {score_val} %."
                )
                return True
            else:
                logger.warning(
                    f"Discord webhook vrátil neočekávaný kód {response.status_code}: {response.text[:200]}"
                )
                return False

    except httpx.TimeoutException:
        logger.warning(f"Timeout ({HTTP_TIMEOUT_SECONDS}s) při odesílání Discord webhooku pro pozici '{job_title}'.")
        return False
    except Exception as e:
        logger.warning(f"Neočekávaná chyba při odesílání Discord webhooku: {e}")
        return False
