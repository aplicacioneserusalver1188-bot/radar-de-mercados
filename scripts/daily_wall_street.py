#!/usr/bin/env python3
"""Informe diario basado en las series existentes; no inventa cotizaciones ni noticias."""
import html, json, os, pathlib, smtplib, ssl, urllib.request, xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from news_spanish import summarize_news

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "market.json"
OUT = ROOT / "reports" / "wall-street-latest.html"
SEC_DATA = ROOT / "data" / "sec_company_summary.json"
REFERENCES = ROOT / "data" / "references.json"
BREADTH = ROOT / "data" / "breadth.json"
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
COMPANIES = [("NVDA","NVIDIA"),("MSFT","Microsoft"),("AAPL","Apple"),("AMZN","Amazon"),("GOOGL","Alphabet"),("META","Meta"),("AVGO","Broadcom"),("JPM","JPMorgan"),("TSLA","Tesla"),("TSM","Taiwan Semiconductor (TSMC)"),("SPCX","SpaceX")]
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
def parse_official_feed(payload, agency, host, now=None, with_description=False):
    """Extrae solo comunicados fechados con enlaces HTTPS del dominio oficial."""
    root = ET.fromstring(payload)
    trusted_hosts = (host,) if isinstance(host, str) else tuple(host)
    current = now or datetime.now(timezone.utc)
    rows = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        date_text = (item.findtext("pubDate") or "").strip()
        description = (item.findtext("description") or "").strip()
        rows.append((title, url, date_text, "rss", description))
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    for item in root.findall(".//atom:entry", namespace):
        title = (item.findtext("atom:title", default="", namespaces=namespace) or "").strip()
        links = item.findall("atom:link", namespace)
        url = next((link.get("href", "") for link in links
                    if link.get("rel", "alternate") == "alternate"), "")
        date_text = (item.findtext("atom:published", default="", namespaces=namespace)
                     or item.findtext("atom:updated", default="", namespaces=namespace) or "").strip()
        summary = (item.findtext("atom:summary", default="", namespaces=namespace) or "").strip()
        rows.append((title, url, date_text, "atom", summary))
    valid = []
    for title, url, date_text, format_name, description in rows:
        location = urlsplit(url)
        if not title or location.scheme != "https" or location.hostname not in trusted_hosts:
            continue
        try:
            publication = (parsedate_to_datetime(date_text) if format_name == "rss"
                           else datetime.fromisoformat(date_text.replace("Z", "+00:00")))
            if publication.tzinfo is None:
                continue
            publication = publication.astimezone(timezone.utc)
        except (ValueError, TypeError, OverflowError):
            continue
        age = current - publication
        if not timedelta(0) <= age <= timedelta(days=4):
            continue
        row=(agency + ": " + title, url,
             publication.strftime("%d/%m/%Y %H:%M UTC"), publication)
        if with_description:
            # No se confía en HTML incluido en feeds ajenos.
            import re
            description=re.sub(r"<[^>]*>", " ", html.unescape(description))
            description=" ".join(description.split())[:1100]
            row += (description,)
        valid.append(row)
    return valid


def news_relevance(title):
    """Orden editorial por temas económicos, sin presumir impacto de mercado."""
    normalized = title.casefold()
    important = ("fomc", "monetary policy", "interest rate", "inflation", "consumer price",
                 "cpi", "pce", "payroll", "employment", "unemployment", "gdp",
                 "gross domestic product", "personal income", "retail sales",
                 "economic growth", "job openings", "política monetaria", "inflación")
    adjacent = ("financial stability", "credit", "treasury", "bank", "securities",
                "financial market", "economy", "trade", "regulation")
    if any(term in normalized for term in important):
        return 2
    if any(term in normalized for term in adjacent):
        return 1
    return 0

def official_news():
    """Fecha, fuente y enlace de comunicados reales; jamás fabricar titulares."""
    feeds = (
        ("Reserva Federal", "https://www.federalreserve.gov/feeds/press_all.xml", "www.federalreserve.gov"),
        ("Oficina de Estadísticas Laborales", "https://www.bls.gov/feed/bls_latest.rss", "www.bls.gov"),
        ("SEC", "https://www.sec.gov/news/pressreleases.rss", "www.sec.gov"),
        ("Oficina de Análisis Económico (BEA)", "https://apps.bea.gov/rss/rss.xml",
         ("www.bea.gov", "bea.gov", "apps.bea.gov")),
    )
    items = []
    for agency, url, host in feeds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ObservatorioRM/1.0 (financial digest)"})
            with urllib.request.urlopen(req, timeout=12) as response:
                payload = response.read(1_000_000)
            items.extend(parse_official_feed(payload, agency, host, with_description=True))
        except (OSError, ET.ParseError, ValueError) as error:
            print("Feed oficial no disponible:", agency, type(error).__name__)
    items.sort(key=lambda row: (news_relevance(row[0]), row[3]), reverse=True)
    seen = set()
    unique = []
    for title, link, date, _, description in items:
        if link not in seen:
            unique.append((title, link, date, description))
            seen.add(link)
    return unique[:10]

def news_market_context(title):
    """Contexto condicional por palabras del titular; no deduce el resultado del comunicado."""
    headline = title.casefold()
    categories = (
        (("federal funds", "interest rate", "fomc", "monetary policy", "tasas de interés", "política monetaria"),
         "Política monetaria: contrastar la decisión o el tono del comunicado con las expectativas previas. Puede influir en rendimientos, dólar y valoración de acciones."),
        (("consumer price", "cpi", "inflation", "personal consumption expenditures", "pce", "precios al consumidor", "inflación"),
         "Inflación: comparar el dato publicado con el consenso y la lectura anterior. Su sorpresa puede modificar las expectativas de tipos de interés."),
        (("employment", "payroll", "job openings", "unemployment", "labor market", "empleo", "desempleo"),
         "Empleo: evaluar creación de puestos, desempleo y revisiones frente al consenso. La interpretación depende de su efecto sobre actividad e inflación."),
        (("gross domestic product", "gdp", "retail sales", "economic activity", "producto interno bruto", "ventas minoristas"),
         "Actividad: comparar el crecimiento y las revisiones con las previsiones. Un dato aislado no determina la dirección del mercado."),
        (("enforcement", "securities", "fraud", "litigation", "disclosure", "regulation", "regulación", "sanción"),
         "Regulación: identificar empresas y normas realmente afectadas antes de inferir repercusiones bursátiles."),
    )
    for terms, explanation in categories:
        if any(term in headline for term in terms):
            return explanation
    return ("Comunicado institucional: examinar el texto original, su alcance y la reacción observada. "
            "El titular por sí solo no permite cuantificar un impacto en bolsa.")

def financial_value(value):
    """Expresar magnitudes contables en millones de dólares."""
    return f'{value / 1_000_000:,.0f} millones USD'

def company_metric_rows(metrics, period="anual"):
    rows=[]
    currency=None
    for key,label in (("revenue","Ingresos"),("net_income","Beneficio neto"),
                      ("operating_cash","Flujo de caja operativo"),
                      ("capital_expenditure","Inversión en activos fijos")):
        vals=metrics.get(key,[])
        if not vals: continue
        latest=vals[0]
        unit=latest.get("currency","USD")
        currency=currency or unit
        amount=f'{latest["value"]/1_000_000:,.0f} millones {unit}'
        value=f'{amount} (periodo terminado {latest["end"]})'
        if len(vals)>=2 and vals[1]["value"] and vals[1].get("currency","USD")==unit:
            change=(latest["value"]/vals[1]["value"]-1)*100
            value+=f'; variación entre periodos disponibles: {change:+.1f}%'
        rows.append(f'<li><strong>{esc(label)}:</strong> {esc(value)}</li>')
    revenue=metrics.get("revenue",[])
    profit=metrics.get("net_income",[])
    if revenue and profit and revenue[0]["end"]==profit[0]["end"] and revenue[0]["value"]>0:
        if revenue[0].get("currency","USD")==profit[0].get("currency","USD"):
            margin=100*profit[0]["value"]/revenue[0]["value"]
            unit=revenue[0].get("currency","USD")
            rows.append(f'<li><strong>Margen neto calculado: {margin:.1f}%</strong>. '
                        f'De cada 100 {esc(unit)} de ingresos quedan aproximadamente '
                        f'{margin:.1f} {esc(unit)} de beneficio neto.</li>')
    return rows

def sec_company_html(sec):
    companies=sec.get("companies",{})
    blocks=[]
    for ticker,name in COMPANIES:
        info=companies.get(ticker,{})
        annual=company_metric_rows(info.get("metrics",{}))
        quarterly=company_metric_rows(info.get("quarterly_metrics",{})) if ticker=="SPCX" else []
        if annual or quarterly:
            src=info.get("source","https://www.sec.gov/edgar/search/")
            sections=[]
            if annual: sections.append('<strong>Cifras anuales:</strong><ul>'+''.join(annual)+'</ul>')
            if quarterly: sections.append('<strong>Cifras trimestrales (10-Q, periodos de tres meses):</strong><ul>'+''.join(quarterly)+'</ul>')
            caveat=(' Cifras en TWD si la fuente publica estados IFRS en dólares taiwaneses; no son USD.'
                    if ticker=="TSM" else
                    ' Las cifras trimestrales no equivalen a resultados anuales.'
                    if ticker=="SPCX" else '')
            blocks.append(f'<li><strong>{esc(name)} ({esc(ticker)})</strong>'
                          +''.join(sections)+f'<a href="{esc(src)}">Fuente SEC XBRL</a>. '
                          +'Datos históricos, no pronósticos.'+esc(caveat)+'</li>')
        else:
            explanation=("TSMC declara mediante 20-F/IFRS; no hubo cifras comparables accesibles." if ticker=="TSM"
                         else "SpaceX presenta 10-Q, pero sus datos trimestrales no estaban disponibles o completos." if ticker=="SPCX"
                         else "La SEC no entregó información financiera verificable en esta ejecución.")
            blocks.append(f'<li><strong>{esc(name)} ({esc(ticker)})</strong>: sin métricas anuales verificadas. {esc(explanation)}</li>')
    return "<ul>"+"".join(blocks)+"</ul>"

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
        return "<p>Datos insuficientes para diagnóstico cuantitativo.</p><p><strong>Conclusión:</strong> Faltan indicadores recientes para determinar el estado del mercado.</p>"
    observations=[]
    if vix and is_recent(vix["date"],7):
        observations.append("volatilidad alta" if vix["value"]>=25 else "volatilidad intermedia" if vix["value"]>=20 else "volatilidad moderada")
    if len(credit)>=2 and is_recent(credit[-1]["date"],7) and credit[-2]["date"]<credit[-1]["date"]:
        observations.append("más tensión crediticia" if credit[-1]["value"]>credit[-2]["value"] else "sin aumento de tensión crediticia")
    if y10 and y2 and y10["date"]==y2["date"] and is_recent(y10["date"],7):
        observations.append("curva de bonos invertida" if y10["value"]<y2["value"] else "curva de bonos no invertida")
    summary="; ".join(observations).capitalize()
    return ("<ul>" + "".join("<li>" + esc(item) + "</li>" for item in lines) + "</ul>"
            + "<p><strong>Conclusión de los indicadores:</strong> " + esc(summary)
            + ". Es una lectura de condiciones financieras; no determina por sí sola la dirección futura de las acciones.</p>")

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

def render_stock_breadth(breadth):
    """SMA: porcentaje de componentes sobre su propia media móvil simple."""
    indices=breadth.get("indices",{})
    rows=[]
    for key,label in (("sp500","S&P 500"),("nasdaq100","Nasdaq 100")):
        entry=indices.get(key,{})
        if all("ma"+str(n) in entry for n in (20,50,200)):
            values=[]
            for n in (20,50,200):
                values.append(f'{entry["ma"+str(n)]:.1f}%')
            source=entry.get("source","")
            link=f'<a href="{esc(source)}">Fuente y metodología</a>' if source.startswith("https://") else ""
            rows.append(f'<tr><th>{esc(label)}</th><td>{values[0]}</td><td>{values[1]}</td>'
                        f'<td>{values[2]}</td><td>{esc(entry.get("date",""))} {link}</td></tr>')
        else:
            rows.append(f'<tr><th>{esc(label)}</th><td colspan="4">No disponible: '
                        'no se obtuvo una lectura reciente y verificable con las tres medias móviles.</td></tr>')
    return ('<h2>Amplitud: empresas por encima de sus medias móviles</h2>'
            '<p>Porcentaje de valores elegibles que cotizan sobre su propia media móvil simple (SMA). '
            'MA20 = corto plazo; MA50 = tendencia intermedia; MA200 = tendencia de largo plazo. '
            'No es la media móvil del índice: se evalúan sus empresas por separado. '
            'Las cifras no proceden de los administradores de los índices y dependen de la cobertura del proveedor.</p>'
            '<table border="1" cellpadding="8"><tr><th>Índice</th><th>MA20</th><th>MA50</th><th>MA200</th>'
            '<th>Fecha y fuente</th></tr>'+"".join(rows)+'</table>'
            '<p>Un porcentaje superior a 50% significa que la mayoría de los valores evaluados está '
            'sobre esa media. No es garantía de tendencia futura ni señal automática de compra.</p>')

def render_market_references(refs):
    """Tabla con unidades, fecha y límites de actualidad de cada mercado."""
    assets=refs.get("assets",{})
    rows=[]
    for key,label,context in (
        ("gold","Oro XAU/USD","Referencia de refugio y tipos reales; no implica alza de acciones."),
        ("wti","Petróleo WTI","Energía de EE. UU.; puede influir en expectativas de inflación."),
        ("brent","Petróleo Brent","Referencia internacional de petróleo; refleja tensiones de oferta y demanda."),
        ("btc","Bitcoin BTC/USDT","Mercado de criptomonedas; par cotizado contra USDT, no USD.")):
        obj=assets.get(key,{})
        if not isinstance(obj,dict) or "value" not in obj:
            value="No disponible: fuente sin datos verificables"
            source=""
        else:
            date_text=obj.get("timestamp",obj.get("date",""))
            try:
                measured=datetime.fromisoformat(date_text.replace("Z","+00:00"))
                if measured.tzinfo is None: measured=measured.replace(tzinfo=timezone.utc)
                age=(datetime.now(timezone.utc)-measured.astimezone(timezone.utc)).total_seconds()
                recent=0<=age<=(86400*7 if key in ("wti","brent") else 86400)
            except ValueError:
                recent=False
            value=f'{obj["value"]:,.2f} {obj.get("unit","")} (dato: {date_text})'
            if not recent: value+="; dato histórico o sin vigencia confirmada"
            if key=="btc" and recent and "change_24h" in obj:
                value+=f'; variación móvil 24 h: {obj["change_24h"]:+.2f}%'
            if key in ("wti","brent") and recent and obj.get("previous") and obj["previous"]["value"]>0:
                pct=(obj["value"]/obj["previous"]["value"]-1)*100
                value+=f'; variación entre observaciones: {pct:+.2f}%'
            url=obj.get("source","")
            source=f' <a href="{esc(url)}">Fuente</a>' if url.startswith("https://") else ""
        rows.append(f"<tr><th>{esc(label)}</th><td>{esc(value)}{source}</td><td>{esc(context)}</td></tr>")
    return ('<h2>Tablero de referencia: oro, petróleo y Bitcoin</h2>'
            '<p>Precios de fuentes independientes y horarios diferentes. No representan un cierre simultáneo.'
            ' WTI y Brent se publican con retraso; Bitcoin es BTC/USDT, distinto de BTC/USD.</p>'
            '<table border="1" cellpadding="8"><tr><th>Activo</th><th>Referencia</th><th>Interpretación</th></tr>'
            + "".join(rows) + "</table>")

def render(data, sec=None, refs=None, breadth=None):
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
    cleaned_news=[(item[0],item[1],item[2],item[3] if len(item)>3 else "") for item in news]
    try:
        summaries=summarize_news([(title.split(": ",1)[-1],title.split(":",1)[0],description)
                                  for title,link,date,description in cleaned_news])
    except (OSError,ValueError,KeyError,TypeError,IndexError) as error:
        summaries={}
        print("Síntesis automática no disponible:",type(error).__name__)
    parts=[]
    for i,(title,link,date,description) in enumerate(cleaned_news):
        summary=summaries.get(i)
        fact=("<strong>Resumen en español (síntesis automática):</strong> "+esc(summary)
              if summary else "<strong>Resumen factual en español:</strong> No disponible sin análisis de la fuente original; no se inventan detalles.")
        parts.append(f'<li><a href="{esc(link)}">{esc(title)}</a> — {esc(date)}. '
                     +fact+f' <strong>Impacto potencial:</strong> {esc(news_market_context(title))}</li>')
    news_html="".join(parts)
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
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Radar diario de Wall Street</title></head><body style="font:15px/1.55 Arial,sans-serif;color:#172334;max-width:900px;margin:auto;padding:24px"><h1>RADAR DE WALL STREET</h1><p><strong>Edición:</strong> {esc(edition_label(sec or {}))}. Las secciones sin fuentes verificadas se muestran como no disponibles.<br><strong>Fecha de elaboración (Venezuela):</strong> {esc(now)}<br><strong>Fuente de datos:</strong> archivo existente del Observatorio RM, FRED y fuentes originales indicadas en el tablero.</p><h2>Resumen ejecutivo</h2><p>Lectura de los indicadores macroeconómicos disponibles. <strong>No se asigna señal alcista o bajista sin precios bursátiles, expectativas de consenso y contexto de noticias verificados.</strong> Las observaciones tienen distintas frecuencias y fechas; no deben tratarse como valores simultáneos.</p>{render_market_references(refs or {})}<h2>Diagnóstico cuantitativo del mercado</h2>{market_diagnosis(data)}<h2>Macroeconomía, Fed, bonos, crédito y liquidez</h2><table style="border-collapse:collapse;width:100%" border="1" cellpadding="8"><tr><th>Indicador</th><th>Última lectura</th><th>Interpretación económica</th></tr>{''.join(items)}</table><p><a href="https://fred.stlouisfed.org/">FRED</a> · <a href="https://www.federalreserve.gov/">Reserva Federal</a> · <a href="https://www.bls.gov/">BLS</a> · <a href="https://www.bea.gov/">BEA</a></p>{render_stock_breadth(breadth or {})}<h2>Índices y sectores bursátiles</h2>{index_breadth(data)}<table border="1" cellpadding="8" style="border-collapse:collapse;width:100%"><tr><th>Índice</th><th>Última lectura y cambio</th></tr>{''.join(index_rows)}</table><p>Los datos proceden de las series públicas de FRED, cuando están disponibles. Nasdaq Composite no es Nasdaq 100. La cobertura de sectores y sus cotizaciones sigue pendiente; no se inventan soportes ni liderazgos.</p><h2>Empresas principales: análisis y perspectivas</h2><p>Hechos contables 10-K, con fecha de ejercicio. Los cambios históricos no son previsiones. Sin cotización y consenso actualizado no se emiten objetivos de precio.</p>{companies}<h2>Noticias y catalizadores</h2><p>Comunicados oficiales de Fed, BLS, SEC y BEA publicados en los últimos cuatro días, cuando sus canales están disponibles:</p><ul>{news_html}</ul><p>Estos canales oficiales no sustituyen una cobertura de prensa independiente. Consultar <a href="https://www.reuters.com/markets/us/">Reuters Mercados</a>, <a href="https://www.sec.gov/">SEC</a> y <a href="https://www.federalreserve.gov/newsevents.htm">Fed — comunicados</a>. La versión ampliada deberá incorporar artículos fechados con enlace directo y contraste de fuentes.</p><h2>Escenarios</h2><ul><li><strong>Favorable:</strong> inflación moderándose, rendimientos estables, crédito resistente y mejora de beneficios.</li><li><strong>Neutral:</strong> señales contradictorias entre inflación, empleo, rendimientos y beneficios.</li><li><strong>Adverso:</strong> presión inflacionaria, endurecimiento financiero y deterioro del empleo o beneficios.</li></ul><p>Son condiciones hipotéticas, no probabilidades calculadas.</p><h2>Control de calidad y cobertura</h2>{data_quality_summary(data, sec, len(news))}<p>{esc(warnings)}</p><p style="font-size:12px;color:#555">Informe informativo; no es recomendación personalizada. Los datos se presentan con su fecha de observación. La disponibilidad y puntualidad dependen de las fuentes públicas.</p></body></html>"""
def essential_macro_coverage(data):
    """Requiere al menos tres de cuatro series esenciales con lecturas vigentes."""
    expected = {"inflation": 75, "payrolls": 75, "treasury10y": 7, "vix": 7}
    series = data.get("series", {})
    return sum(
        bool(series.get(key, {}).get("points"))
        and is_recent(series[key]["points"][-1]["date"], limit)
        for key, limit in expected.items()
    )

def annual_company_coverage(sec):
    """Número de empresas con información anual para mostrar, nunca inventada."""
    return sum(
        bool(info.get("metrics", {}).get("revenue") or info.get("metrics", {}).get("net_income"))
        for info in sec.get("companies", {}).values()
    )

def edition_label(sec):
    return ("edición macroeconómica; cobertura empresarial pendiente"
            if annual_company_coverage(sec) < 3 else
            "edición con información empresarial parcial")

def build_email_message(report, sender, recipient, sec):
    """Construir el correo sin acceder a red ni afirmar entrega."""
    edition = edition_label(sec)
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = ("Radar de Wall Street (" + edition + ") — " +
                          datetime.now(ZoneInfo("America/Caracas")).strftime("%d/%m/%Y"))
    message.set_content("Edición: " + edition +
                        ". Los datos ausentes y las limitaciones se indican en el informe HTML.")
    message.add_alternative(report, subtype="html")
    return message

def main():
    if not DATA.exists(): raise SystemExit("No existe data/market.json; ejecutar scripts/update_data.py primero")
    data=json.loads(DATA.read_text(encoding="utf-8"))
    if essential_macro_coverage(data) < 3:
        raise SystemExit("Datos esenciales insuficientes o vencidos: no se enviará un informe potencialmente engañoso")
    sec=json.loads(SEC_DATA.read_text(encoding="utf-8")) if SEC_DATA.exists() else {}
    refs=json.loads(REFERENCES.read_text(encoding="utf-8")) if REFERENCES.exists() else {}
    breadth=json.loads(BREADTH.read_text(encoding="utf-8")) if BREADTH.exists() else {}
    report=render(data,sec,refs,breadth); OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(report,encoding="utf-8")
    if os.getenv("RADAR_DRY_RUN") == "1":
        print("Prueba de extremo a extremo: informe generado; correo desactivado expresamente")
        return
    # Si la SEC bloquea el acceso, se puede remitir la edición macroeconómica
    # con advertencias explícitas en vez de dejar sin informe al destinatario.
    edition=edition_label(sec)
    if annual_company_coverage(sec) < 3:
        print("Aviso: fuentes empresariales insuficientes; se enviaría edición macroeconómica identificada como parcial.")
    user=os.getenv("GMAIL_USER"); password=os.getenv("GMAIL_APP_PASSWORD"); recipient=os.getenv("REPORT_TO")
    if not all([user,password,recipient]):
        raise SystemExit("Informe generado, pero ENVÍO NO REALIZADO: configurar secretos GMAIL_USER, GMAIL_APP_PASSWORD y REPORT_TO")
    msg=build_email_message(report, user, recipient, sec)
    send_email_via_gmail(msg, user, password)
    print("SMTP aceptó el informe para",recipient)

def send_email_via_gmail(message, username, app_password):
    """El servidor SMTP confirma aceptación; la recepción se verifica por separado."""
    with smtplib.SMTP_SSL("smtp.gmail.com", 465,
                          context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(username, app_password)
        smtp.send_message(message)
if __name__=="__main__": main()
