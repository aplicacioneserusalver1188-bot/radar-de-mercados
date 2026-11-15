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

    @patch.object(radar, "official_news", return_value=[])
    def test_ppi_is_not_reported_as_consumer_inflation(self, _news):
        data={"series":{"ppi":{"points":[{"date":"2025-10-01","value":200},{"date":"2026-10-01","value":210}]}}}
        result=radar.render(data)
        self.assertIn("variación interanual del índice de materias primas: +5.00%",result)
        self.assertNotIn("inflación interanual: +5.00%",result)

    @patch.object(radar, "official_news", return_value=[])
    def test_payrolls_skip_nonconsecutive_or_reversed_monthly_changes(self, _news):
        data={"series":{"payrolls":{"points":[{"date":"2026-07-01","value":150000},{"date":"2026-10-01","value":150200}]}}}
        self.assertNotIn("variación mensual:",radar.render(data))
        data["series"]["payrolls"]["points"].reverse()
        self.assertNotIn("cambio frente al dato anterior:",radar.render(data))

    @patch.object(radar, "official_news", return_value=[])
    def test_partial_macro_edition_when_sec_unavailable(self, _news):
        self.assertEqual(radar.annual_company_coverage({}), 0)
        self.assertIn("macroeconómica", radar.edition_label({}))
        result=radar.render({"series": {}}, {})
        self.assertIn("cobertura empresarial pendiente", result)
        self.assertIn("sin métricas SEC comparables", result)

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

    def test_index_breadth_is_not_stock_market_breadth(self):
        from datetime import datetime, timedelta, timezone
        today=datetime.now(timezone.utc).date()
        previous=(today-timedelta(days=1)).isoformat()
        latest=today.isoformat()
        data={"series":{
            "sp500":{"points":[{"date":previous,"value":100},{"date":latest,"value":102}]},
            "dow":{"points":[{"date":previous,"value":100},{"date":latest,"value":98}]}
        }}
        output=radar.index_breadth(data)
        self.assertIn("1 al alza, 1 a la baja",output)
        self.assertIn("No equivale a amplitud del mercado",output)

    @patch.object(radar, "official_news", return_value=[])
    def test_stale_index_level_is_historical_without_change(self, _news):
        from datetime import datetime, timedelta, timezone
        old=(datetime.now(timezone.utc).date()-timedelta(days=20)).isoformat()
        older=(datetime.now(timezone.utc).date()-timedelta(days=21)).isoformat()
        data={"series":{"sp500":{"points":[{"date":older,"value":100},{"date":old,"value":105}]}}}
        report=radar.render(data)
        self.assertIn("lectura histórica, no cotización vigente",report)
        self.assertNotIn("variación entre observaciones: +5.00%",report)

    def test_quality_report_counts_current_stale_and_absent(self):
        from datetime import datetime, timedelta, timezone
        today=datetime.now(timezone.utc).date()
        data={"series":{
            "vix":{"frequency":"daily","points":[{"date":today.isoformat(),"value":18.0}]},
            "inflation":{"frequency":"monthly","points":[{"date":(today-timedelta(days=120)).isoformat(),"value":310.0}]}
        }}
        summary=radar.data_quality_summary(data, {"companies":{}}, 2)
        self.assertIn("antiguas: 1",summary)
        self.assertIn("recientes según su frecuencia: 1",summary)
        self.assertIn("Comunicados oficiales recientes con fecha y enlace: 2",summary)
        old_vix={"series":{"vix":{"points":[{"date":(today-timedelta(days=30)).isoformat(),"value":42.0}]}}}
        self.assertIn("Datos insuficientes",radar.market_diagnosis(old_vix))

    def test_future_dates_and_old_indices_are_not_current(self):
        from datetime import datetime, timedelta, timezone
        today=datetime.now(timezone.utc).date()
        future=(today+timedelta(days=2)).isoformat()
        old=(today-timedelta(days=10)).isoformat()
        self.assertFalse(radar.is_recent(future, 7))
        self.assertFalse(radar.is_recent(old, 7))
        self.assertTrue(radar.is_recent(today.isoformat(), 7))
        data={"series":{
            "vix":{"frequency":"daily","points":[{"date":future,"value":30}]},
            "sp500":{"points":[{"date":old,"value":100},{"date":old,"value":101}]}
        }}
        summary=radar.data_quality_summary(data)
        self.assertIn("antiguas: 2",summary)
        self.assertIn("Datos insuficientes",radar.market_diagnosis(data))
        self.assertIn("Sin índices recientes suficientes",radar.index_breadth(data))

    @patch.object(radar, "official_news", return_value=[])
    def test_out_of_order_observations_do_not_create_changes(self, _news):
        from datetime import datetime, timedelta, timezone
        today=datetime.now(timezone.utc).date()
        current=today.isoformat()
        yesterday=(today-timedelta(days=1)).isoformat()
        data={"series":{
            "sp500":{"points":[{"date":current,"value":100},{"date":yesterday,"value":110}]},
            "credit":{"points":[{"date":current,"value":3.0},{"date":yesterday,"value":4.0}]}
        }}
        self.assertIn("Sin índices recientes suficientes",radar.index_breadth(data))
        self.assertIn("Datos insuficientes",radar.market_diagnosis(data))
        report=radar.render(data)
        self.assertNotIn("variación entre observaciones:",report)

    def test_essential_macro_coverage_rejects_stale_series(self):
        from datetime import datetime, timedelta, timezone
        today=datetime.now(timezone.utc).date()
        old_daily=(today-timedelta(days=20)).isoformat()
        recent=today.isoformat()
        monthly=(today-timedelta(days=45)).isoformat()
        data={"series":{
            "inflation":{"points":[{"date":monthly,"value":310}]},
            "payrolls":{"points":[{"date":monthly,"value":150000}]},
            "treasury10y":{"points":[{"date":old_daily,"value":4.2}]},
            "vix":{"points":[{"date":recent,"value":20}]}
        }}
        self.assertEqual(radar.essential_macro_coverage(data),3)
        data["series"]["vix"]["points"][0]["date"]=old_daily
        self.assertEqual(radar.essential_macro_coverage(data),2)

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

    @patch.object(radar, "official_news", return_value=[
        ("Reserva Federal: FOMC monetary policy decision",
         "https://www.federalreserve.gov/newsevents/pressreleases/monetary.htm",
         "15/11/2026 10:00 UTC")])
    def test_news_provides_conditional_context_not_unverified_market_outcome(self, _news):
        report=radar.render({"series":{}})
        self.assertIn("Relevancia potencial:",report)
        self.assertIn("Política monetaria:",report)
        self.assertIn("consenso",report.lower() if "consenso" in report.lower() else radar.news_market_context("BLS CPI inflation").lower())
        self.assertNotIn("las acciones subieron",report)

    def test_news_category_is_not_inferred_for_unknown_release(self):
        context=radar.news_market_context("SEC: Agency announces new website")
        self.assertIn("titular por sí solo no permite cuantificar",context)
        context=radar.news_market_context("BLS: Consumer Price Index (CPI)")
        self.assertIn("Inflación:",context)

    def test_official_news_parser_accepts_rss_and_atom_without_unsafe_links(self):
        from datetime import datetime, timezone
        from email.utils import format_datetime
        now=datetime.now(timezone.utc)
        when=format_datetime(now)
        rss=(f'<rss><channel><item><title>Comunicado monetario</title>'
             f'<link>https://www.federalreserve.gov/newsevents/pressreleases/example.htm</link>'
             f'<pubDate>{when}</pubDate></item><item>'
             f'<title>Enlace malicioso</title><link>https://www.federalreserve.gov.evil.example/x</link>'
             f'<pubDate>{when}</pubDate></item></channel></rss>')
        results=radar.parse_official_feed(rss.encode(), "Reserva Federal", "www.federalreserve.gov", now=now)
        self.assertEqual(len(results),1)
        self.assertIn("Comunicado monetario", results[0][0])
        atom=('''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
            <title>Actualización oficial</title>
            <link rel="alternate" href="https://www.federalreserve.gov/newsevents/example"/>
            <published>''' + now.isoformat() + '''</published></entry></feed>''')
        results=radar.parse_official_feed(atom.encode(), "Reserva Federal", "www.federalreserve.gov", now=now)
        self.assertEqual(len(results),1)
        self.assertIn("Actualización oficial",results[0][0])

    def test_official_news_parser_rejects_future_and_unverified_dates(self):
        from datetime import datetime, timezone, timedelta
        from email.utils import format_datetime
        now=datetime.now(timezone.utc)
        future=format_datetime(now+timedelta(days=2))
        rss=(f'<rss><channel><item><title>Futuro</title>'
             f'<link>https://www.federalreserve.gov/newsevents/example</link>'
             f'<pubDate>{future}</pubDate></item>'
             f'<item><title>Fecha faltante</title>'
             f'<link>https://www.federalreserve.gov/newsevents/other</link>'
             f'</item></channel></rss>')
        self.assertEqual(radar.parse_official_feed(rss.encode(), "Fed", "www.federalreserve.gov", now=now), [])

    @patch.object(radar, "official_news", return_value=[])
    def test_missing_news_not_fabricated(self, _news):
        result=radar.render({"series":{}})
        self.assertIn("No se recuperaron comunicados verificables recientes",result)
        self.assertNotIn("mercados subieron",result)

if __name__=="__main__":
    unittest.main()
