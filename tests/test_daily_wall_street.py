import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import daily_wall_street as radar

class ReportTests(unittest.TestCase):
    @patch.object(radar, "official_news", return_value=[("Decisión de política", "https://www.federalreserve.gov/newsevents/pressreleases/a.htm", "14/11/2026 11:00 UTC")])
    def test_report_contains_sources_and_derived_metrics(self, _news):
        data={"series":{
            "inflation":{"points":[{"date":"2025-10-01","value":100},{"date":"2026-10-01","value":103}]},
            "payrolls":{"points":[{"date":"2026-09-01","value":150000},{"date":"2026-10-01","value":150200}]}
        }}
        result=radar.render(data)
        self.assertIn("inflación interanual: +3.00%",result)
        self.assertIn("variación mensual: +200,000 empleos",result)
        self.assertIn("Decisión de política",result)
        self.assertIn("No disponible",result)
        self.assertIn("S&P 500",result)

    @patch.object(radar, "official_news", return_value=[])
    def test_missing_news_not_fabricated(self, _news):
        result=radar.render({"series":{}})
        self.assertIn("No se recuperaron comunicados recientes",result)
        self.assertNotIn("mercados subieron",result)

if __name__=="__main__":
    unittest.main()
