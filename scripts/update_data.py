import csv, io, json, pathlib, urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "market.json"

def series(series_id):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    with urllib.request.urlopen(url, timeout=30) as response:
        rows = list(csv.DictReader(io.TextIOWrapper(response, encoding="utf-8")))
    clean = [{"date": r.get("observation_date") or r.get("DATE"), "value": float(r[series_id])} for r in rows if r.get(series_id) not in (None, ".", "")]
    return clean[-520:]

def main():
    data = {"updated_at": datetime.now(timezone.utc).isoformat(), "series": {}}
    for key, fred_id, label, frequency in [
        ("vix", "VIXCLS", "VIX", "daily"),
        ("inflation", "CPIAUCSL", "Índice de precios al consumidor", "monthly"),
        ("claims", "ICSA", "Solicitudes iniciales de desempleo", "weekly"),
        ("credit", "BAMLH0A0HYM2", "High Yield OAS", "daily"),
        ("treasury10y", "DGS10", "Treasury 10 años", "daily"),
        ("sofr", "SOFR", "SOFR", "daily"),
        ("diesel", "GASDESW", "Diésel minorista EE. UU.", "weekly"),
        ("rrp", "RRPONTSYD", "RRP overnight", "daily"),
        ("tga", "WTREGEN", "Treasury General Account", "weekly"),
        ("reserves", "WRESBAL", "Reservas bancarias", "weekly"),
    ]:
        try:
            data["series"][key] = {"label": label, "frequency": frequency, "points": series(fred_id)}
        except Exception as error:
            data["series"][key] = {"label": label, "frequency": frequency, "points": [], "error": str(error)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    main()
