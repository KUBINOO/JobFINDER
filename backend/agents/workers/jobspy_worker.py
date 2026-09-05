import asyncio
from datetime import datetime, date, time, timezone
import logging
from typing import List, Optional, Dict, Any
import pandas as pd

from schemas_v2 import RawJobPayload
from agents.relevance import calculate_relevance
from .base import BaseRemoteWorker

logger = logging.getLogger(__name__)

# Site normalization map for source_portal tag
SITE_NAME_MAP = {
    "linkedin": "LinkedIn",
    "indeed": "Indeed",
    "glassdoor": "Glassdoor",
    "zip_recruiter": "ZipRecruiter",
    "google": "Google",
    "bayt": "Bayt",
    "naukri": "Naukri",
    "bdjobs": "BDJobs",
}

CZ_LOCATION_INDICATORS = {
    "czech", "czechia", "cesk", "česk", "praha", "prah", "praze", "praz", "prague", 
    "brno", "brn", "ostrav", "plzen", "plzeň", "plzn", "olomouc", "liberec"
}

# Ensure JobSpy Country parser does not crash on unmapped country strings from LinkedIn metadata
try:
    import jobspy
    _orig_country_from_string = jobspy.Country.from_string

    def _safe_country_from_string(cls, country_str: str):
        try:
            return _orig_country_from_string(country_str)
        except Exception:
            return jobspy.Country.WORLDWIDE

    jobspy.Country.from_string = classmethod(_safe_country_from_string)
except Exception:
    pass


def _clean_str(val: Any, default: str = "") -> str:
    """Safely converts Pandas values, collections or strings, eliminating NaN/None."""
    if val is None:
        return default
    if isinstance(val, (list, tuple, set)):
        return ", ".join(str(x) for x in val if x is not None and str(x).strip())
    if isinstance(val, dict):
        return default
    try:
        if pd.isna(val):
            return default
    except Exception:
        pass
    s = str(val).strip()
    return default if s.lower() == "nan" else s


def _safe_float(val: Any) -> Optional[float]:
    """Safely converts string, float, int to float, returning None on failure or NaN."""
    if val is None:
        return None
    if isinstance(val, (list, tuple, set, dict)):
        return None
    try:
        if isinstance(val, (int, float)):
            if pd.isna(val):
                return None
            return float(val)
        cleaned = str(val).replace(",", "").replace("$", "").replace("€", "").strip()
        return float(cleaned)
    except Exception:
        return None


def _format_salary(row: pd.Series) -> Optional[str]:
    """Formats salary bounds from JobSpy DataFrame row."""
    min_amt = _safe_float(row.get("min_amount"))
    max_amt = _safe_float(row.get("max_amount"))
    currency = _clean_str(row.get("currency"), "USD")
    interval = _clean_str(row.get("interval"), "year")

    has_min = min_amt is not None and min_amt > 0
    has_max = max_amt is not None and max_amt > 0

    if has_min and has_max:
        return f"{int(min_amt)} - {int(max_amt)} {currency}/{interval}"
    elif has_min:
        return f"{int(min_amt)}+ {currency}/{interval}"
    elif has_max:
        return f"Up to {int(max_amt)} {currency}/{interval}"
    return None


def _parse_published_at(val: Any) -> Optional[datetime]:
    """Safely normalizes various datetime representations into UTC datetime."""
    if val is None:
        return None
    if isinstance(val, (list, tuple, set, dict)):
        return None
    try:
        if pd.isna(val):
            return None
    except Exception:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, date):
        return datetime.combine(val, time.min, tzinfo=timezone.utc)
    try:
        dt = pd.to_datetime(val)
        if pd.isna(dt):
            return None
        pydt = dt.to_pydatetime()
        return pydt if pydt.tzinfo else pydt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


class JobSpyWorker(BaseRemoteWorker):
    """
    Tier 1 Multi-Platform Worker leveraging python-jobspy.
    Scrapes LinkedIn, Indeed, and Glassdoor concurrently in a non-blocking thread.
    Applies adaptive location handling, graceful degradation, and semantic relevance filtering.
    """

    def __init__(self, timeout: float = 25.0):
        super().__init__(name="JobSpy", timeout=timeout)
        self.default_sites = ["linkedin", "indeed", "glassdoor"]

    def _determine_location_parameters(
        self, 
        query: str, 
        market: str, 
        explicit_location: Optional[str]
    ) -> Dict[str, Any]:
        """
        Determines location, country_indeed, and is_remote parameters based on
        the target market, query text, and explicit location overrides.
        """
        q_lower = query.lower()
        m_lower = (market or "global").lower()

        # If location is explicitly provided, use it
        if explicit_location:
            loc_lower = explicit_location.lower()
            is_cz = any(ind in loc_lower for ind in CZ_LOCATION_INDICATORS)
            return {
                "location": explicit_location,
                "country_indeed": "czech republic" if is_cz else "usa",
                "is_remote": False
            }

        # Check if query contains Czech indicators
        query_has_cz = any(ind in q_lower for ind in CZ_LOCATION_INDICATORS)

        if m_lower == "cz" or query_has_cz:
            if any(p in q_lower for p in ("praha", "prah", "praze", "prague")):
                loc = "Prague, Czechia"
            elif any(b in q_lower for b in ("brno", "brn")):
                loc = "Brno, Czechia"
            elif "ostrav" in q_lower:
                loc = "Ostrava, Czechia"
            elif any(pl in q_lower for pl in ("plzen", "plzeň", "plzn")):
                loc = "Pilsen, Czechia"
            else:
                loc = "Czech Republic"

            return {
                "location": loc,
                "country_indeed": "czech republic",
                "is_remote": False
            }
        elif m_lower == "hybrid":
            return {
                "location": "Czech Republic",
                "country_indeed": "czech republic",
                "is_remote": True
            }
        else:
            # Global remote search
            return {
                "location": None,
                "country_indeed": "usa",
                "is_remote": True
            }

    def _execute_jobspy_scrape(
        self,
        sites: List[str],
        search_term: str,
        location: Optional[str],
        country_indeed: str,
        is_remote: bool,
        job_type: Optional[str],
        results_wanted: int
    ) -> pd.DataFrame:
        """
        Synchronous wrapper calling jobspy.scrape_jobs.
        Executed inside asyncio.to_thread to prevent event loop blocking.
        """
        import jobspy

        if not sites:
            return pd.DataFrame()

        logger.info(
            f"JobSpy scrape started: sites={sites}, search_term='{search_term}', "
            f"location='{location}', country_indeed='{country_indeed}', "
            f"is_remote={is_remote}, job_type={job_type}, results_wanted={results_wanted}"
        )

        return jobspy.scrape_jobs(
            site_name=sites,
            search_term=search_term if search_term else None,
            location=location,
            country_indeed=country_indeed,
            is_remote=is_remote,
            job_type=job_type,
            results_wanted=results_wanted,
            linkedin_fetch_description=False,
            verbose=0
        )

    async def fetch_jobs(
        self,
        query: str = "",
        limit: int = 15,
        part_time_only: bool = False,
        market: str = "global",
        location: Optional[str] = None,
        site_names: Optional[List[str]] = None,
        **kwargs
    ) -> List[RawJobPayload]:
        """
        Asynchronously fetches and normalizes job listings from LinkedIn, Indeed, and Glassdoor.
        Guarantees non-blocking execution and graceful degradation without raising exceptions.
        """
        sites_to_query = list(site_names or self.default_sites)
        loc_params = self._determine_location_parameters(query, market, location)
        
        # Dynamically exclude Glassdoor if unsupported by JobSpy for the selected country
        try:
            import jobspy
            country_enum = jobspy.Country.from_string(loc_params["country_indeed"])
            if len(country_enum.value) < 3 and "glassdoor" in [s.lower() for s in sites_to_query]:
                sites_to_query = [s for s in sites_to_query if s.lower() != "glassdoor"]
        except Exception:
            pass

        job_type = "parttime" if part_time_only else None
        results_wanted = max(limit * 2, 10)

        results: List[RawJobPayload] = []

        try:
            # Execute blocking JobSpy scraping in a worker thread with SLA timeout
            df = await asyncio.wait_for(
                asyncio.to_thread(
                    self._execute_jobspy_scrape,
                    sites=sites_to_query,
                    search_term=query.strip(),
                    location=loc_params["location"],
                    country_indeed=loc_params["country_indeed"],
                    is_remote=loc_params["is_remote"],
                    job_type=job_type,
                    results_wanted=results_wanted
                ),
                timeout=self.timeout
            )

            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                logger.info("JobSpy scraping completed with 0 results.")
                return []

            logger.info(f"JobSpy scraping returned raw DataFrame with {len(df)} rows.")

            for _, row in df.iterrows():
                try:
                    site_raw = _clean_str(row.get("site"), "JobSpy")
                    site_display = SITE_NAME_MAP.get(site_raw.lower(), site_raw.capitalize())
                    source_portal = f"JobSpy ({site_display})"

                    job_url = _clean_str(row.get("job_url"))
                    job_url_direct = _clean_str(row.get("job_url_direct"))
                    final_url = job_url or job_url_direct
                    if not final_url:
                        continue

                    title = _clean_str(row.get("title"))
                    if not title:
                        continue

                    company = _clean_str(row.get("company"), "Unknown Company")
                    description = _clean_str(row.get("description"))
                    job_location = _clean_str(row.get("location"))
                    if not job_location and loc_params["is_remote"]:
                        job_location = "Remote"

                    # Extract and clean tags
                    raw_tags: List[str] = [site_display.lower()]
                    if loc_params["is_remote"]:
                        raw_tags.append("remote")

                    row_job_type = _clean_str(row.get("job_type"))
                    if row_job_type:
                        raw_tags.extend([t.strip().lower() for t in row_job_type.split(",") if t.strip()])

                    row_skills = _clean_str(row.get("skills"))
                    if row_skills:
                        raw_tags.extend([s.strip().lower() for s in row_skills.split(",") if s.strip()])

                    # Deduplicate tags
                    seen_tags = set()
                    deduped_tags = []
                    for t in raw_tags:
                        if t not in seen_tags:
                            seen_tags.add(t)
                            deduped_tags.append(t)

                    # 1. Part-time check if required
                    if part_time_only:
                        is_pt = (
                            any("part" in t for t in deduped_tags) or
                            "part-time" in title.lower() or
                            "part time" in title.lower() or
                            "part-time" in description.lower() or
                            "contract" in description.lower()
                        )
                        if not is_pt:
                            continue

                    # 2. Semantic relevance filtering (threshold >= 0.45)
                    if query.strip():
                        rel_score = calculate_relevance(
                            query=query,
                            title=title,
                            tags=deduped_tags,
                            snippet=description[:500]
                        )
                        if rel_score < 0.45:
                            continue

                    salary_str = _format_salary(row)
                    pub_date = _parse_published_at(row.get("date_posted"))

                    results.append(
                        RawJobPayload(
                            source_portal=source_portal,
                            source_url=final_url,
                            title=title,
                            company_name=company,
                            description=description,
                            raw_location=job_location or None,
                            raw_tags=deduped_tags,
                            raw_salary=salary_str,
                            apply_url=job_url_direct or final_url,
                            published_at=pub_date
                        )
                    )

                    if len(results) >= limit:
                        break
                except Exception as row_exc:
                    logger.warning(f"Error parsing JobSpy row, skipping: {row_exc}")
                    continue

        except asyncio.TimeoutError:
            logger.warning(
                f"JobSpyWorker timed out after {self.timeout}s for query='{query}', "
                f"market='{market}'. Returning {len(results)} collected jobs."
            )
            return results
        except Exception as exc:
            logger.warning(
                f"JobSpyWorker encountered an error during execution ({type(exc).__name__}: {exc}). "
                f"Returning {len(results)} collected jobs gracefully."
            )
            return results

        logger.info(f"JobSpyWorker successfully retrieved and normalized {len(results)} positions.")
        return results
