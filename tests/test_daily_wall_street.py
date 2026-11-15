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

    def test_scheduled_report_is_isolated_and_gated_for_email(self):
        root=Path(__file__).resolve().parents[1]
        scheduled=(root/".github/workflows/daily-wall-street.yml").read_text(encoding="utf-8")
        testing=(root/".github/workflows/test-wall-street.yml").read_text(encoding="utf-8")
        self.assertTrue((root/"scripts/update_wall_street_data.py").is_file())
        self.assertIn("scripts/update_wall_street_data.py", scheduled)
        self.assertIn("scripts/update_wall_street_data.py", testing)
        self.assertIn("github.event_name == 'workflow_dispatch'", scheduled)
        self.assertIn("inputs.preview_only", scheduled)
        self.assertIn("cron: '0 11 * * *'", scheduled)
        self.assertNotIn("RADAR_ENABLE_EMAIL", scheduled)
        self.assertNotIn("python scripts/update_data.py", scheduled)

    @patch.object(radar.smtplib, "SMTP_SSL")
    def test_gmail_transport_uses_tls_and_authenticates_before_sending(self, smtp_cls):
        message=radar.build_email_message("<p>Prueba</p>", "sender@example.com",
                                          "recipient@example.com", {})
        smtp=smtp_cls.return_value.__enter__.return_value
        radar.send_email_via_gmail(message, "sender@example.com", "app-pass-example")
        smtp_cls.assert_called_once()
        self.assertEqual(smtp_cls.call_args.args[:2], ("smtp.gmail.com", 465))
        smtp.login.assert_called_once_with("sender@example.com", "app-pass-example")
        smtp.send_message.assert_called_once_with(message)
        self.assertLess(smtp.mock_calls.index(__import__("unittest.mock", fromlist=["call"]).call.login(
            "sender@example.com", "app-pass-example")),
            smtp.mock_calls.index(__import__("unittest.mock", fromlist=["call"]).call.send_message(message)))

    @patch.object(radar.smtplib, "SMTP_SSL")
    def test_gmail_login_failure_does_not_claim_delivery(self, smtp_cls):
        smtp=smtp_cls.return_value.__enter__.return_value
        smtp.login.side_effect=radar.smtplib.SMTPAuthenticationError(535, b"Authentication failed")
        with self.assertRaises(radar.smtplib.SMTPAuthenticationError):
            radar.send_email_via_gmail("message", "sender@example.com", "bad-password")
        smtp.send_message.assert_not_called()

    def test_email_message_marks_incomplete_coverage_and_has_html(self):
        msg=radar.build_email_message("<html><body>Informe parcial</body></html>",
                                      "sender@example.com", "recipient@example.com", {})
        self.assertIn("edición macroeconómica", msg["Subject"])
        self.assertEqual(msg["To"], "recipient@example.com")
        html_part=msg.get_body(preferencelist=("html",))
        self.assertIsNotNone(html_part)
        self.assertIn("Informe parcial", html_part.get_content())
        self.assertNotIn("enviado", msg.get_body(preferencelist=("plain",)).get_content().lower())

    @patch.object(radar, "official_news", return_value=[])
    def test_partial_macro_edition_when_sec_unavailable(self, _news):
        self.assertEqual(radar.annual_company_coverage({}), 0)
        self.assertIn("macroeconómica", radar.edition_label({}))
        result=radar.render({"series": {}}, {})
        self.assertIn("cobertura empresarial pendiente", result)
        self.assertIn("sin métricas anuales verificadas", result)

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

    def test_tsm_ifrs_20f_keeps_twd_and_skips_short_periods(self):
        facts={"facts":{"ifrs-full":{"Revenue":{"units":{"TWD":[
            {"form":"20-F","fp":"FY","start":"2025-01-01","end":"2025-12-31","filed":"2026-03-10","val":3000000000000},
            {"form":"20-F","fp":"FY","start":"2024-01-01","end":"2024-12-31","filed":"2025-03-10","val":2500000000000},
            {"form":"20-F","fp":"FY","start":"2026-01-01","end":"2026-03-31","filed":"2026-05-01","val":900000000000}
        ]}}}}}
        summary=update_sec.summarize(facts,"TSM")
        annual=summary["metrics"]["revenue"]
        self.assertEqual([x["value"] for x in annual],[3000000000000,2500000000000])
        self.assertTrue(all(x["currency"]=="TWD" for x in annual))
        report=radar.sec_company_html({"companies":{"TSM":summary}})
        self.assertIn("millones TWD",report)
        self.assertNotIn("3,000,000 millones USD",report)

    def test_spcx_quarterly_10q_keeps_three_months_and_skips_ytd(self):
        facts={"facts":{"us-gaap":{"Revenues":{"units":{"USD":[
            {"form":"10-Q","fp":"Q3","start":"2026-07-01","end":"2026-09-30","filed":"2026-11-01","val":10000000000},
            {"form":"10-Q","fp":"Q3","start":"2026-01-01","end":"2026-09-30","filed":"2026-11-01","val":25000000000},
            {"form":"10-Q","fp":"Q2","start":"2026-04-01","end":"2026-06-30","filed":"2026-08-01","val":8000000000}
        ]}}}}}
        summary=update_sec.summarize(facts,"SPCX")
        self.assertEqual([x["value"] for x in summary["quarterly_metrics"]["revenue"]],
                         [10000000000,8000000000])
        output=radar.sec_company_html({"companies":{"SPCX":summary}})
        self.assertIn("Cifras trimestrales",output)
        self.assertIn("10,000 millones USD",output)
        self.assertNotIn("25,000 millones USD",output)

    @patch.object(radar, "official_news", return_value=[])
    def test_sec_renders_numbers_without_inventing_missing_companies(self, _news):
        sec = {"companies": {"NVDA": {"metrics": {
            "revenue": [{"value": 10000000000, "end": "2025-12-31"}],
            "net_income": [{"value": 2000000000, "end": "2025-12-31"}]
        }, "source": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json"}}}
        report = radar.render({"series": {}}, sec)
        self.assertIn("Margen neto calculado: 20.0%", report)
        self.assertIn("NVIDIA", report)
        self.assertIn("sin métricas anuales verificadas", report)

    @patch.object(radar, "official_news", return_value=[])
    def test_scenarios_are_separate_and_diagnosis_has_conclusion(self, _news):
        data={"series":{}}
        report=radar.render(data)
        self.assertIn("<li><strong>Favorable:</strong>",report)
        self.assertIn("<li><strong>Neutral:</strong>",report)
        self.assertIn("<li><strong>Adverso:</strong>",report)
        self.assertIn("Conclusión:",report)
        self.assertIn("Taiwan Semiconductor (TSMC)",report)
        self.assertIn("SpaceX",report)

    def test_company_readable_financial_values(self):
        self.assertEqual(radar.financial_value(12300000000),"12,300 millones USD")

    def test_breadth_parse_validates_three_simple_moving_averages(self):
        import update_breadth
        nasdaq="<p>Latest values 2026-11-13 Above 20DMA 50.50% Above 50DMA 54.46% Above 200DMA 55.56%</p>"
        sp="<p>as of market close, Nov 13, 2026 200d 64%50d 72%20d 67%</p>"
        n=update_breadth.parse_nasdaq(nasdaq)
        s=update_breadth.parse_sp500(sp)
        self.assertEqual(n["ma20"],50.50)
        self.assertEqual(n["ma200"],55.56)
        self.assertEqual(s["ma20"],67)
        self.assertEqual(s["ma50"],72)
        self.assertEqual(s["ma200"],64)
        report=radar.render_stock_breadth({"indices":{
            "sp500":{"source":"https://example.com","date":"2026-11-13",**s},
            "nasdaq100":{"source":"https://example.com","date":"2026-11-13",**n}}})
        self.assertIn("MA20",report)
        self.assertIn("67.0%",report)
        self.assertIn("55.6%",report)
        with self.assertRaises(ValueError):
            update_breadth.parse_nasdaq("No results")

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
        self.assertIn("Impacto potencial:",report)
        self.assertIn("Política monetaria:",report)
        self.assertIn("expectativas previas", report)
        self.assertIn("consenso", radar.news_market_context("BLS CPI inflation").lower())
        self.assertNotIn("las acciones subieron",report)

    def test_news_relevance_prioritizes_macro_topics_without_assigning_market_direction(self):
        self.assertEqual(radar.news_relevance("BLS Consumer Price Index CPI"), 2)
        self.assertEqual(radar.news_relevance("BEA Gross Domestic Product GDP"), 2)
        self.assertEqual(radar.news_relevance("SEC Agency redesigns website"), 0)
        self.assertEqual(radar.news_relevance("Treasury securities market"), 1)
        self.assertNotIn("subieron", radar.news_market_context("BLS CPI inflation"))

    def test_news_category_is_not_inferred_for_unknown_release(self):
        context=radar.news_market_context("SEC: Agency announces new website")
        self.assertIn("titular por sí solo no permite cuantificar",context)
        context=radar.news_market_context("BLS: Consumer Price Index (CPI)")
        self.assertIn("Inflación:",context)

    def test_reference_parsers_validate_gold_and_bitcoin(self):
        from datetime import datetime,timezone
        import update_references
        now=datetime.now(timezone.utc)
        gold=update_references.parse_gold({
            "symbol":"XAU","currency":"USD","price":4123.45,"updatedAt":now.isoformat()})
        self.assertEqual(gold["unit"],"USD/onza troy")
        self.assertEqual(gold["value"],4123.45)
        with self.assertRaises(ValueError):
            update_references.parse_gold({"price":0,"updatedAt":now.isoformat()})
        btc=update_references.parse_btc({
            "symbol":"BTCUSDT","lastPrice":"91500.0","closeTime":int(now.timestamp()*1000),
            "priceChangePercent":"1.5"})
        self.assertEqual(btc["unit"],"USDT/BTC")
        self.assertEqual(btc["change_24h"],1.5)
        with self.assertRaises(ValueError):
            update_references.parse_btc({
                "symbol":"BTCUSD","lastPrice":"91500","closeTime":int(now.timestamp()*1000),
                "priceChangePercent":"1.5"})

    @patch.object(radar, "official_news", return_value=[])
    def test_market_references_include_gold_oil_and_bitcoin_with_units(self, _news):
        from datetime import datetime, timezone
        current=datetime.now(timezone.utc).isoformat()
        refs={"assets":{
            "gold":{"value":4200,"timestamp":current,"unit":"USD/onza troy","source":"https://gold-api.com/"},
            "wti":{"value":72,"date":current[:10],"unit":"USD/barril","source":"https://fred.stlouisfed.org/series/DCOILWTICO"},
            "brent":{"value":76,"date":current[:10],"unit":"USD/barril","source":"https://fred.stlouisfed.org/series/DCOILBRENTEU"},
            "btc":{"value":91000,"timestamp":current,"unit":"USDT/BTC","change_24h":2.5,"source":"https://www.binance.com/en/trade/BTC_USDT"}
        }}
        report=radar.render({"series":{}}, refs=refs)
        self.assertIn("Oro XAU/USD",report)
        self.assertIn("Petróleo WTI",report)
        self.assertIn("Petróleo Brent",report)
        self.assertIn("Bitcoin BTC/USDT",report)
        self.assertIn("variación móvil 24 h: +2.50%",report)

    @patch.object(radar, "official_news", return_value=[
        ("Reserva Federal: Monetary policy statement","https://www.federalreserve.gov/test","15/11/2026 11:00 UTC","Published a statement")])
    def test_news_labels_unknown_factual_summary_honestly(self, _news):
        with patch.object(radar, "summarize_news", return_value={}):
            report=radar.render({"series":{}})
        self.assertIn("Resumen factual en español:",report)
        self.assertIn("No disponible sin análisis de la fuente original",report)
        self.assertIn("Impacto potencial:",report)

    def test_news_parser_can_extract_official_description(self):
        from datetime import datetime,timezone
        from email.utils import format_datetime
        now=datetime.now(timezone.utc)
        raw=("<rss><channel><item><title>New report</title><link>https://www.federalreserve.gov/news</link>"
             "<pubDate>"+format_datetime(now)+"</pubDate>"
             "<description>Report on &lt;b&gt;economic conditions&lt;/b&gt;.</description></item></channel></rss>")
        parsed=radar.parse_official_feed(raw.encode(),"Fed","www.federalreserve.gov",
                                         now=now,with_description=True)
        self.assertEqual(len(parsed),1)
        self.assertIn("economic conditions",parsed[0][4])
        self.assertNotIn("<b>",parsed[0][4])

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

    def test_bea_feed_accepts_only_approved_official_hosts(self):
        from datetime import datetime, timezone
        from email.utils import format_datetime
        now=datetime.now(timezone.utc)
        published=format_datetime(now)
        xml=(f'<rss><channel><item><title>GDP advance estimate</title>'
             f'<link>https://www.bea.gov/news/releases/gdp</link>'
             f'<pubDate>{published}</pubDate></item>'
             f'<item><title>Malicious mirror</title>'
             f'<link>https://www.bea.gov.fake.example/story</link>'
             f'<pubDate>{published}</pubDate></item></channel></rss>')
        results=radar.parse_official_feed(xml.encode(), "BEA",
                ("www.bea.gov", "bea.gov", "apps.bea.gov"), now=now)
        self.assertEqual(len(results), 1)
        self.assertIn("GDP advance estimate", results[0][0])

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
