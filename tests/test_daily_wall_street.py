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
        self.assertIn("IPC: precios al consumidor",result)
        self.assertIn("+3.00% interanual",result)
        self.assertIn("+200,000 puestos frente al mes anterior",result)
        self.assertIn("Decisión de política",result)
        self.assertIn("No disponible",result)
        self.assertIn("S&amp;P 500",result)

    @patch.object(radar, "official_news", return_value=[])
    def test_ppi_is_not_reported_as_consumer_inflation(self, _news):
        data={"series":{"ppi":{"points":[{"date":"2025-10-01","value":200},{"date":"2026-10-01","value":210}]}}}
        result=radar.render(data)
        self.assertIn("PPI de materias primas cambió +5.00% interanual",result)
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
        self.assertIn("sin datos SEC comparables verificados", result)

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

    def test_sec_selects_most_recent_tag_instead_of_2022_for_nvda(self):
        facts={"facts":{"us-gaap":{
            "RevenueFromContractWithCustomerExcludingAssessedTax":{"units":{"USD":[
                {"form":"10-K","fp":"FY","start":"2021-01-31","end":"2022-01-30",
                 "filed":"2022-03-01","val":26914000000}]}},
            "Revenues":{"units":{"USD":[
                {"form":"10-K","fp":"FY","start":"2025-01-27","end":"2026-01-25",
                 "filed":"2026-03-01","val":215938000000},
                {"form":"10-K","fp":"FY","start":"2024-01-29","end":"2025-01-26",
                 "filed":"2025-03-01","val":130000000000}]}}
        }}}
        vals=update_sec.annual_values(facts,update_sec.TAGS["revenue"])
        self.assertEqual(vals[0]["end"],"2026-01-25")
        self.assertEqual(vals[0]["value"],215938000000)
        self.assertNotIn("2022-01-30",[x["end"] for x in vals])
        company=update_sec.summarize(facts,"NVDA")
        self.assertEqual(company["metrics"]["revenue"][0]["value"],215938000000)

    def test_financial_analysis_omits_metrics_from_different_years(self):
        metrics={
            "revenue":[{"end":"2022-01-30","value":26914000000}],
            "net_income":[{"end":"2026-01-25","value":120067000000}],
            "operating_cash":[{"end":"2026-01-25","value":102718000000}],
            "capital_expenditure":[{"end":"2012-01-29","value":139000000}],
        }
        html=radar.company_metric_rows(metrics)
        self.assertIn("2026-01-25","".join(html))
        self.assertNotIn("26,914 millones","".join(html))
        self.assertNotIn("139 millones","".join(html))
        self.assertNotIn("Margen neto","".join(html))

    def test_gold_uses_explicit_futures_proxy_when_spot_unavailable(self):
        import update_price_history
        from datetime import datetime,timedelta,timezone
        today=datetime.now(timezone.utc).date()
        rows=[{"date":(today-timedelta(days=30-i)).isoformat(),"close":3800+i}
              for i in range(30)]
        with patch.object(update_price_history,"stooq",side_effect=ValueError("blocked")), \
             patch.object(update_price_history,"yahoo_stock",return_value=rows) as yahoo, \
             patch.object(update_price_history,"fred_series",return_value=[{"date":r["date"],"value":r["close"]} for r in rows]), \
             patch.object(update_price_history,"btc_history",return_value=rows):
            result=update_price_history.collect()
        self.assertEqual(yahoo.call_args_list[0].args[0],"GC=F")
        gold=result["assets"]["gold"]
        self.assertIn("FUTUROS",gold["proxy"])
        self.assertIn("COMEX",gold["label"])
        snippet=radar.chart_fragment("gold",{"assets":{"gold":gold}},{"gold":"/tmp/gold.png"})
        self.assertIn("FUTUROS COMEX",snippet)

    def test_low_relevance_banking_fees_not_market_catalyst(self):
        self.assertEqual(radar.news_relevance(
            "Fed Board announces pricing for payment services provided to banks"),0)
        self.assertEqual(radar.news_relevance("Fed FOMC interest rate decision"),2)

    def test_market_chart_conclusion_uses_historical_closes(self):
        import render_charts
        from datetime import datetime,timedelta,timezone
        end=datetime.now(timezone.utc).date()
        points=[{"date":(end-timedelta(days=(239-i))).isoformat(),"close":100+i}
                for i in range(240)]
        measured=render_charts.metrics(points)
        self.assertIn("ma200",measured)
        self.assertIn("ma50",measured)
        self.assertIn("corto y mediano plazo favorable",render_charts.interpretation(measured))
        html=radar.chart_fragment("gold",{"assets":{"gold":{
            "unit":"USD/onza troy","source":"https://stooq.com/q/?s=xauusd",
            "points":points}}},{"gold":"/tmp/example.png"})
        self.assertIn("cid:radar-gold",html)
        self.assertIn("Qué muestra:",html)

    def test_news_official_body_extraction_no_duplicate_title(self):
        import news_story
        page="<html><main><p>Economy report details a change in inflation expectations and monetary policy assumptions for the coming fiscal year.</p><p>Officials also described changes in bond yields and lending conditions for banks after the announcement.</p></main></html>"
        item=news_story.official_details("https://www.federalreserve.gov/test",
                                         "Official announcement",request_fn=lambda u:page)
        self.assertIn("inflation expectations",item)
        self.assertIn("bond yields",item)
        self.assertEqual(news_story.official_details("https://attacker.example/test",request_fn=lambda u:page),"")

    @patch.object(radar,"official_news",return_value=[])
    def test_company_weekly_and_daily_changes_with_news(self):
        from datetime import datetime,timedelta,timezone
        import company_pulse
        today=datetime.now(timezone.utc).date()
        points=[{"date":(today-timedelta(days=5-i)).isoformat(),
                 "close":100+2*i} for i in range(6)]
        p=company_pulse.momentum(points)
        self.assertAlmostEqual(p["daily"],100*(110/108-1))
        self.assertAlmostEqual(p["weekly"],10)
        self.assertIn("Última sesión",company_pulse.reading(p))
        self.assertIn("Continuación favorable",company_pulse.scenarios(p))
        news=[{"title":"Company shares rose after an announcement",
               "url":"https://news.google.com/rss/articles/example",
               "source":"Financial Times","date":today.isoformat()}]
        text=company_pulse.company_news_html(news,translator=lambda x:"Empresa anuncia novedades")
        self.assertIn("Empresa anuncia novedades",text)
        self.assertIn("no hechos confirmados",text)
        self.assertNotIn("causó",text)

    @patch.object(radar,"official_news",return_value=[])
    def test_company_cards_focus_on_last_session_and_week(self,_news):
        from datetime import datetime,timedelta,timezone
        today=datetime.now(timezone.utc).date()
        points=[{"date":(today-timedelta(days=220-i)).isoformat(),
                 "close":100+i} for i in range(221)]
        assets={"NVDA":{"points":points,"source":"https://stooq.com/q/?s=nvda.us","unit":"USD/acción"}}
        report=radar.render({"series":{}},history={"assets":assets},chart_keys={"NVDA":"/tmp/nvda.png"},
                            company_news={"companies":{}})
        self.assertIn("Última sesión:",report)
        self.assertIn("Últimas 5 sesiones:",report)
        self.assertIn("Qué está haciendo la acción:",report)
        self.assertIn("Escenario condicional:",report)
        self.assertIn("Últimas 5 sesiones",report)
        self.assertNotIn("Resultados financieros (contexto secundario)",report)

    def test_company_news_feed_requires_recent_date_and_link(self):
        import update_company_news
        from datetime import datetime,timezone
        now=datetime(2026,11,15,tzinfo=timezone.utc)
        rss=b"""<rss><channel><item><title>Nvidia releases new GPU</title>
        <link>https://news.google.com/rss/articles/yes</link>
        <pubDate>Sat, 14 Nov 2026 12:00:00 GMT</pubDate><source>Reuters</source>
        </item><item><title>Old company release</title>
        <link>https://news.google.com/rss/articles/old</link>
        <pubDate>Thu, 29 Oct 2026 12:00:00 GMT</pubDate></item>
        <item><title>Unsafe link</title><link>https://attacker.example/bad</link>
        <pubDate>Sat, 14 Nov 2026 12:00:00 GMT</pubDate></item></channel></rss>"""
        rows=update_company_news.parse_feed(rss,now)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["source"],"Reuters")

    def test_four_index_graphs_and_company_graphs_in_report(self,_news):
        from datetime import datetime,timedelta,timezone
        end=datetime.now(timezone.utc).date()
        points=[{"date":(end-timedelta(days=240-i)).isoformat(),"close":4000+i}
                for i in range(241)]
        source="https://fred.stlouisfed.org/series/SP500"
        history={"assets":{key:{"points":points,"unit":"puntos",
                                 "source":source,"label":key}
                           for key in ("sp500","nasdaq","dow","russell","NVDA")}}
        keys={key:"/tmp/"+key+".png" for key in history["assets"]}
        report=radar.render({"series":{}},history=history,chart_keys=keys)
        for key in ("sp500","nasdaq","dow","russell","nvda"):
            self.assertIn("cid:radar-"+key,report)
        self.assertIn("Qué muestra:",report)
        self.assertIn("Nasdaq Composite",report)
        self.assertNotIn("Última lectura y cambio",report)

    def test_macro_stories_replace_dictionary_table(self):
        from datetime import datetime,timezone
        import macro_story
        now=datetime(2026,11,15,tzinfo=timezone.utc)
        data={"series":{
            "pce":{"source_url":"https://fred.stlouisfed.org/series/PCEPI","points":[
                {"date":"2025-09-01","value":100},
                {"date":"2026-09-01","value":103.65}]},
            "corepce":{"points":[{"date":"2025-09-01","value":100},
                                 {"date":"2026-09-01","value":103.12}]},
            "unemployment":{"points":[{"date":"2026-09-01","value":3.9},
                                        {"date":"2026-10-01","value":4.1}]},
        }}
        report=macro_story.macro_story(data,now=now)
        self.assertIn("PCE general 3.65%",report)
        self.assertIn("PCE subyacente 3.12%",report)
        self.assertIn("Inflación por encima del 2% y desempleo en aumento",report)
        self.assertIn("Por qué importa",report)
        self.assertNotIn("nivel del índice",report)

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
        self.assertIn("Resultados trimestrales verificados",output)
        self.assertIn("10,000 millones USD",output)
        self.assertNotIn("25,000 millones USD",output)

    @patch.object(radar, "official_news", return_value=[])
    def test_sec_renders_numbers_without_inventing_missing_companies(self, _news):
        sec = {"companies": {"NVDA": {"metrics": {
            "revenue": [{"value": 10000000000, "end": "2025-12-31"}],
            "net_income": [{"value": 2000000000, "end": "2025-12-31"}]
        }, "source": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json"}}}
        report = radar.render({"series": {}}, sec)
        self.assertIn("Margen neto: 20.0%", report)
        self.assertIn("NVIDIA", report)
        self.assertIn("sin datos SEC comparables verificados", report)

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
        self.assertIn("presenta observación fuera de vigencia",report)
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
        self.assertIn("Por qué importa:",report)
        self.assertIn("tipos de interés",report)
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
        self.assertIn("no está demostrada",context)
        context=radar.news_market_context("BLS: Consumer Price Index (CPI)")
        self.assertIn("inflación",context.lower())

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
        self.assertNotIn("Petróleo Brent",report)
        self.assertIn("Bitcoin BTC/USDT",report)
        self.assertIn("Bitcoin BTC/USDT",report)

    @patch.object(radar, "official_news", return_value=[
        ("Reserva Federal: Monetary policy statement","https://www.federalreserve.gov/test","15/11/2026 11:00 UTC","Published a statement")])
    def test_news_labels_unknown_factual_summary_honestly(self, _news):
        with patch.object(radar, "local_news", return_value={}):
            report=radar.render({"series":{}})
        self.assertIn("Qué ocurrió:",report)
        self.assertIn("No se obtuvieron hechos adicionales verificables",report)
        self.assertIn("Por qué importa:",report)

    def test_offline_spanish_news_uses_source_excerpt_only(self):
        import news_offline_es as local
        payload=[("Federal Reserve releases financial stability report","Reserva Federal",
                  "The Federal Reserve published a new report. It describes conditions in financial markets. "
                  "This is a third sentence that should not be included.")]
        translated=local.local_news(payload, translate_fn=lambda s: "ES: "+s)
        self.assertEqual(translated[0]["title_es"],"ES: Federal Reserve releases financial stability report")
        self.assertIn("ES: The Federal Reserve published a new report.",translated[0]["summary_es"])
        self.assertNotIn("third sentence",translated[0]["summary_es"])
        self.assertEqual(local.local_news([("Notice","Fed","")],
                                          translate_fn=lambda s:"ES: "+s),{})

    @patch.object(radar, "official_news", return_value=[
        ("Reserva Federal: Federal Reserve publishes a report",
         "https://www.federalreserve.gov/test","15/11/2026 11:00 UTC",
         "The Federal Reserve published a report on financial stability.")])
    def test_news_renders_spanish_title_summary_and_original_source(self, _news):
        mock={0:{"title_es":"La Reserva Federal publica un informe",
                 "summary_es":"La Reserva Federal publicó un informe de estabilidad financiera."}}
        with patch.object(radar,"local_news",return_value=mock):
            report=radar.render({"series":{}})
        self.assertIn("La Reserva Federal publica un informe",report)
        self.assertIn("Qué ocurrió:",report)
        self.assertIn("La Reserva Federal publicó un informe",report)
        self.assertIn("https://www.federalreserve.gov/test",report)

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
