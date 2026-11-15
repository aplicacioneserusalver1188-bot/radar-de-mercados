#!/usr/bin/env python3
"""Informe diario basado en las series existentes; no inventa cotizaciones ni noticias."""
import html, json, os, pathlib, smtplib, ssl, urllib.request, xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "market.json"
OUT = ROOT / "reports" / "wall-street-latest.html"
SEC_DATA = ROOT / "data" / "sec_company_summary.json"
SERIES = [
 ("pce", "Inflación PCE (nivel del índice)", "Variación interanual del deflactor del consumo personal; referencia clave para la Fed."),
 ("corepce", "PCE subyacente (nivel del índice)", "Excluye alimentos y energía; su variación interanual ayuda a evaluar persistencia de inflación."),
 ("ppi", "Precios al productor (índice de materias primas)", "Señal parcial de presiones de costes; no equivale al PPI de demanda final."),
 ("unemployment", "Tasa de desempleo", "Porcentaje de fuerza laboral sin empleo que busca trabajo."),
 ("gdp", "PIB real", "Actividad económica ajustada por inflación; se publica trimestralmente."),
 ("retail", "Ventas minoristas (nivel)", "Indicador del consumo de bienes; debe distinguirse nivel y crecimiento."),
 ("fedfunds", "Objetivo superior de fondos federales", "Límite superior de la banda objetivo fijada por la Fed."),
 ("treasury2y", "Rendimiento del Tesoro a 2 años", "Muy sensible a expectativas de política monetaria."),
 ("inflation", "Inflación (IPC, nivel del índice)", "La variación interanual permite evaluar presiones de precios; el nivel del índice no es la tasa de inflación."),
 ("payrolls", "Empleo no agrícola (nivel)", "La variación mensual mide creación neta de puestos; el nivel por sí solo no es el cambio."),
 ("claims", "Solicitudes iniciales de desempleo", "Un aumento persistente puede anticipar debilitamiento del mercado laboral."),
 ("treasury10y", "Rendimiento del Tesoro a 10 años", "Puede afectar tasas de descuento y valoraciones de acciones."),
 ("sofr", "SOFR", "Referencia del costo de financiación a corto plazo."),
 ("credit", "Diferencial de crédito de alto rendimiento", "Un diferencial creciente puede indicar mayor percepción de riesgo crediticio."),
 ("vix", "VIX", "Medida de volatilidad implícita; no indica por sí sola dirección."),
 ("nfci", "Condiciones financieras", "Valores más altos suelen indicar condiciones relativamente más restrictivas."),
 ("rrp", "Facilidad de recompra inversa", "Señal de uso de una herramienta de liquidez; no interpretar aisladamente."),
 ("tga", "Cuenta General del Tesoro", "Los movimientos pueden afectar la liquidez del sistema."),
 ("reserves", "Reservas bancarias", "Indicador parcial de liquidez bancaria."),
 ("consumer", "Sentimiento del consumidor", "Contexto para gasto y expectativas de hogares."),
 ("diesel", "Precio minorista del diésel", "Señal parcial de costos energéticos y transporte.")
]
INDICES = [("sp500","S&P 500"),("nasdaq","Nasdaq Composite"),("dow","Dow Jones Industrial Average"),("russell","Russell 2000")]
COMPANIES = [("NVDA","NVIDIA"),("MSFT","Microsoft"),("AAPL","Apple"),("AMZN","Amazon"),("GOOGL","Alphabet"),("META","Meta"),("AVGO","Broadcom"),("JPM","JPMorgan"),("TSLA","Tesla")]
FRESHNESS_LIMITS = {"daily": 7, "weekly": 17, "monthly": 75, "quarterly": 155}
def age_days(date_text):
    return (datetime.now(timezone.utc).date() - datetime.fromisoformat(date_text).date()).days
def freshness_limit(frequency):
    return FRESHNESS_LIMITS.get(frequency, 45)
def is_recent(date_text, limit):
    """Las observaciones futuras o antiguas no son lecturas actuales."""
    return 0 <= age_days(date_text) <= limit
def fred_link(obj, label):
    url = obj.get("source_url", "")
    if not (url.startswith("https://fred.stlouisfed.org/series/") and
            url.removeprefix("https://fred.stlouisfed.org/series/").replace("_", "").isalnum()):
        return esc(label)
    return f'<a href="{esc(url)}">{esc(label)}</a>'
def esc(v): return html.escape(str(v))
def format_point(p):
    return f"{p['value']:,.2f} ({p['date']})"
def official_news():
    """Fecha, fuente y enlace de comunicados reales; jamás fabricar titulares."""
    feeds = (
        ("Reserva Federal", "https://www.federalreserve.gov/feeds/press_all.xml", "www.federalreserve.gov"),
        ("Oficina de Estadísticas Laborales", "https://www.bls.gov/feed/bls_latest.rss", "www.bls.gov"),
        ("SEC", "https://www.sec.gov/news/pressreleases.rss", "www.sec.gov"),
    )
    items = []
    for agency, url, host in feeds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ObservatorioRM/1.0 (financial digest)"})
            with urllib.request.urlopen(req, timeout=12) as response:
                root = ET.fromstring(response.read(1_000_000))
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                published = (item.findtext("pubDate") or "").strip()
                if not title or not link.startswith("https://" + host + "/"):
                    continue
                try:
                    publication = parsedate_to_datetime(published).astimezone(timezone.utc)
                except (ValueError, TypeError, OverflowError):
                    continue
                age = datetime.now(timezone.utc) - publication
                if not timedelta(0) <= age <= timedelta(days=4):
                    continue
                items.append((agency + ": " + title, link,
                              publication.strftime("%d/%m/%Y %H:%M UTC"), publication))
        except (OSError, ET.ParseError, ValueError) as error:
            print("Feed oficial no disponible:", agency, type(error).__name__)
    items.sort(key=lambda row: row[3], reverse=True)
    seen = set()
    unique = []
    for title, link, date, _ in items:
        if link not in seen:
            unique.append((title, link, date))
            seen.add(link)
    return unique[:10]


def sec_company_html(sec):
    companies = sec.get("companies", {})
    blocks = []
    for ticker, name in COMPANIES:
        info = companies.get(ticker, {})
        metrics = info.get("metrics", {})
        rows = []
        for key, label in (("revenue", "Ingresos"), ("net_income", "Beneficio neto"),
                           ("operating_cash", "Flujo de caja operativo"),
                           ("capital_expenditure", "Inversión en inmovilizado")):
            vals = metrics.get(key, [])
            if vals:
                latest = vals[0]
                value = f'{latest["value"]/1e9:,.2f} mil millones USD (ejercicio terminado {latest["end"]})'
                if len(vals) >= 2 and vals[1]["value"] != 0:
                    change = (latest["value"]/vals[1]["value"]-1)*100
                    value += f'; cambio frente a {vals[1]["end"]}: {change:+.1f}%'
                rows.append(f"<li>{esc(label)}: {esc(value)}</li>")
        if rows:
            revenue = metrics.get("revenue", [])
            profit = metrics.get("net_income", [])
            if revenue and profit and revenue[0]["end"] == profit[0]["end"] and revenue[0]["value"] > 0:
                margin = 100 * profit[0]["value"] / revenue[0]["value"]
                rows.append(f"<li>Margen neto calculado: {margin:.1f}% del ingreso fiscal anual</li>")
            src = info.get("source", "https://www.sec.gov/edgar/search/")
            blocks.append(f'<li><strong>{esc(name)} ({esc(ticker)})</strong><ul>{"".join(rows)}</ul><a href="{esc(src)}">Fuente SEC XBRL</a>. Datos contables históricos, no pronóstico.</li>')
        else:
            blocks.append(f'<li><strong>{esc(name)} ({esc(ticker)})</strong>: sin métricas SEC comparables verificadas en esta ejecución.</li>')
    return "<ul>" + "".join(blocks) + "</ul>"


def data_quality_summary(data, sec=None, news_count=0):
    """Informe auditable de cobertura, frescura y límites, no una nota de confianza inventada."""
    series = data.get("series", {})
    keys = [key for key, _, _ in SERIES] + [key for key, _ in INDICES]
    current = old = absent = 0
    for key in keys:
        entry = series.get(key, {})
        points = entry.get("points", [])
        if not points:
            absent += 1
        elif not is_recent(points[-1]["date"], 7 if key in dict(INDICES) else freshness_limit(entry.get("frequency"))):
            old += 1
        else:
            current += 1
    valid_companies = sum(
        bool(info.get("metrics", {}).get("revenue") or info.get("metrics", {}).get("net_income"))
        for info in (sec or {}).get("companies", {}).values()
    )
    return (
        f"<p>Series FRED consultadas: {len(keys)}; recientes según su frecuencia: {current}; "
        f"antiguas: {old}; sin información: {absent}. "
        f"Empresas con cifras SEC anuales disponibles: {valid_companies} de {len(COMPANIES)}. "
        f"Comunicados oficiales recientes con fecha y enlace: {news_count}. "
        "La cobertura no garantiza exhaustividad ni calidad predictiva.</p>"
    )

def market_diagnosis(data):
    series = data.get("series", {})
    lines = []
    def last(key):
        pts = series.get(key, {}).get("points", [])
        return pts[-1] if pts else None
    vix = last("vix")
    if vix and is_recent(vix["date"], 7):
        x = vix["value"]
        label = "alta" if x >= 25 else "moderada" if x < 20 else "intermedia"
        lines.append(f'VIX {x:.2f} ({vix["date"]}): volatilidad implícita {label}; no predice por sí sola si el mercado subirá o bajará.')
    credit = series.get("credit", {}).get("points", [])
    if (len(credit) >= 2 and is_recent(credit[-1]["date"], 7)
            and credit[-2]["date"] < credit[-1]["date"]):
        first, second = credit[-2], credit[-1]
        change = second["value"] - first["value"]
        reading = "aumenta la prima de riesgo" if change > 0 else "disminuye la prima de riesgo" if change < 0 else "permanece estable"
        lines.append(f'Diferencial de crédito {second["value"]:.2f} puntos ({second["date"]}), cambio {change:+.2f}: {reading}.')
    y10, y2 = last("treasury10y"), last("treasury2y")
    if y10 and y2 and y10["date"] == y2["date"] and is_recent(y10["date"], 7):
        spread = y10["value"] - y2["value"]
        reading = "curva invertida, señal histórica de riesgo económico que no fija fechas" if spread < 0 else "curva no invertida, sin garantizar expansión futura"
        lines.append(f'Diferencial Tesoro 10 menos 2 años {spread:+.2f} puntos porcentuales ({y10["date"]}): {reading}.')
    if not lines:
        return "<p>Datos insuficientes para diagnóstico cuantitativo.</p>"
    return "<ul>" + "".join("<li>" + esc(item) + "</li>" for item in lines) + "</ul>"

def index_breadth(data):
    """Resumen descriptivo de índices, no amplitud interna de mercado."""
    up = down = flat = 0
    names = []
    for key, label in INDICES:
        points = data.get("series", {}).get(key, {}).get("points", [])
        if len(points) < 2:
            continue
        latest, previous = points[-1], points[-2]
        if (previous["value"] <= 0 or previous["date"] >= latest["date"]
                or not is_recent(latest["date"], 7)):
            continue
        change = (latest["value"] / previous["value"] - 1) * 100
        names.append(f'{label}: {change:+.2f}% ({latest["date"]})')
        if change > 0.01:
            up += 1
        elif change < -0.01:
            down += 1
        else:
            flat += 1
    if not names:
        return "<p>Sin índices recientes suficientes para comparar movimientos.</p>"
    return ("<p><strong>Balance entre índices disponibles:</strong> " +
            f"{up} al alza, {down} a la baja y {flat} sin cambios significativos. " +
            "No equivale a amplitud del mercado por número de acciones. " +
            esc("; ".join(names)) + ".</p>")

def render(data, sec=None):
    now=datetime.now(ZoneInfo("America/Caracas")).strftime("%d/%m/%Y %H:%M")
    items=[]; flags=[]; news=official_news()
    for key,label,meaning in SERIES:
        obj=data.get("series",{}).get(key,{})
        pts=obj.get("points",[])
        if pts:
            last=pts[-1]; prior=pts[-2] if len(pts)>1 else None
            valid_prior=prior is not None and prior["date"] < last["date"]
            diff=f"; cambio frente al dato anterior: {last['value']-prior['value']:+,.2f}" if valid_prior else ""
            value=format_point(last)+diff
            if key in ("inflation","pce","corepce","ppi"):
                previous_year=next((p for p in reversed(pts[:-1]) if p["date"][:7]==f"{int(last['date'][:4])-1}{last['date'][4:7]}"),None)
                if previous_year and previous_year["value"]:
                    name="variación interanual del índice de materias primas" if key=="ppi" else "inflación interanual"
                    value+=f"; {name}: {(last['value']/previous_year['value']-1)*100:+.2f}%"
            if key=="treasury10y":
                short=data.get("series",{}).get("treasury2y",{}).get("points",[])
                if short and short[-1]["date"]==last["date"]:
                    value+=f"; diferencial 10a–2a: {last['value']-short[-1]['value']:+.2f} puntos porcentuales"
            if key=="payrolls" and valid_prior:
                last_month=int(last["date"][:4])*12+int(last["date"][5:7])
                prior_month=int(prior["date"][:4])*12+int(prior["date"][5:7])
                if last_month-prior_month==1:
                    value+=f"; variación mensual: {(last['value']-prior['value'])*1000:+,.0f} empleos"
            if not is_recent(last["date"], freshness_limit(obj.get("frequency"))):
                flags.append(label+" presenta observación antigua ("+last["date"]+")")
        else:
            value="No disponible"; flags.append(label+" sin datos")
        items.append(f"<tr><th>{fred_link(obj,label)}</th><td>{esc(value)}</td><td>{esc(meaning)}</td></tr>")
    companies=sec_company_html(sec or {})
    news_html = "".join(f'<li><a href="{esc(link)}">{esc(title)}</a> — {esc(date)}. Comunicado oficial; su impacto bursátil requiere contexto.</li>' for title,link,date in news)
    if not news_html:
        news_html="<li>No se recuperaron comunicados verificables recientes de los canales oficiales consultados.</li>"
    index_rows=[]
    for key,label in INDICES:
        points=data.get("series",{}).get(key,{}).get("points",[])
        if len(points)>=2:
            last,prior=points[-1],points[-2]
            age=age_days(last["date"])
            if not is_recent(last["date"], 7):
                flags.append(label+" presenta observación fuera de vigencia ("+str(age)+" días respecto de hoy)")
            valid_dates=prior["date"] < last["date"]
            recent=is_recent(last["date"], 7)
            change=(last["value"]/prior["value"]-1)*100 if recent and valid_dates and prior["value"] > 0 else None
            value=f'{last["value"]:,.2f} ({last["date"]})'
            if not recent:
                value+='; lectura histórica, no cotización vigente'
            elif not valid_dates:
                value+='; variación omitida por fechas inconsistentes'
            if change is not None:
                value+=f'; variación entre observaciones: {change:+.2f}%'
        else:
            value="No disponible; verificar cobertura de FRED"
        index_rows.append(f"<tr><th>{fred_link(data.get('series',{}).get(key,{}),label)}</th><td>{esc(value)}</td></tr>")
    warnings="; ".join(flags) if flags else "Sin errores de disponibilidad detectados en las series incluidas."
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Radar diario de Wall Street</title></head><body style="font:15px/1.55 Arial,sans-serif;color:#172334;max-width:900px;margin:auto;padding:24px"><h1>RADAR INTEGRAL DE WALL STREET</h1><p><strong>Fecha de elaboración (Venezuela):</strong> {esc(now)}<br><strong>Fuente de datos:</strong> archivo existente del Observatorio RM, FRED y fuentes originales indicadas en el tablero.</p><h2>Resumen ejecutivo</h2><p>Lectura de los indicadores macroeconómicos disponibles. <strong>No se asigna señal alcista o bajista sin precios bursátiles, expectativas de consenso y contexto de noticias verificados.</strong> Las observaciones tienen distintas frecuencias y fechas; no deben tratarse como valores simultáneos.</p><h2>Diagnóstico cuantitativo del mercado</h2>{market_diagnosis(data)}<h2>Macroeconomía, Fed, bonos, crédito y liquidez</h2><table style="border-collapse:collapse;width:100%" border="1" cellpadding="8"><tr><th>Indicador</th><th>Última lectura</th><th>Interpretación económica</th></tr>{''.join(items)}</table><p><a href="https://fred.stlouisfed.org/">FRED</a> · <a href="https://www.federalreserve.gov/">Reserva Federal</a> · <a href="https://www.bls.gov/">BLS</a> · <a href="https://www.bea.gov/">BEA</a></p><h2>Índices y sectores bursátiles</h2>{index_breadth(data)}<table border="1" cellpadding="8" style="border-collapse:collapse;width:100%"><tr><th>Índice</th><th>Última lectura y cambio</th></tr>{''.join(index_rows)}</table><p>Los datos proceden de las series públicas de FRED, cuando están disponibles. Nasdaq Composite no es Nasdaq 100. La cobertura de sectores y sus cotizaciones sigue pendiente; no se inventan soportes ni liderazgos.</p><h2>Empresas principales: análisis y perspectivas</h2><p>Hechos contables 10-K, con fecha de ejercicio. Los cambios históricos no son previsiones. Sin cotización y consenso actualizado no se emiten objetivos de precio.</p>{companies}<h2>Noticias y catalizadores</h2><p>Noticias y comunicados oficiales recientes de Fed, BLS y SEC (cuando estén disponibles):</p><ul>{news_html}</ul><p>Estos canales oficiales no sustituyen una cobertura de prensa independiente. Consultar <a href="https://www.reuters.com/markets/us/">Reuters Mercados</a>, <a href="https://www.sec.gov/">SEC</a> y <a href="https://www.federalreserve.gov/newsevents.htm">Fed — comunicados</a>. La versión ampliada deberá incorporar artículos fechados con enlace directo y contraste de fuentes.</p><h2>Escenarios</h2><p><strong>Favorable:</strong> inflación moderándose, rendimientos estables, crédito resistente y mejora de beneficios. <strong>Neutral:</strong> señales contradictorias. <strong>Adverso:</strong> presión inflacionaria, endurecimiento financiero y deterioro del empleo o beneficios. Son condiciones hipotéticas, no probabilidades calculadas.</p><h2>Control de calidad y cobertura</h2>{data_quality_summary(data, sec, len(news))}<p>{esc(warnings)}</p><p style="font-size:12px;color:#555">Informe informativo; no es recomendación personalizada. Los datos se presentan con su fecha de observación. La disponibilidad y puntualidad dependen de las fuentes públicas.</p></body></html>"""
def essential_macro_coverage(data):
    """Requiere al menos tres de cuatro series esenciales con lecturas vigentes."""
    expected = {"inflation": 75, "payrolls": 75, "treasury10y": 7, "vix": 7}
    series = data.get("series", {})
    return sum(
        bool(series.get(key, {}).get("points"))
        and is_recent(series[key]["points"][-1]["date"], limit)
        for key, limit in expected.items()
    )

def main():
    if not DATA.exists(): raise SystemExit("No existe data/market.json; ejecutar scripts/update_data.py primero")
    data=json.loads(DATA.read_text(encoding="utf-8"))
    if essential_macro_coverage(data) < 3:
        raise SystemExit("Datos esenciales insuficientes o vencidos: no se enviará un informe potencialmente engañoso")
    sec=json.loads(SEC_DATA.read_text(encoding="utf-8")) if SEC_DATA.exists() else {}
    report=render(data,sec); OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(report,encoding="utf-8")
    if os.getenv("RADAR_DRY_RUN") == "1":
        print("Prueba de extremo a extremo: informe generado; correo desactivado expresamente")
        return
    valid_companies=sum(bool(info.get("metrics", {}).get("revenue") or info.get("metrics", {}).get("net_income")) for info in sec.get("companies", {}).values())
    if valid_companies < 3:
        raise SystemExit("ENVÍO CANCELADO: información empresarial SEC insuficiente (menos de tres empresas con cifras anuales)")
    user=os.getenv("GMAIL_USER"); password=os.getenv("GMAIL_APP_PASSWORD"); recipient=os.getenv("REPORT_TO")
    if not all([user,password,recipient]):
        raise SystemExit("Informe generado, pero ENVÍO NO REALIZADO: configurar secretos GMAIL_USER, GMAIL_APP_PASSWORD y REPORT_TO")
    msg=EmailMessage();msg["From"]=user;msg["To"]=recipient;msg["Subject"]="Radar Integral de Wall Street — "+datetime.now(ZoneInfo("America/Caracas")).strftime("%d/%m/%Y")
    msg.set_content("Informe diario de Wall Street en formato HTML adjunto al cuerpo del correo.")
    msg.add_alternative(report,subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com",465,context=ssl.create_default_context(),timeout=30) as smtp:
        smtp.login(user,password);smtp.send_message(msg)
    print("Informe enviado a",recipient)
if __name__=="__main__": main()
