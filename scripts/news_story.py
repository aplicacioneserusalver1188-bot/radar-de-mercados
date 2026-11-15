#!/usr/bin/env python3
"""Extrae párrafos factuales de comunicados oficiales; no añade hechos externos."""
from html.parser import HTMLParser
from urllib.parse import urlsplit
import urllib.request

TRUSTED={"www.federalreserve.gov","www.bls.gov","www.sec.gov",
         "www.bea.gov","bea.gov","apps.bea.gov"}

class Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside=0
        self.blocked=0
        self.buffer=[]
        self.paragraphs=[]
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","nav","footer","header"):
            self.blocked+=1
        if tag=="p":
            self.inside+=1
            self.buffer=[]
    def handle_endtag(self,tag):
        if tag=="p" and self.inside:
            value=" ".join("".join(self.buffer).split())
            if 85<=len(value)<=2500:
                self.paragraphs.append(value)
            self.buffer=[]
            self.inside-=1
        if tag in ("script","style","nav","footer","header") and self.blocked:
            self.blocked-=1
    def handle_data(self,data):
        if self.inside and not self.blocked:
            self.buffer.append(data)

def official_details(url,title="",request_fn=None):
    parts=urlsplit(url)
    if parts.scheme!="https" or parts.hostname not in TRUSTED:
        return ""
    if request_fn is None:
        request=urllib.request.Request(url,headers={"User-Agent":"ObservatorioRM/1.0 (personal digest)"})
        with urllib.request.urlopen(request,timeout=7) as response:
            if urlsplit(response.geturl()).hostname not in TRUSTED:
                return ""
            payload=response.read(350_000).decode("utf-8","replace")
    else:
        payload=request_fn(url)
    parser=Paragraphs()
    parser.feed(payload)
    clean=[]
    normalized=title.casefold().strip()
    for paragraph in parser.paragraphs:
        if (paragraph.casefold().strip()==normalized or
            "subscribe" in paragraph.casefold() or
            "javascript" in paragraph.casefold()):
            continue
        clean.append(paragraph)
        if len(clean)>=2:
            break
    return " ".join(clean)[:1000]
