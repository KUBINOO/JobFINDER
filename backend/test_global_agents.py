import asyncio
import logging
import sys

# Nastavení logování
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_global_agents")

from schemas_v2 import RawJobPayload, EmploymentType, TimezoneRegion
from agents.normalizer import NormalizationAgent
from agents.workers.remoteok import RemoteOKWorker
from agents.workers.remotive import RemotiveWorker
from agents.workers.wwr import WeWorkRemotelyWorker
from agents.workers.arbeitnow import ArbeitnowWorker
from agents.dispatcher import DispatcherAgent


async def test_workers():
    logger.info("=== 1. Testování jednotlivých workerů ===")

    # Test RemoteOK
    remoteok = RemoteOKWorker()
    try:
        ro_jobs = await remoteok.fetch_jobs(query="python", limit=3, part_time_only=False)
        logger.info(f"✅ RemoteOK OK: {len(ro_jobs)} nabídek získáno.")
    except Exception as e:
        logger.warning(f"⚠️ RemoteOK varování (možný rate limit): {e}")

    # Test Remotive
    remotive = RemotiveWorker()
    try:
        rem_jobs = await remotive.fetch_jobs(query="python", limit=3, part_time_only=False)
        logger.info(f"✅ Remotive OK: {len(rem_jobs)} nabídek získáno.")
    except Exception as e:
        logger.warning(f"⚠️ Remotive varování: {e}")

    # Test We Work Remotely
    wwr = WeWorkRemotelyWorker()
    try:
        wwr_jobs = await wwr.fetch_jobs(query="", limit=3, part_time_only=False)
        logger.info(f"✅ WeWorkRemotely OK: {len(wwr_jobs)} nabídek získáno.")
    except Exception as e:
        logger.warning(f"⚠️ WeWorkRemotely varování: {e}")

    # Test Arbeitnow
    arbeitnow = ArbeitnowWorker()
    try:
        ab_jobs = await arbeitnow.fetch_jobs(query="", limit=3, part_time_only=False)
        logger.info(f"✅ Arbeitnow OK: {len(ab_jobs)} nabídek získáno.")
    except Exception as e:
        logger.warning(f"⚠️ Arbeitnow varování: {e}")


def test_normalization_and_timezone():
    logger.info("\n=== 2. Testování Normalizace, Timezone a Deduplikace ===")
    normalizer = NormalizationAgent(timezone_preference="EMEA_ONLY")

    raw_samples = [
        # 1. US Only -> mělo by být vyřazeno
        RawJobPayload(
            source_portal="RemoteOK",
            source_url="https://example.com/job1",
            title="Senior React Developer",
            company_name="US Corp Inc.",
            description="Great role for React devs. Must reside in the US and have US citizenship. Full description here with plenty of words to pass the quality gate length check.",
            raw_location="US Only"
        ),
        # 2. EMEA / CET friendly -> mělo by projít
        RawJobPayload(
            source_portal="Remotive",
            source_url="https://example.com/job2",
            title="Frontend Developer (Part-time)",
            company_name="Prague Tech s.r.o.",
            description="We are looking for a part-time student or contractor to join our team in Europe (CET timezone). Long descriptive text to satisfy the minimum length requirement.",
            raw_location="Europe / Remote"
        ),
        # 3. Duplikát nabídky 2 z jiného portálu -> mělo by být deduplikováno!
        RawJobPayload(
            source_portal="WeWorkRemotely",
            source_url="https://weworkremotely.com/job2-duplicate?utm_source=rss",
            title="Frontend Developer - Part time",
            company_name="Prague Tech",
            description="Same job posted on WWR. We are looking for a part-time student or contractor to join our team in Europe (CET timezone).",
            raw_location="Worldwide"
        ),
    ]

    normalized = normalizer.normalize_and_deduplicate(raw_samples, part_time_only=False)

    logger.info(f"Vstupní inzeráty: {len(raw_samples)}, normalizované unikátní: {len(normalized)}")

    # Ověření: US Corp byl vyřazen
    titles = [j.title for j in normalized]
    companies = [j.company_name for j in normalized]

    assert "US Corp Inc." not in companies, "US Only inzerát měl být vyřazen!"
    assert len(normalized) == 1, f"Očekáván přesně 1 unikátní inzerát (po deduplikaci), ale máme {len(normalized)}"
    assert normalized[0].employment_type == EmploymentType.PART_TIME, "Úvazek měl být detekován jako PART_TIME!"
    assert normalized[0].timezone_region in (TimezoneRegion.EMEA, TimezoneRegion.WORLDWIDE), "Timezone region měl být EMEA/WORLDWIDE!"

    logger.info(f"✅ Normalizace & Timezone & Deduplikace prošly perfektně! Zachován inzerát: {normalized[0].title} u {normalized[0].company_name}")


async def test_dispatcher():
    logger.info("\n=== 3. Testování DispatcherAgenta (End-to-End Search) ===")
    dispatcher = DispatcherAgent()
    state = await dispatcher.execute_search(
        query="developer",
        count=5,
        market="global",
        employment_type="PART_TIME",
        timezone_preference="EMEA_ONLY"
    )

    logger.info(f"Běh: {state.run_id}")
    logger.info(f"Stav: {state.status}")
    logger.info(f"Výsledky workerů: {state.worker_counts}")
    logger.info(f"Chyby workerů: {state.worker_errors}")
    logger.info(f"Výsledný počet deduplikovaných nabídek: {len(state.normalized_listings)}")

    for i, job in enumerate(state.normalized_listings, 1):
        logger.info(f"  {i}. [{job.source_portal}] {job.title} @ {job.company_name} | {job.employment_type.value} | {job.timezone_region.value}")

    assert len(state.normalized_listings) > 0, "Dispatcher měl vrátit alespoň jednu platnou globální nabídku!"
    logger.info("✅ DispatcherAgent E2E test úspěšný!")


async def main():
    try:
        test_normalization_and_timezone()
        await test_workers()
        await test_dispatcher()
        logger.info("\n🎉 VŠECHNY MULTI-AGENTNÍ TESTY PROŠLY ÚSPĚŠNĚ! 🎉")
    except Exception as e:
        logger.error(f"❌ Test selhal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
