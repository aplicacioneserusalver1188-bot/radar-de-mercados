import json
import sys
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import market_top_news as top
import update_market_top_news as feed
import daily_wall_street as radar

NOW=datetime(2026,11,15,23,0,tzinfo=timezone.utc)

def item(title,age_hours=2,description=""):
    return {"title":title,"url":"https://www.cnbc.com/article/"+str(len(title))+"/",
            "source":"CNBC","published":(NOW-timedelta(hours=age_hours)).isoformat(),
            "description":description,"verified_host":True}

class TopNewsTests(unittest.TestCase):
    def test_scoring_weights_and_priorities(self):
        inflation=item("Inflation CPI surprises investors")
        result=top.score(inflation,now=NOW)
        self.assertEqual(result["score"],100)
        self.assertEqual(result["topic"],"Inflación")
        self.assertIn("bonos",result["assets"])
        self.assertIsNone(top.score(item("New pricing for payment services"),now=NOW))
        self.assertIsNone(top.score(item("Best stocks to buy amid inflation"),now=NOW))
        self.assertIsNone(top.score(item("Analyst picks top technology stocks"),now=NOW))
        self.assertIsNone(top.score(item("Small biotech earnings beat estimates"),now=NOW))
        self.assertIsNotNone(top.score(item("Nvidia earnings change AI chip outlook"),now=NOW))

    def test_recent_news_is_prioritized_without_dropping_ongoing_catalysts(self):
        recent=item("Federal Reserve considers interest rate policy",age_hours=2)
        previous=item("Fed rate hike weighs on markets",age_hours=40)
        recent["url"]="https://www.cnbc.com/article/fed-today"
        previous["url"]="https://www.cnbc.com/article/fed-yesterday"
        result=top.rank_news([recent,previous],now=NOW)
        self.assertEqual(len(result),1)
        old=item("FOMC announces rate hike",age_hours=170)
        self.assertFalse(top.rank_news([old],now=NOW))

    def test_no_duplicate_and_no_fillers(self):
        first=item("Federal Reserve signals interest rate cut")
        second=item("Federal Reserve signals interest rate cut")
        second["url"]="https://www.cnbc.com/another"
        third=item("Federal Reserve signals interest rate cut on Sunday")
        third["url"]="https://www.cnbc.com/third"
        filler=item("Interesting lifestyle story about celebrities")
        result=top.rank_news([first,second,third,filler],now=NOW)
        self.assertEqual(len(result),1)

    def test_sources_and_published_date_validation(self):
        xml=b"""<rss><channel>
          <item><title>US inflation CPI report shocks market</title>
            <link>https://www.cnbc.com/2026/11/15/news.html</link>
            <pubDate>Sun, 15 Nov 2026 21:00:00 GMT</pubDate>
            <description>Consumer prices changed compared with forecasts according to officials.</description>
          </item>
          <item><title>Markets face FOMC decision</title>
            <link>https://evil.example/redirect</link>
            <pubDate>Sun, 15 Nov 2026 21:00:00 GMT</pubDate>
          </item></channel></rss>"""
        out=feed.parse_rss(xml,"CNBC",("www.cnbc.com",),NOW)
        self.assertEqual(len(out),1)
        self.assertIn("CPI",out[0]["title"])
        self.assertEqual(out[0]["source"],"CNBC")

    def test_render_avoids_repeated_title_and_generic_instructions(self):
        news=item("US inflation CPI surprises investors",
                  description="Published consumer inflation figures differed from earlier projections. Financial markets may adjust their rate expectations.")
        result=top.rank_news([news],now=NOW)
        text=top.render_top_news(result)
        self.assertIn("Impacto potencial:",text)
        self.assertIn("Activos afectados:",text)
        self.assertIn("Prioridad editorial 100/100",text)
        self.assertIn("Nasdaq 100",text)
        self.assertNotIn("revisar el comunicado",text.lower())
        self.assertEqual(text.count("US inflation CPI surprises investors"),1)

    def test_translation_noise_is_rejected(self):
        news=top.rank_news([item("US inflation CPI surprises investors")],now=NOW)
        text=top.render_top_news(news,translate_fn=lambda _:"URL structure: https://example.gov/policy")
        self.assertIn("US inflation CPI surprises investors",text)
        self.assertNotIn("URL structure",text)

    @patch.object(radar,"official_news",return_value=[])
    def test_report_top_news_is_unique_and_near_front(self,_news):
        headlines=top.rank_news([item("Inflation CPI surprises investors")],now=NOW)
        rendered=radar.render({"series":{}},market_news=headlines)
        self.assertIn("Las 5 noticias que pueden mover Wall Street",rendered)
        self.assertEqual(rendered.count("Inflation CPI surprises investors"),1)
        self.assertLess(rendered.index("Las 5 noticias que pueden mover Wall Street"),
                        rendered.index("Pulso de los mercados"))
        self.assertNotIn("Noticias y catalizadores</h2>",rendered)

    @patch.object(radar,"official_news",return_value=[])
    def test_no_fabricated_news_if_feeds_unavailable(self,_news):
        rendered=radar.render({"series":{}},market_news=[])
        self.assertIn("No se obtuvieron noticias con relevancia",rendered)
        self.assertNotIn("1. <a",rendered)

if __name__=="__main__":unittest.main()
