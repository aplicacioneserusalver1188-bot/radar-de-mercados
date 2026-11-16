#!/usr/bin/env python3
"""Agenda verificable de los próximos siete días para Wall Street.

Prioriza calendarios oficiales (BLS, Fed y NYSE). Los resultados empresariales
solo se incluyen cuando Yahoo Finance publica una fecha para una empresa seguida.
"""
import calendar
import html
import json
import pathlib
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"week_ahead.json"
BLS="https://www.bls.gov/schedule/{year}/{month:02d}_sched_list.htm"
FOMC="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
NYSE="https://www.nyse.com/markets/hours-calendars"
COMPANIES=("NVDA","MSFT","AAPL","AMZN","GOOGL","META","AVGO","JPM","TSLA","TSM","SPCX")
MONTHS={name:index for index,name in enumerate(calendar.month_name) if name}
WEEKDAYS=("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")
IMPORTANT_BLS=("Consumer Price Index","Producer Price Index","Employment Situation",
               "Job Openings","Import and Export Price","Employment Cost Index",
               "Productivity and Costs","State Employment and Unemployment")

def get(url):
    request=urllib.request.Request(url,headers={"User-Agent":"RadarWallStreet/1.0 (public financial calendar)","Accept":"text/html,application/json"})
    with urllib.request.urlopen(request,timeout=16) as response:
        return response.read(800_000).decode("utf-8","replace")

def plain(content):
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",content))).strip()

def in_window(day,start,end):
    return start<=day<=end

def parse_bls_schedule(content,start,end):
    text=plain(content)
    result=[]
    date_pattern="|".join(WEEKDAYS)
    pattern=re.compile(rf"(?:{date_pattern}),\s+([A-Z][a-z]+)\s+(\d{{1,2}}),\s+(\d{{4}})\s*(\d{{1,2}}:\d{{2}}\s+[AP]M)?\s*(.*?)(?=(?:{date_pattern}),\s+[A-Z][a-z]+\s+\d{{1,2}},\s+\d{{4}}|NOTE:|$)")
    for month,day,year,time,title in pattern.findall(text):
        if month not in MONTHS:
            continue
        event_day=date(int(year),MONTHS[month],int(day))
        title=" ".join(title.split())
        if in_window(event_day,start,end) and any(key.casefold() in title.casefold() for key in IMPORTANT_BLS):
            result.append({"date":event_day.isoformat(),"time":time or "Hora no indicada","timezone":"ET",
                           "category":"Macro","title":title,"source":"BLS","url":"https://www.bls.gov/schedule/"})
    return result

def parse_fomc_meetings(content,year):
    """Extrae las reuniones regulares que la Fed publica en su calendario anual."""
    text=plain(content)
    heading=f"{year} FOMC Meetings"
    section=text.split(heading,1)[1] if heading in text else ""
    if not section:
        return []
    section=section.split(f"{year-1} FOMC Meetings",1)[0]
    rows=[]
    for month,first,last in re.findall(r"\b("+"|".join(MONTHS)+r")\s+(\d{1,2})-(\d{1,2})",section):
        rows.append((date(year,MONTHS[month],int(first)),date(year,MONTHS[month],int(last))))
    return rows

def fomc_events(content,start,end):
    events=[]
    for year in {start.year,end.year}:
        for first,last in parse_fomc_meetings(content,year):
            if in_window(first,start,end) or in_window(last,start,end):
                events.append({"date":first.isoformat(),"time":"Hora según Fed","timezone":"ET",
                               "category":"Fed","title":f"Reunión FOMC ({first.strftime('%d/%m')}–{last.strftime('%d/%m')})",
                               "source":"Reserva Federal","url":FOMC})
            minutes=last+timedelta(days=21)
            if in_window(minutes,start,end):
                events.append({"date":minutes.isoformat(),"time":"14:00","timezone":"ET",
                               "category":"Fed","title":f"Publicación estimada de minutas FOMC ({first.strftime('%d/%m')}–{last.strftime('%d/%m')})",
                               "source":"Reserva Federal","url":FOMC})
    return events

def easter(year):
    a=year%19; b=year//100; c=year%100; d=b//4; e=b%4; f=(b+8)//25; g=(b-f+1)//3
    h=(19*a+b-d-g+15)%30; i=c//4; k=c%4; l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451
    return date(year,(h+l-7*m+114)//31,((h+l-7*m+114)%31)+1)

def observed(day):
    return day-timedelta(days=1) if day.weekday()==5 else day+timedelta(days=1) if day.weekday()==6 else day

def nyse_holidays(year):
    jan1=observed(date(year,1,1)); juneteenth=observed(date(year,6,19)); july4=observed(date(year,7,4)); christmas=observed(date(year,12,25))
    third_monday=lambda month: date(year,month,1)+timedelta(days=(14-date(year,month,1).weekday())%7)
    last_monday=lambda month: date(year,month,calendar.monthrange(year,month)[1])-timedelta(days=(date(year,month,calendar.monthrange(year,month)[1]).weekday())%7)
    thanksgiving=date(year,11,1)+timedelta(days=(3-date(year,11,1).weekday())%7+21)
    return [(jan1,"Año Nuevo"),(third_monday(1),"Martin Luther King Jr. Day"),(third_monday(2),"Presidents Day"),
            (easter(year)-timedelta(days=2),"Good Friday"),(last_monday(5),"Memorial Day"),(juneteenth,"Juneteenth"),
            (july4,"Independence Day"),(date(year,9,1)+timedelta(days=(7-date(year,9,1).weekday())%7),"Labor Day"),
            (thanksgiving,"Thanksgiving Day"),(christmas,"Christmas Day")]

def market_holiday_events(start,end):
    events=[]
    for year in {start.year,end.year}:
        for day,name in nyse_holidays(year):
            if in_window(day,start,end):
                events.append({"date":day.isoformat(),"time":"Mercado cerrado","timezone":"ET","category":"Mercado",
                               "title":f"NYSE cerrada: {name}","source":"NYSE","url":NYSE})
    return events

def earnings_events(start,end):
    events=[]
    for ticker in COMPANIES:
        url=f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=calendarEvents"
        try:
            payload=json.loads(get(url))
            dates=payload["quoteSummary"]["result"][0].get("calendarEvents",{}).get("earnings",{}).get("earningsDate",[])
            for item in dates[:1]:
                stamp=item.get("raw")
                if isinstance(stamp,(int,float)):
                    day=datetime.fromtimestamp(stamp,timezone.utc).date()
                    if in_window(day,start,end):
                        events.append({"date":day.isoformat(),"time":"Hora por confirmar","timezone":"ET","category":"Resultados",
                                       "title":f"Resultado programado: {ticker}","source":"Yahoo Finance","url":url})
        except (OSError,ValueError,KeyError,IndexError,TypeError,urllib.error.HTTPError):
            continue
    return events

def collect(now=None,request=get):
    today=(now or datetime.now(timezone.utc)).date(); end=today+timedelta(days=7)
    events=[]; errors=[]
    for month_start in {date(today.year,today.month,1),date(end.year,end.month,1)}:
        try:
            events.extend(parse_bls_schedule(request(BLS.format(year=month_start.year,month=month_start.month)),today,end))
        except (OSError,ValueError,urllib.error.HTTPError) as error:
            errors.append("BLS: "+type(error).__name__)
    try:
        events.extend(fomc_events(request(FOMC),today,end))
    except (OSError,ValueError,urllib.error.HTTPError) as error:
        errors.append("Fed: "+type(error).__name__)
    events.extend(market_holiday_events(today,end))
    events.extend(earnings_events(today,end)) if request is get else []
    unique={(e["date"],e["category"],e["title"]):e for e in events}
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"window_start":today.isoformat(),"window_end":end.isoformat(),
            "events":sorted(unique.values(),key=lambda e:(e["date"],e["category"],e["title"]))[:16],"errors":errors}

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    result=collect(); OUT.write_text(json.dumps(result,ensure_ascii=False),encoding="utf-8")
    print("Agenda semanal:",len(result["events"]),"eventos")

if __name__=="__main__":main()
