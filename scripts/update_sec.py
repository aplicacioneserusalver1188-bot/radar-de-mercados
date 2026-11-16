#!/usr/bin/env python3
"""Extract comparable annual SEC company facts; never substitute absent values."""
import json
import os
import pathlib
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sec_company_summary.json"
STATUS_OUT = ROOT / "data" / "sec_fetch_status.json"
COMPANIES = {
    "NVDA": 1045810, "MSFT": 789019, "AAPL": 320193,
    "AMZN": 1018724, "GOOGL": 1652044, "META": 1326801,
    "AVGO": 1730168, "JPM": 19617, "TSLA": 1318605,
    "TSM": 1046179, "SPCX": 1181412,
}
TAGS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues", "SalesRevenueNet"),
    "net_income": ("NetIncomeLoss",),
    "operating_cash": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_expenditure": ("PaymentsToAcquirePropertyPlantAndEquipment",),
}
# Presentación internacional: SEC puede publicar información de emisores extranjeros en IFRS y TWD.
IFRS_TAGS = {
    "revenue": ("Revenue", "RevenueFromContractsWithCustomers"),
    "net_income": ("ProfitLoss", "ProfitLossAttributableToOwnersOfParent"),
    "operating_cash": ("CashFlowsFromUsedInOperatingActivities",),
    "capital_expenditure": ("PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",),
}
def financial_series(facts, namespaces, names, forms, months, currency):
    """Dos periodos completos comparables; nunca mezclar moneda ni duración."""
    for namespace in namespaces:
        section=facts.get("facts",{}).get(namespace,{})
        for name in names:
            units=section.get(name,{}).get("units",{}).get(currency,[])
            periods=[]
            for row in units:
                if row.get("form") not in forms or row.get("fp") not in ("FY", "Q1", "Q2", "Q3", "Q4"):
                    continue
                try:
                    start,end=row["start"],row["end"]
                    duration=(datetime.fromisoformat(end)-datetime.fromisoformat(start)).days
                    allowed=(330<=duration<=380 if months==12 else 70<=duration<=105)
                    if not allowed or not isinstance(row.get("val"),(int,float)) or not row.get("filed"):
                        continue
                    periods.append({"end":end,"filed":row["filed"],"value":row["val"],
                                    "currency":currency,"form":row["form"],"start":start})
                except (KeyError,TypeError,ValueError):
                    continue
            if periods:
                latest={}
                for row in sorted(periods,key=lambda x:(x["end"],x["filed"])):
                    latest[row["end"]]=row
                return sorted(latest.values(),key=lambda x:x["end"],reverse=True)[:2]
    return []

def sec_user_agent():
    """Return only an SEC identity with a contact address.

    A repository URL is not an operational contact.  Avoid requests using the
    old generic identity, which predictably receives HTTP 403.
    """
    value = os.getenv("SEC_USER_AGENT", "").strip()
    return value if "@" in value and len(value) >= 12 else ""

def load_summary():
    try:
        value = json.loads(OUT.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) and isinstance(value.get("companies"), dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}

def has_financial_data(summary):
    return any(info.get("metrics") for info in summary.get("companies", {}).values()
               if isinstance(info, dict))

def write_status(**status):
    status["attempted_at"] = datetime.now(timezone.utc).isoformat()
    STATUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATUS_OUT.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")

def annual_values(facts, tags):
    """Escoger el año fiscal más reciente ENTRE TODAS las etiquetas GAAP alternativas.

    Antes se elegía la primera etiqueta con registros, incluso si era de 2012 o
    2022, ignorando otra etiqueta con información de 2026.
    """
    gaap=facts.get("facts",{}).get("us-gaap",{})
    candidates=[]
    for tag in tags:
        units=gaap.get(tag,{}).get("units",{}).get("USD",[])
        for row in units:
            if row.get("form")!="10-K" or row.get("fp")!="FY":
                continue
            start,end,filed=row.get("start"),row.get("end"),row.get("filed")
            if not all((start,end,filed)) or not isinstance(row.get("val"),(int,float)):
                continue
            try:
                span=(datetime.fromisoformat(end)-datetime.fromisoformat(start)).days
            except (TypeError,ValueError):
                continue
            if 330<=span<=380:
                candidates.append({"end":end,"filed":filed,"value":row["val"],
                                   "currency":"USD","form":"10-K","start":start,
                                   "accession":row.get("accn"),"tag":tag})
    newest={}
    # Priorizar etiquetas listadas solo cuando pertenecen al mismo cierre.
    tag_order={tag:i for i,tag in enumerate(tags)}
    for row in sorted(candidates,key=lambda x:(x["end"],-tag_order[x["tag"]],x["filed"])):
        newest[row["end"]]=row
    dates=sorted(newest,reverse=True)
    return [newest[x] for x in dates[:2]]

def summarize(facts, ticker):
    metrics = {name: annual_values(facts, tags) for name, tags in TAGS.items()}
    if ticker=="TSM":
        # TSM reporta como emisor extranjero: datos IFRS de 20-F, generalmente en TWD.
        for name,tags in IFRS_TAGS.items():
            if not metrics[name]:
                metrics[name]=financial_series(facts,("ifrs-full",),tags,("20-F",),12,"TWD")
    # Una cifra aislada antigua de una etiqueta no se mezcla con los ejercicios
    # recientes del resto de estados financieros de la misma compañía.
    all_periods=[datetime.fromisoformat(rows[0]["end"])
                 for rows in metrics.values() if rows]
    if all_periods:
        latest_period=max(all_periods)
        for key,rows in metrics.items():
            if rows:
                gap=(latest_period-datetime.fromisoformat(rows[0]["end"])).days
                if gap>400:
                    metrics[key]=[]
    quarterly={}
    if ticker=="SPCX":
        # Solo periodos individuales de ~3 meses; no comparar acumulados 9M con trimestres.
        quarterly={name:financial_series(facts,("us-gaap",),tags,("10-Q",),3,"USD")
                   for name,tags in TAGS.items()}
    return {"ticker": ticker, "entity_name": facts.get("entityName", ticker),
            "cik": facts.get("cik"), "metrics": metrics,"quarterly_metrics":quarterly,
            "source": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{COMPANIES[ticker]:010d}.json"}

def main():
    result = {"updated_at": datetime.now(timezone.utc).isoformat(), "companies": {}}
    previous = load_summary()
    agent = sec_user_agent()
    if not agent:
        write_status(state="not_attempted", reason="SEC_USER_AGENT_REQUIRES_CONTACT_EMAIL")
        print("SEC no consultada: configurar SEC_USER_AGENT con nombre de aplicación y correo de contacto válido.")
        return
    sec_access_blocked = False
    for ticker, cik in COMPANIES.items():
        if sec_access_blocked:
            result["companies"][ticker] = {"ticker": ticker, "error": "SEC_ACCESS_BLOCKED_AFTER_403"}
            continue
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": agent, "Accept-Encoding": "identity",
                "Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=18) as response:
                facts = json.loads(response.read(25_000_000))
            result["companies"][ticker] = summarize(facts, ticker)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            status = getattr(exc, "code", None)
            result["companies"][ticker] = {"ticker": ticker, "error": type(exc).__name__, "http_status": status}
            if status == 403:
                sec_access_blocked = True
                print("SEC HTTP 403: detener consultas restantes, respetando el control de acceso del proveedor.")
        time.sleep(0.15)  # Respect SEC limits, one sequential request per company.
    available=sum(bool(c.get("metrics", {}).get("revenue")) for c in result["companies"].values())
    if sec_access_blocked and not available and has_financial_data(previous):
        write_status(state="blocked", http_status=403, preserved_cached_summary=True)
        print("SEC HTTP 403: se conserva el último resumen SEC verificable; no se reemplaza por ausencias.")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    write_status(state="blocked" if sec_access_blocked else "ok",
                 http_status=403 if sec_access_blocked else None,
                 preserved_cached_summary=False)
    print("SEC: métricas empresariales disponibles:", available)
    print("SEC: fallos por empresa (tipo y HTTP):",
          {ticker: (item.get("error"), item.get("http_status"))
           for ticker, item in result["companies"].items() if item.get("error")})

if __name__ == "__main__":
    main()
