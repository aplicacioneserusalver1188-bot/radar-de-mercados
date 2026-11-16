#!/usr/bin/env python3
"""Recupera noticias fechadas con fuentes públicas verificables, sin API de pago."""
import html
import json
import pathlib
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from market_top_news import rank_news

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"market_top_news.json"
FEEDS=(
    ("CNBC","https://www.cnbc.com/id/100003114/device/rss/rss.html",("www.cnbc.com","cnbc.com")),
    ("CNBC Mercados","https://www.cnbc.com/id/20409666/device/rss/rss.html",("www.cnbc.com","cnbc.com")),
    ("MarketWatch","https://feeds.content.dowjones.io/public/rss/mw_topstories",("www.marketwatch.com","marketwatch.com")),
    ("NPR Economía","https://feeds.npr.org/1006/rss.xml",("www.npr.org","npr.org")),
)

def clean_description(raw):
    return " ".join(html.unescape(re.sub(r"<[^>]*>"," ",raw or "")).split())[:650]

def parse_rss(data,source,allowed,now=None):
    root=ET.fromstring(data)
    found=[]
    for item in root.findall(".//item"):
        title=(item.findtext("title") or "").strip()
        url=(item.findtext("link") or "").strip()
        publication=(item.findtext("pubDate") or "").strip()
        host=urlsplit(url)
        if not title or host.scheme!="https" or host.hostname not in allowed:
            continue
        try:
            stamp=parsedate_to_datetime(publication)
            if stamp.tzinfo is None:continue
            stamp=stamp.astimezone(timezone.utc)
        except (TypeError,ValueError,OverflowError):
            continue
        found.append({"title":html.unescape(title)[:290],"url":url,
                      "source":source,"published":stamp.isoformat(),
                      "description":clean_description(item.findtext("description")),
                      "verified_host":True})
    return found

def download(url):
    request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; ObservatorioRM/1.0)","Accept":"application/rss+xml,application/xml"})
    with urllib.request.urlopen(request,timeout=8) as response:
        return response.read(500_000)

def collect(request_fn=None,official_fn=None,now=None):
    request_fn=request_fn or download
    now=now or datetime.now(timezone.utc)
    items=[]
    for source,url,allowed in FEEDS:
        try:
            data=parse_rss(request_fn(url),source,allowed,now)
            items.extend(data)
            print("Noticias",source,len(data))
        except (OSError,ET.ParseError,ValueError,UnicodeError) as exc:
            print("Feed no disponible",source,type(exc).__name__)
    if official_fn is None:
        from daily_wall_street import official_news
        official_fn=official_news
    try:
        for title,url,date,description in official_fn():
            try:
                stamp=datetime.strptime(date,"%d/%m/%Y %H:%M UTC").replace(tzinfo=timezone.utc)
            except (TypeError,ValueError):
                continue
            label,sep,headline=title.partition(": ")
            items.append({"title":headline if sep else title,"url":url,
                          "source":label if sep else "Comunicado oficial",
                          "published":stamp.isoformat(),"description":clean_description(description),
                          "verified_host":urlsplit(url).hostname in {
                              "www.federalreserve.gov","www.bls.gov","www.sec.gov",
                              "apps.bea.gov","www.bea.gov","bea.gov"}})
    except (OSError,ValueError,TypeError) as exc:
        print("Comunicados oficiales no disponibles:",type(exc).__name__)
    selected=rank_news(items,now=now)
    # Evitar almacenar datos personales o contenido de páginas sin permiso:
    # solo título, extracto breve, fecha, fuente, enlace y criterio editorial.
    return {"generated_at":now.isoformat(),"selection":"Prioridad editorial ponderada, no probabilidad",
            "considered":len(items),"items":selected}

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    result=collect()
    OUT.write_text(json.dumps(result,ensure_ascii=False),encoding="utf-8")
    print("Top noticias de impacto:",len(result["items"]),"de",result["considered"],
          "candidatas; no se rellenan huecos.")

if __name__=="__main__":main()
