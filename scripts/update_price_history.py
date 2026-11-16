#!/usr/bin/env python3
"""Histórico público, gratuito y sin claves para gráficos del informe PERSONAL.

Nunca se confunde oro spot con futuros ni BTC/USDT con BTC/USD.
Cada gráfico revela su fuente y el último día de observación.
"""
import csv
import io
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from update_wall_street_data import series as fred_series

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"price_history.json"
INDEX_KEYS={"sp500":("S&P 500","SP500"),"nasdaq100":("Nasdaq 100","NASDAQ100"),"dow":("Dow Jones Industrial Average","DJIA"),"russell":("Russell 2000","RU2000PR")}
COMPANIES=("NVDA","MSFT","AAPL","AMZN","GOOGL","META","AVGO","JPM","TSLA","TSM","SPCX")
TRADINGVIEW_SYMBOLS={
    "gold":"OANDA:XAUUSD", "wti":"TVC:USOIL", "btc":"BINANCE:BTCUSDT",
    "sp500":"SP:SPX", "nasdaq":"NASDAQ:IXIC", "nasdaq100":"NASDAQ:NDX",
    "dow":"DJ:DJI", "russell":"TVC:RUT", "JPM":"NYSE:JPM", "TSM":"NYSE:TSM",
    **{ticker:"NASDAQ:"+ticker for ticker in COMPANIES if ticker not in ("JPM","TSM")},
}

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"ObservatorioRM/1.0 (personal financial report)","Accept":"application/json,text/csv"})
    with urllib.request.urlopen(req,timeout=14) as response:
        return response.read(600_000)

def stooq(symbol):
    end=datetime.now(timezone.utc).date()
    start=end-timedelta(days=440)
    url=("https://stooq.com/q/d/l/?"
         +urllib.parse.urlencode({"s":symbol,"d1":start.strftime("%Y%m%d"),
                                  "d2":end.strftime("%Y%m%d"),"i":"d"}))
    rows=list(csv.DictReader(io.StringIO(get(url).decode("utf-8","replace"))))
    if not rows or "Date" not in rows[0] or "Close" not in rows[0]:
        raise ValueError("Stooq no devolvió serie diaria CSV")
    return standardize({"date":row["Date"],"open":row.get("Open"),
                        "high":row.get("High"),"low":row.get("Low"),
                        "close":row["Close"]} for row in rows)

def yahoo_stock(ticker):
    # Interfaz pública no oficial: alternativa gratuita, sin garantía de acceso.
    symbol=urllib.parse.quote(ticker,safe="")
    uri=f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d"
    obj=json.loads(get(uri))
    result=obj["chart"]["result"][0]
    if result.get("meta",{}).get("currency")!="USD":
        raise ValueError("Yahoo respondió otra moneda")
    times=result["timestamp"]
    quote=result["indicators"]["quote"][0]
    rows=[{"date":datetime.fromtimestamp(ts,timezone.utc).date().isoformat(),
           "open":o,"high":h,"low":l,"close":c}
          for ts,o,h,l,c in zip(times,quote["open"],quote["high"],quote["low"],quote["close"])
          if c is not None]
    return standardize(rows)

def standardize(rows):
    """Normaliza cierres y conserva OHLC solo si los cuatro valores son válidos."""
    seen={}
    for row in rows:
        if isinstance(row,dict):
            day,price=row.get("date"),row.get("close")
        else:
            day,price=row
        try:
            value=float(price)
            datetime.fromisoformat(day)
        except (ValueError,TypeError):
            continue
        if value>0 and value<1e9:
            point={"date":day,"close":round(value,6)}
            if isinstance(row,dict):
                try:
                    o,h,l=(float(row[name]) for name in ("open","high","low"))
                    if all(0 < item < 1e9 for item in (o,h,l)) and l<=min(o,value)<=max(o,value)<=h:
                        point.update(open=round(o,6),high=round(h,6),low=round(l,6))
                except (ValueError,TypeError,KeyError):
                    pass
            seen[day]=point
    out=[seen[day] for day in sorted(seen)]
    if len(out)<20:
        raise ValueError("Menos de 20 cierres comprobables")
    return out[-300:]

def gold_spot_history():
    """Histórico auténtico XAU/USD spot diario, gratuito y sin API key.

    No utilizar contratos GC=F, ETF GLD ni otros instrumentos como sustitutos.
    """
    obj=json.loads(get("https://xaus.com/api/v1/history"))
    if obj.get("symbol")!="XAUUSD" or obj.get("interval")!="daily":
        raise ValueError("La fuente no confirmó histórico spot XAU/USD diario")
    state=obj.get("data_state",{})
    if state and state.get("status")=="unavailable":
        raise ValueError("Fuente XAU spot sin datos disponibles")
    return standardize((p["d"],p["c"]) for p in obj.get("points",[])
                       if isinstance(p,dict) and "d" in p and "c" in p)

def btc_history():
    url="https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=300"
    rows=json.loads(get(url))
    today=datetime.now(timezone.utc).date().isoformat()
    return standardize({"date":datetime.fromtimestamp(int(r[0])/1000,timezone.utc).date().isoformat(),
                        "open":r[1],"high":r[2],"low":r[3],"close":r[4]}
                       for r in rows if len(r)>=7 and
                       datetime.fromtimestamp(int(r[0])/1000,timezone.utc).date().isoformat()<today)

def collect():
    result={"updated_at":datetime.now(timezone.utc).isoformat(),"assets":{}}
    for key in ("gold","wti","btc",*INDEX_KEYS,*COMPANIES):
        proxy=None
        try:
            if key=="gold":
                try:
                    points=gold_spot_history()
                    source="https://xaus.com/api/"
                except (OSError,ValueError,KeyError,TypeError):
                    # Una alternativa es válida únicamente si también es oro SPOT.
                    points=stooq("xauusd")
                    source="https://stooq.com/q/?s=xauusd"
                label="Precio del oro spot XAU/USD"
                unit="USD/onza troy"
            elif key=="wti":
                points=[{"date":p["date"],"close":p["value"]} for p in fred_series("DCOILWTICO")]
                if len(points)<20:raise ValueError("Histórico WTI insuficiente")
                source="https://fred.stlouisfed.org/series/DCOILWTICO"
                label="Petróleo WTI (EE. UU.)"
                unit="USD/barril"
            elif key=="btc":
                points=btc_history()
                source="https://data-api.binance.vision/"
                label="Bitcoin BTC/USDT"
                unit="USDT/BTC"
            elif key in INDEX_KEYS:
                # Reutilizar FRED; para Russell su cobertura no siempre existe.
                label,fid=INDEX_KEYS[key]
                market_path=ROOT/"data"/"market.json"
                market=(json.loads(market_path.read_text(encoding="utf-8"))
                        if market_path.exists() else {})
                rows=market.get("series",{}).get(key,{}).get("points",[])
                try:
                    points=standardize((p["date"],p["value"]) for p in rows)
                    source="https://fred.stlouisfed.org/series/"+fid
                    unit="puntos"
                except (ValueError,TypeError,KeyError):
                    if key!="russell":
                        raise
                    try:
                        points=yahoo_stock("^RUT")
                        source="https://finance.yahoo.com/quote/%5ERUT/history/"
                        unit="puntos"
                        label="Russell 2000 (índice ^RUT)"
                    except (OSError,ValueError,KeyError,TypeError,IndexError):
                        points=stooq("iwm.us")
                        source="https://stooq.com/q/?s=iwm.us"
                        unit="USD/participación ETF"
                        label="Russell 2000 — referencia ETF IWM"
                        proxy=("IWM es un ETF que sigue el Russell 2000, NO el "
                               "valor del índice. El gráfico es aproximación, "
                               "no cotización del Russell 2000.")
            else:
                try:
                    points=stooq(key.lower()+".us")
                    source="https://stooq.com/q/?s="+key.lower()+".us"
                except (OSError,ValueError,KeyError,TypeError):
                    points=yahoo_stock(key)
                    source="https://finance.yahoo.com/quote/"+key+"/history/"
                label=key
                unit="USD/acción"
            result["assets"][key]={"label":label,"unit":unit,"source":source,"points":points,
                                  "tradingview_url":"https://www.tradingview.com/chart/?symbol="
                                  +urllib.parse.quote(TRADINGVIEW_SYMBOLS.get(key,""),safe="")}
            if proxy:
                result["assets"][key]["proxy"]=proxy
        except (OSError,ValueError,KeyError,TypeError,IndexError) as error:
            result["assets"][key]={"error":type(error).__name__,"points":[]}
        print("Gráfico",key,":",len(result["assets"][key].get("points",[])),"observaciones")
    return result

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(collect(),ensure_ascii=False),encoding="utf-8")

if __name__=="__main__":main()
