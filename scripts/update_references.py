#!/usr/bin/env python3
"""Referencias independientes: oro XAU/USD, WTI/Brent FRED y BTC/USDT Binance."""
import json, pathlib, urllib.request
from datetime import datetime, timezone
from update_wall_street_data import series as fred_series

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"references.json"

def request_json(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"ObservatorioRM/1.0"}),timeout=12) as response:
        return json.loads(response.read(100000))

def parse_gold(obj):
    value=float(obj["price"])
    if value <= 0: raise ValueError("precio XAU no válido")
    stamp=obj.get("updatedAt")
    if not stamp: raise ValueError("fecha XAU no disponible")
    stamp=datetime.fromisoformat(stamp.replace("Z","+00:00"))
    if stamp.tzinfo is None: raise ValueError("fecha XAU sin zona")
    return {"value":value,"timestamp":stamp.astimezone(timezone.utc).isoformat(),"unit":"USD/onza troy",
            "source":"https://gold-api.com/","label":"Oro XAU/USD (spot)"}

def parse_btc(obj):
    if obj.get("symbol") != "BTCUSDT": raise ValueError("par BTC inesperado")
    value=float(obj["lastPrice"])
    if value <= 0: raise ValueError("precio BTC no válido")
    timestamp=datetime.fromtimestamp(int(obj["closeTime"])/1000,timezone.utc).isoformat()
    return {"value":value,"timestamp":timestamp,"unit":"USDT/BTC",
            "change_24h":float(obj["priceChangePercent"]),
            "source":"https://www.binance.com/en/trade/BTC_USDT","label":"Bitcoin BTC/USDT (Binance)"}

def collect():
    data={"updated_at":datetime.now(timezone.utc).isoformat(),"assets":{}}
    for key,fid,label in (("wti","DCOILWTICO","Petróleo WTI"),("brent","DCOILBRENTEU","Petróleo Brent")):
        try:
            points=fred_series(fid)
            if not points: raise ValueError("sin observaciones")
            last=points[-1]
            data["assets"][key]={"value":last["value"],"date":last["date"],
               "unit":"USD/barril","label":label,"source":"https://fred.stlouisfed.org/series/"+fid,
               "previous":points[-2] if len(points)>1 else None}
        except (OSError,KeyError,TypeError,ValueError) as error:
            data["assets"][key]={"error":type(error).__name__}
    for key,url,parser in (
        ("gold","https://api.gold-api.com/price/XAU",parse_gold),
        ("btc","https://data-api.binance.vision/api/v3/ticker/24hr?symbol=BTCUSDT",parse_btc)):
        try:data["assets"][key]=parser(request_json(url))
        except (OSError,KeyError,TypeError,ValueError) as error:
            data["assets"][key]={"error":type(error).__name__}
    return data

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(collect(),ensure_ascii=False),encoding="utf-8")

if __name__=="__main__":main()
