#!/usr/bin/env python3
"""Noticias financieras recientes por empresa, desde un RSS gratuito.

Los titulares son referencias editoriales: NO prueban causalidad del precio.
No usa IA de pago ni credenciales. Solo enlaces y fechas de la fuente.
"""
import json
import pathlib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"company_news.json"
QUERIES={
    "NVDA":"NVIDIA stock earnings AI chips",
    "MSFT":"Microsoft stock Azure AI",
    "AAPL":"Apple stock iPhone",
    "AMZN":"Amazon stock AWS",
    "GOOGL":"Alphabet Google stock AI",
    "META":"Meta Platforms stock advertising",
    "AVGO":"Broadcom stock semiconductors",
    "JPM":"JPMorgan Chase stock banking",
    "TSLA":"Tesla stock vehicles",
    "TSM":"TSMC Taiwan Semiconductor stock",
    "SPCX":"SpaceX stock company",
}

def parse_feed(payload,now=None):
    today=now or datetime.now(timezone.utc)
    result=[]
    root=ET.fromstring(payload)
    for item in root.findall("./channel/item"):
        title=(item.findtext("title") or "").strip()
        link=(item.findtext("link") or "").strip()
        publication=(item.findtext("pubDate") or "").strip()
        origin=item.find("source")
        source=(origin.text or "").strip() if origin is not None else ""
        if not title or not link.startswith("https://news.google.com/"):
            continue
        try:
            published=parsedate_to_datetime(publication)
            if not published.tzinfo: continue
            age=today-published.astimezone(timezone.utc)
            if not timedelta(0)<=age<=timedelta(days=7): continue
        except (ValueError,TypeError,OverflowError):
            continue
        # Noticias sindicadas, no contenido completo ni hechos comprobados de forma independiente.
        result.append({"title":title[:300],"url":link,
                       "source":source[:80] or "Google Noticias (agregador)",
                       "date":published.date().isoformat()})
    return result[:2]

def collect(request_fn=None):
    request_fn=request_fn or _download
    companies={}
    for ticker,query in QUERIES.items():
        url="https://news.google.com/rss/search?"+urllib.parse.urlencode({
            "q":query+" when:7d", "hl":"en-US","gl":"US","ceid":"US:en"})
        try:
            found=parse_feed(request_fn(url))
            companies[ticker]=found
        except (OSError,ValueError,ET.ParseError,UnicodeError) as error:
            print("Noticias empresa",ticker,":",type(error).__name__)
            companies[ticker]=[]
        print("Noticias",ticker,len(companies[ticker]))
    return {"updated_at":datetime.now(timezone.utc).isoformat(),"companies":companies}

def _download(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; ObservatorioRM/1.0)"})
    with urllib.request.urlopen(req,timeout=6) as response:
        return response.read(350_000)

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(collect(),ensure_ascii=False),encoding="utf-8")

if __name__=="__main__":main()
