#!/usr/bin/env python3
"""Amplitud de mercado publicada por proveedores externos: medias simples de 20/50/200."""
import json, pathlib, re, urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"breadth.json"
SOURCES={
    "sp500":("S&P 500","https://chartrow.com/sp500/market-breadth"),
    "nasdaq100":("Nasdaq 100","https://aveceasar.github.io/nasdaq100-percent-above-moving-averages/"),
}

class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(); self.words=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):self.skip+=1
    def handle_endtag(self,tag):
        if tag in ("script","style") and self.skip:self.skip-=1
    def handle_data(self,data):
        if not self.skip:self.words.append(data)
def text_content(html):
    parser=PlainText()
    parser.feed(html)
    return " ".join(" ".join(parser.words).split())

def read_date(text):
    match=re.search(r"(?:20\d\d)-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])",text)
    return match.group(0) if match else None

def parse_nasdaq(content):
    text=text_content(content)
    pattern=r"Latest values\s+(20\d\d-\d\d-\d\d)\s+Above 20DMA\s+([\d.]+)%\s+Above 50DMA\s+([\d.]+)%\s+Above 200DMA\s+([\d.]+)%"
    match=re.search(pattern,text,re.I)
    if not match:raise ValueError("Sin tabla de medias simples Nasdaq 100 verificable")
    return {"date":match.group(1),"ma20":float(match.group(2)),"ma50":float(match.group(3)),"ma200":float(match.group(4)),
            "method":"SMA, cesta de componentes actuales; cobertura variable"}

def parse_sp500(content):
    text=text_content(content)
    # Buscar el resumen compacto de 20/50/200 SMA, no textos sueltos que podrían tener otro periodo.
    patterns=[
      r"200d\s+([\d.]+)%\s*50d\s+([\d.]+)%\s*20d\s+([\d.]+)%\s*([A-Z][a-z]{2} \d{1,2}, 20\d\d)?",
      r"20d\s+([\d.]+)%\s*50d\s+([\d.]+)%\s*200d\s+([\d.]+)%\s*([A-Z][a-z]{2} \d{1,2}, 20\d\d)?",
    ]
    match=re.search(patterns[0],text,re.I)
    if match:
        ma200,ma50,ma20=map(float,match.groups()[:3])
    else:
        match=re.search(patterns[1],text,re.I)
        if not match:raise ValueError("S&P 500 sin trío SMA 20/50/200 verificable")
        ma20,ma50,ma200=map(float,match.groups()[:3])
    # Chartrow antes mostraba "as of market close". Ahora muestra la fecha
    # consolidada junto al trío de medias y una hora intradía distinta arriba.
    # Preferimos la fecha del trío: representa el cierre utilizado en el cálculo.
    raw_date=match.group(4) or None
    if not raw_date:
        legacy_date=re.search(r"as of market close,\s+([A-Z][a-z]{2} \d{1,2}, 20\d\d)",text)
        raw_date=legacy_date.group(1) if legacy_date else None
    if not raw_date:raise ValueError("Fecha de cierre S&P 500 no identificada")
    date=datetime.strptime(raw_date,"%b %d, %Y").date().isoformat()
    return {"date":date,"ma20":ma20,"ma50":ma50,"ma200":ma200,
            "method":"SMA, universo de miembros cubiertos por el proveedor"}

def validate(row):
    d=datetime.fromisoformat(row["date"]).replace(tzinfo=timezone.utc)
    days=(datetime.now(timezone.utc).date()-d.date()).days
    if not 0<=days<=7:raise ValueError("Lectura antigua o futura")
    if any(not 0<=row["ma"+str(n)]<=100 for n in (20,50,200)):
        raise ValueError("Amplitud fuera de rango")
    return row

def collect():
    result={"updated_at":datetime.now(timezone.utc).isoformat(),"indices":{}}
    for key,(label,url) in SOURCES.items():
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"ObservatorioRM/1.0"})
            with urllib.request.urlopen(req,timeout=12) as response:
                content=response.read(1_000_000).decode("utf-8","replace")
            values=validate(parse_nasdaq(content) if key=="nasdaq100" else parse_sp500(content))
            result["indices"][key]={"label":label,"source":url,**values}
        except (OSError,ValueError,TypeError,KeyError) as error:
            result["indices"][key]={"label":label,"source":url,"error":type(error).__name__}
    return result

def main():
    data=collect()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
    print("Amplitud SMA:",{k:("OK" if "ma20" in v else "no disponible") for k,v in data["indices"].items()})

if __name__=="__main__":main()
