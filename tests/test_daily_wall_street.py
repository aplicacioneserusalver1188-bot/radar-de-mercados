import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import daily_wall_street as radar
import update_sec

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
        self.assertIn("S&amp;P 500",result)

    def test_sec_annual_values_excludes_quarter_and_compares_fiscal_years(self):
        facts = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            {"form": "10-Q", "fp": "Q1", "start": "2026-01-01", "end": "2026-03-31", "filed": "2026-04-20", "val": 5},
            {"form": "10-K", "fp": "FY", "start": "2024-01-01", "end": "2024-12-31", "filed": "2025-02-01", "val": 80},
            {"form": "10-K", "fp": "FY", "start": "2025-01-01", "end": "2025-12-31", "filed": "2026-02-01", "val": 100}
        ]}}}}}
        values = update_sec.annual_values(facts, ("Revenues",))
        self.assertEqual([r["value"] for r in values], [100, 80])
        summary = update_sec.summarize(facts, "NVDA")
        self.assertEqual(summary["metrics"]["revenue"][0]["value"], 100)

    @patch.object(radar, "official_news", return_value=[])
    def test_sec_renders_numbers_without_inventing_missing_companies(self, _news):
        sec = {"companies": {"NVDA": {"metrics": {
            "revenue": [{"value": 10000000000, "end": "2025-12-31"}],
            "net_income": [{"value": 2000000000, "end": "2025-12-31"}]
        }, "source": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json"}}}
        report = radar.render({"series": {}}, sec)
        self.assertIn("Margen neto calculado: 20.0%", report)
        self.assertIn("NVIDIA", report)
        self.assertIn("sin métricas SEC comparables", report)

    def test_fred_source_is_linked_and_freshness_depends_on_frequency(self):
        self.assertEqual(radar.freshness_limit("daily"), 7)
        self.assertEqual(radar.freshness_limit("monthly"), 75)
        self.assertEqual(radar.freshness_limit("quarterly"), 155)
        label = radar.fred_link({"source_url": "https://fred.stlouisfed.org/series/DGS10"}, "Tesoro 10 años")
        self.assertIn("https://fred.stlouisfed.org/series/DGS10", label)
        unsafe = radar.fred_link({"source_url": "javascript:alert(1)"}, "Tesoro")
        self.assertNotIn("<a", unsafe)

    def test_quantitative_diagnosis_only_uses_observed_values(self):
        result = radar.market_diagnosis({"series": {
            "vix": {"points": [{"value": 28.2, "date": "2026-11-13"}]},
            "credit": {"points": [{"value": 3.7, "date": "2026-11-12"},
                                    {"value": 3.9, "date": "2026-11-13"}]},
            "treasury2y": {"points": [{"value": 4.2, "date": "2026-11-13"}]},
            "treasury10y": {"points": [{"value": 4.0, "date": "2026-11-13"}]}
        }})
        self.assertIn("28.20", result)
        self.assertIn("aumenta la prima de riesgo", result)
        self.assertIn("curva invertida", result)
        self.assertNotIn("probabilidad", result)

    @patch.object(radar, "official_news", return_value=[])
    def test_missing_news_not_fabricated(self, _news):
        result=radar.render({"series":{}})
        self.assertIn("No se recuperaron comunicados verificables recientes",result)
        self.assertNotIn("mercados subieron",result)

if __name__=="__main__":
    unittest.main()
