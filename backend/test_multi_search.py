import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from scrapers.search import JobSearchScraper

class TestMultiSearchDistribution(unittest.TestCase):
    def test_distribution_exact_sum(self):
        scraper = JobSearchScraper()
        sources = ["jobs.cz", "startupjobs.cz"]
        
        # Test 7 inzerátů mezi 2 zdroje (např. 4 a 3)
        counts = scraper.distribute_counts(7, sources)
        self.assertEqual(sum(counts.values()), 7)
        self.assertEqual(len(counts), 2)
        values = sorted(list(counts.values()))
        self.assertEqual(values, [3, 4])

    def test_distribution_three_sources(self):
        scraper = JobSearchScraper()
        sources = ["jobs.cz", "prace.cz", "startupjobs.cz"]
        
        # Test 10 inzerátů mezi 3 zdroje (např. 4, 3, 3)
        counts = scraper.distribute_counts(10, sources)
        self.assertEqual(sum(counts.values()), 10)
        self.assertEqual(len(counts), 3)
        values = sorted(list(counts.values()))
        self.assertEqual(values, [3, 3, 4])

    def test_distribution_five_sources(self):
        scraper = JobSearchScraper()
        sources = ["jobs.cz", "prace.cz", "startupjobs.cz", "profesia.cz", "volnamista.cz"]
        
        # Test 5 inzerátů mezi 5 zdrojů (každý přesně 1)
        counts = scraper.distribute_counts(5, sources)
        self.assertEqual(sum(counts.values()), 5)
        for val in counts.values():
            self.assertEqual(val, 1)

    def test_distribution_randomness(self):
        scraper = JobSearchScraper()
        sources = ["jobs.cz", "startupjobs.cz"]
        
        # Ověření, že zbytek padne někdy na Jobs.cz a někdy na StartupJobs.cz
        first_source_received_4 = False
        second_source_received_4 = False
        
        for _ in range(50):
            counts = scraper.distribute_counts(7, sources)
            if counts["jobs.cz"] == 4:
                first_source_received_4 = True
            if counts["startupjobs.cz"] == 4:
                second_source_received_4 = True
                
        self.assertTrue(first_source_received_4, "Jobs.cz by měl v některých bězích dostat 4 inzeráty")
        self.assertTrue(second_source_received_4, "StartupJobs.cz by měl v některých bězích dostat 4 inzeráty")


class TestMultiSearchScraper(unittest.IsolatedAsyncioTestCase):
    async def test_search_jobs_multi_sources(self):
        scraper = JobSearchScraper()
        
        # Mockování jednotlivých scraperů
        def mock_single(source, query, count):
            if "startupjobs" in source:
                return [f"https://www.startupjobs.cz/nabidka/{i}" for i in range(count)]
            elif "jobs.cz" in source:
                return [f"https://www.jobs.cz/rpd/{i}" for i in range(count)]
            return []
            
        scraper.search_single_source = AsyncMock(side_effect=mock_single)
        
        results = await scraper.search_jobs(
            query="Python", 
            count=7, 
            sources=["jobs.cz", "startupjobs.cz"]
        )
        
        self.assertEqual(len(results), 7)
        jobs_cz_count = sum(1 for r in results if "www.jobs.cz" in r)
        startup_count = sum(1 for r in results if "startupjobs.cz" in r)
        
        self.assertEqual(jobs_cz_count + startup_count, 7)
        self.assertIn(jobs_cz_count, [3, 4])
        self.assertIn(startup_count, [3, 4])


if __name__ == "__main__":
    unittest.main()
