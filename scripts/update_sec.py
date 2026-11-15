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
COMPANIES = {
    "NVDA": 1045810, "MSFT": 789019, "AAPL": 320193,
    "AMZN": 1018724, "GOOGL": 1652044, "META": 1326801,
    "AVGO": 1730168, "JPM": 19617, "TSLA": 1318605,
}
TAGS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues", "SalesRevenueNet"),
    "net_income": ("NetIncomeLoss",),
    "operating_cash": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_expenditure": ("PaymentsToAcquirePropertyPlantAndEquipment",),
}
AGENT = os.getenv("SEC_USER_AGENT") or "ObservatorioRM/1.0 (contact: https://github.com/aplicacioneserusalver1188-bot/radar-de-mercados)"

def annual_values(facts, tags):
    """Only facts for full 10-K fiscal years, avoiding quarterly/YTD mixing."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        units = gaap.get(tag, {}).get("units", {}).get("USD", [])
        records = []
        for row in units:
            if row.get("form") != "10-K" or row.get("fp") != "FY":
                continue
            start, end, filed = row.get("start"), row.get("end"), row.get("filed")
            if not all((start, end, filed)) or not isinstance(row.get("val"), (int, float)):
                continue
            try:
                span = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
            except ValueError:
                continue
            if not 330 <= span <= 380:
                continue
            records.append({"end": end, "filed": filed, "value": row["val"],
                            "accession": row.get("accn")})
        if records:
            # Latest filing for each fiscal period; keep recent two distinct years.
            newest = {}
            for r in sorted(records, key=lambda x: (x["end"], x["filed"])):
                newest[r["end"]] = r
            return sorted(newest.values(), key=lambda x: x["end"], reverse=True)[:2]
    return []

def summarize(facts, ticker):
    metrics = {name: annual_values(facts, tags) for name, tags in TAGS.items()}
    return {"ticker": ticker, "entity_name": facts.get("entityName", ticker),
            "cik": facts.get("cik"), "metrics": metrics,
            "source": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{COMPANIES[ticker]:010d}.json"}

def main():
    result = {"updated_at": datetime.now(timezone.utc).isoformat(), "companies": {}}
    sec_access_blocked = False
    for ticker, cik in COMPANIES.items():
        if sec_access_blocked:
            result["companies"][ticker] = {"ticker": ticker, "error": "SEC_ACCESS_BLOCKED_AFTER_403"}
            continue
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": AGENT, "Accept-Encoding": "identity",
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
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print("SEC: métricas empresariales disponibles:",
          sum(bool(c.get("metrics", {}).get("revenue")) for c in result["companies"].values()))
    print("SEC: fallos por empresa (tipo y HTTP):",
          {ticker: (item.get("error"), item.get("http_status"))
           for ticker, item in result["companies"].items() if item.get("error")})

if __name__ == "__main__":
    main()
