#!/usr/bin/env python3
"""Informe diario basado en las series existentes; no inventa cotizaciones ni noticias."""
import html, json, os, pathlib, smtplib, ssl, urllib.request, xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from news_offline_es import local_news
from render_charts import metrics as chart_metrics, interpretation as trend_interpretation, build_charts
from news_story import official_details
from macro_story import macro_story
from company_pulse import momentum, reading as stock_reading, scenarios as stock_scenarios, company_news_html
from market_top_news import render_top_news
from news_offline_es import local_translation

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "market.json"
OUT = ROOT / "reports" / "wall-street-latest.html"
SEC_DATA = ROOT / "data" / "sec_company_summary.json"
SEC_STATUS = ROOT / "data" / "sec_fetch_status.json"
REFERENCES = ROOT / "data" / "references.json"
BREADTH = ROOT / "data" / "breadth.json"
PRICE_HISTORY = ROOT / "data" / "price_history.json"
COMPANY_NEWS = ROOT / "data" / "company_news.json"
TOP_NEWS = ROOT / "data" / "market_top_news.json"
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
INDICES = [("sp500","S&P 500"),("nasdaq","Nasdaq Composite"),("nasdaq100","Nasdaq 100"),("dow","Dow Jones Industrial Average"),("russell","Russell 2000")]
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
    # Las tarifas administrativas bancarias no son catalizadores relevantes
    # para el mercado global por el simple hecho de proceder de la Fed.
    if any(topic in normalized for topic in (
        "payment services", "check services", "pricing for payment",
        "fees for payment services")):
        return 0
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
    # Solo comunicados con contenido económico identificable. No llenar el
    # informe con notas administrativas ajenas al movimiento de los activos.
    selected=[item for item in unique if news_relevance(item[0])>0][:7]
    enriched=[]
    for i,(title,link,date,description) in enumerate(selected):
        headline=title.split(": ",1)[-1]
        similar=(description[:130].casefold().strip() in headline.casefold() or
                 headline[:100].casefold() in description.casefold())
        if i<5 and (len(description)<180 or similar):
            try:
                details=official_details(link,headline)
                if len(details)>len(description)+60:
                    description=details
            except (OSError,ValueError,UnicodeError) as error:
                print("Texto íntegro no disponible:",type(error).__name__)
        enriched.append((title,link,date,description))
    return enriched

def news_market_context(title):
    """Impacto específico condicionado al hecho; nunca instrucciones editoriales."""
    t=title.casefold()
    if any(s in t for s in ("payment services","check services","pricing","fees")):
        return ("Afecta principalmente a costes de servicios bancarios. "
                "Sin cuantificar las nuevas tarifas no hay evidencia de un impacto "
                "material sobre S&P 500 o Nasdaq 100; catalizador de baja prioridad.")
    if any(s in t for s in ("fomc","interest rate","monetary policy","federal funds")):
        return ("Puede modificar las expectativas sobre tipos de interés, "
                "el precio de los bonos, el dólar y las valoraciones bursátiles. "
                "El efecto concreto depende de la decisión, el tono y las expectativas previas.")
    if any(s in t for s in ("cpi","consumer price","inflation","pce","price index")):
        return ("Un dato de inflación diferente de lo esperado puede cambiar "
                "las expectativas de tipos de la Fed y repercutir en bonos, "
                "acciones y oro. Sin consenso verificable no se infiere la dirección.")
    if any(s in t for s in ("payroll","employment","unemployment","job openings")):
        return ("La fortaleza o debilidad del empleo influye en las expectativas "
                "de actividad económica y política monetaria. El impacto requiere "
                "comparar cifras reales con previsiones y revisiones.")
    if any(s in t for s in ("gdp","gross domestic product","retail sales","consumer spending")):
        return ("Señal sobre crecimiento y consumo. Puede afectar perspectivas "
                "de beneficios, pero el efecto bursátil depende de las sorpresas "
                "frente a las expectativas.")
    if any(s in t for s in ("regulation","fraud","enforcement","securities")):
        return ("Podría afectar directamente a las compañías y actividades "
                "mencionadas en el comunicado; no se extrapola automáticamente "
                "al mercado general.")
    return ("La repercusión financiera no está demostrada con la información "
            "disponible; no se presenta como catalizador bursátil.")


def financial_value(value):
    """Expresar magnitudes contables en millones de dólares."""
    return f'{value / 1_000_000:,.0f} millones USD'

def company_metric_rows(metrics,period="anual"):
    """Solo mostrar magnitudes del mismo ejercicio fiscal, sin cifras antiguas."""
    all_latest=[x[0]["end"] for x in metrics.values() if x]
    if not all_latest:
        return []
    end=max(all_latest)
    chosen={key:next((row for row in rows if row["end"]==end),None)
            for key,rows in metrics.items()}
    rows_html=[]
    for key,label in (("revenue","Ingresos"),("net_income","Beneficio neto"),
                      ("operating_cash","Flujo de caja operativo"),
                      ("capital_expenditure","Inversión en activos fijos")):
        current=chosen.get(key)
        if not current:
            continue
        unit=current.get("currency","USD")
        value=f'{current["value"]/1_000_000:,.0f} millones {unit}'
        all_rows=metrics.get(key,[])
        previous=next((r for r in all_rows if r["end"]!=end and
                       r.get("currency","USD")==unit and
                       330<=(datetime.fromisoformat(end)-datetime.fromisoformat(r["end"])).days<=400),
                      None) if period=="anual" else None
        if previous and previous["value"]>0:
            value+=f'; cambio interanual: {(current["value"]/previous["value"]-1)*100:+.1f}%'
        rows_html.append(f'<li><strong>{esc(label)}:</strong> {esc(value)}</li>')
    rev=chosen.get("revenue")
    profit=chosen.get("net_income")
    cash=chosen.get("operating_cash")
    if rev and rev["value"]>0 and profit and rev.get("currency","USD")==profit.get("currency","USD"):
        margin=100*profit["value"]/rev["value"]
        rows_html.append(f'<li><strong>Margen neto: {margin:.1f}%</strong>. '
                         f'Beneficio de {margin:.1f} por cada 100 {esc(rev.get("currency","USD"))} de ingresos.</li>')
    if cash and profit and profit["value"]>0 and cash.get("currency","USD")==profit.get("currency","USD"):
        coverage=cash["value"]/profit["value"]
        result=("supera" if coverage>=1 else "queda por debajo de")
        rows_html.append(f'<li><strong>Conversión de beneficio en efectivo:</strong> '
                         f'el flujo operativo {result} al beneficio neto (relación {coverage:.2f}x).</li>')
    rows_html.insert(0,f'<li><strong>Periodo comparable:</strong> cierre {esc(end)}.</li>')
    return rows_html

def company_conclusion(metrics):
    rev=metrics.get("revenue",[])
    profit=metrics.get("net_income",[])
    if not rev:
        return "Sin ingresos del último ejercicio comparables: no es responsable concluir si el negocio mejora."
    end=rev[0]["end"]
    profit_current=next((x for x in profit if x["end"]==end),None)
    prev=next((x for x in rev[1:] if 330<=(datetime.fromisoformat(end)-datetime.fromisoformat(x["end"])).days<=400),None)
    if not prev or prev["value"]<=0:
        return "Hay cifras del último ejercicio, pero faltan dos años consecutivos para evaluar crecimiento."
    growth=100*(rev[0]["value"]/prev["value"]-1)
    movement="crecieron" if growth>0 else "retrocedieron" if growth<0 else "se mantuvieron"
    diagnosis=f"Los ingresos {movement} {abs(growth):.1f}% frente al ejercicio anterior."
    if profit_current and rev[0]["value"]>0:
        margin=100*profit_current["value"]/rev[0]["value"]
        diagnosis+=f" El margen neto de este ejercicio fue {margin:.1f}%."
    return diagnosis+" El movimiento bursátil se analiza por separado; los resultados contables no predicen el precio."

def sec_company_html(sec,history=None,chart_keys=None,company_news=None):
    """Acción primero: sesión, semana, catalizadores y escenario técnico.
    Resultados financieros quedan opcionales y secundarios.
    """
    companies=sec.get("companies",{})
    histories=(history or {}).get("assets",{})
    benchmark=histories.get("sp500",{}).get("points",[])
    headlines=(company_news or {}).get("companies",{})
    cards=[]
    for ticker,name in COMPANIES:
        info=companies.get(ticker,{})
        asset=histories.get(ticker,{})
        pulse=momentum(asset.get("points",[]),benchmark)
        content=f'<h3 style="margin:0 0 8px">{esc(name)} ({esc(ticker)})</h3>'
        if pulse:
            content+=('<p><strong>Último cierre:</strong> '
                      f'{pulse["close"]:,.2f} USD · {esc(pulse["date"])}'
                      f' &nbsp; <strong>Última sesión:</strong> {pulse["daily"]:+.2f}%'
                      f' &nbsp; <strong>Últimas 5 sesiones:</strong> {pulse["weekly"]:+.2f}%</p>')
            content+='<p><strong>Qué está haciendo la acción:</strong> '+esc(stock_reading(pulse))+'</p>'
            content+='<p><strong>Escenario condicional:</strong> '+esc(stock_scenarios(pulse))+'</p>'
        else:
            content+='<p>No se obtuvo un histórico reciente suficiente para describir la última sesión y semana.</p>'
        content+=chart_fragment(ticker,history,chart_keys)
        content+=company_news_html(headlines.get(ticker,[]),translator=local_translation,ticker=ticker)
        annual=company_metric_rows(info.get("metrics",{}))
        quarterly=company_metric_rows(info.get("quarterly_metrics",{}),"trimestral") if ticker=="SPCX" else []
        if annual or quarterly:
            content+='<details><summary>Resultados financieros (contexto secundario)</summary>'
            if annual:
                content+='<ul>'+''.join(annual)+'</ul><p>'+esc(company_conclusion(info.get("metrics",{})))+'</p>'
            if quarterly:content+='<ul>'+''.join(quarterly)+'</ul>'
            content+='</details>'
        # No saturar 11 fichas con ausencia repetitiva de datos SEC.
        cards.append('<div style="padding:16px;border:1px solid #dfe5ec;margin:14px 0;border-radius:10px">'
                     +content+'</div>')
    return ''.join(cards)

def data_quality_summary(data, sec=None, news_count=0, sec_status=None):
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
    sec_note=""
    if (sec_status or {}).get("state")=="blocked":
        if sec_status.get("preserved_cached_summary"):
            sec_note=" La consulta SEC actual fue bloqueada (HTTP 403); las cifras conservadas pueden no ser recientes."
        else:
            sec_note=" La consulta SEC actual fue bloqueada (HTTP 403); no se sustituyeron datos ausentes por estimaciones."
    elif (sec_status or {}).get("state")=="not_attempted":
        sec_note=" SEC no se consultó: falta una identificación de aplicación con correo de contacto válido."
    return (
        f"<p>Series FRED consultadas: {len(keys)}; recientes según su frecuencia: {current}; "
        f"antiguas: {old}; sin información: {absent}. "
        f"Empresas con cifras SEC anuales disponibles: {valid_companies} de {len(COMPANIES)}. "
        f"Comunicados oficiales recientes con fecha y enlace: {news_count}. "
        "La cobertura no garantiza exhaustividad ni calidad predictiva."+sec_note+"</p>"
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

def macro_pulse(data):
    """Síntesis del PCE anual sobre variación interanual real, no sobre nivel índice."""
    details=[]
    for key,label in (("pce","Inflación PCE general"),("corepce","Inflación PCE subyacente")):
        series=data.get("series",{}).get(key,{})
        points=series.get("points",[])
        if not points or not is_recent(points[-1]["date"],75):
            continue
        latest=points[-1]
        earlier=next((p for p in reversed(points[:-1]) if
                      p["date"][:7]==f"{int(latest['date'][:4])-1}{latest['date'][4:7]}"),None)
        if not earlier or earlier["value"]<=0:
            continue
        rate=(latest["value"]/earlier["value"]-1)*100
        movement=("por encima" if rate>2 else "por debajo" if rate<2 else "en torno")
        details.append(f'{label}: {rate:.2f}% anual al {latest["date"]}, {movement} '
                       'del objetivo de inflación de 2% de la Fed.')
    if not details:
        return '<p><strong>Lectura macro:</strong> faltan comparaciones interanuales recientes para evaluar la inflación.</p>'
    return ('<div style="padding:14px;background:#f1f5fa;border-radius:9px">'
            '<strong>Qué está pasando con la inflación:</strong> '
            +esc(" ".join(details))
            +'<p><strong>Posible implicación:</strong> una inflación persistentemente superior al 2% '
            'puede dificultar los recortes de tipos, afectando a bonos y valoraciones bursátiles. '
            'Sin la lectura anterior y el consenso no podemos afirmar si sorprendió al mercado.</p></div>')

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
    interpretations=[]
    for key,label in (("sp500","S&P 500"),("nasdaq100","Nasdaq 100")):
        entry=indices.get(key,{})
        if all("ma"+str(n) in entry for n in (20,50,200)):
            short,medium,long=[float(entry["ma"+str(n)]) for n in (20,50,200)]
            if min(short,medium,long)>50:
                reading="participación mayoritaria en los tres plazos"
            elif max(short,medium,long)<50:
                reading="participación minoritaria en los tres plazos"
            else:
                reading="señales mixtas entre corto, mediano y largo plazo"
            near=("; el plazo corto está cerca del equilibrio del 50%" if 45<=short<=55 else "")
            interpretations.append(f'{label}: {reading}{near} (MA20 {short:.1f}%, MA50 {medium:.1f}%, MA200 {long:.1f}%).')
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
            '<p><strong>Conclusión de amplitud:</strong> '
            +esc(" ".join(interpretations) if interpretations else
                 "Los proveedores no entregaron información suficiente para evaluar la participación de las empresas.")
            +'</p><p>Por encima del 50% equivale a mayoría de los valores evaluados, '
            'pero no garantiza movimientos futuros ni supone una señal de compra.</p>')

def chart_fragment(key, history=None, chart_keys=None):
    """Imagen CID incrustada en Gmail, más conclusión calculada con los cierres."""
    asset=(history or {}).get("assets",{}).get(key,{})
    points=asset.get("points",[])
    measure=chart_metrics(points)
    if not measure:
        return '<p style="color:#65758a">Sin precios históricos verificables: no se dibuja una tendencia ficticia.</p>'
    if measure.get("stale"):
        return f'<p>El último cierre ({esc(measure.get("date",""))}) está desactualizado. No se presenta como cotización actual.</p>'
    details=[f'Último cierre: <strong>{measure["close"]:,.2f} {esc(asset.get("unit",""))}</strong> ({esc(measure["date"])})']
    if "change20" in measure:
        details.append(f'Cambio de 20 sesiones: <strong>{measure["change20"]:+.1f}%</strong>')
    for n in (20,50,200):
        if "ma"+str(n) in measure:
            details.append(f'MA{n}: {measure["ma"+str(n)]:,.2f}')
    proxy_warning=('<p style="color:#9b5d18;font-weight:bold">'+esc(asset["proxy"])+'</p>'
                   if asset.get("proxy") else "")
    graphic=(f'<p><img src="cid:radar-{key.lower()}" alt="Gráfico histórico de {esc(key)}" '
             'style="width:100%;max-width:630px;height:auto;border:1px solid #e8edf2"></p>'
             if key in (chart_keys or ()) else '<p>Gráfico no disponible en esta ejecución.</p>')
    url=asset.get("source","")
    source=f'<a href="{esc(url)}">Histórico y fuente</a>' if url.startswith("https://") else ""
    return ('<p>'+' · '.join(details)+'</p>'+proxy_warning+graphic
            +'<p><strong>Qué muestra:</strong> '+esc(trend_interpretation(measure))+'</p>'
            +'<p style="font-size:12px">'+source+'</p>')

def render_market_references(refs,history=None,chart_keys=None):
    """Tres referencias clave, cada una con conclusión y gráfico individual."""
    assets=refs.get("assets",{})
    blocks=[]
    for key,name,context in (
        ("gold","Oro XAU/USD","Activo de referencia de refugio; se compara su propia tendencia, no se deduce miedo a partir de un solo precio."),
        ("wti","Petróleo WTI — Estados Unidos","Referencia de energía que puede presionar costes e inflación; interpretar movimiento de varias sesiones."),
        ("btc","Bitcoin BTC/USDT","Activo digital sensible a la liquidez y al apetito por riesgo; USDT no equivale exactamente a USD.")):
        obj=assets.get(key,{})
        if "value" in obj:
            last=(obj.get("timestamp") or obj.get("date") or "")[:10]
            price=f'{obj["value"]:,.2f} {obj.get("unit","")}'
            latest=f'<p style="font-size:24px;font-weight:bold;margin:8px 0">{esc(price)}</p><p>Referencia: {esc(last)}</p>'
        else:
            latest='<p>Precio actual no disponible en la fuente consultada.</p>'
        blocks.append('<div style="margin:14px 0;padding:18px;border:1px solid #dfe5ec;border-radius:12px">'
                      f'<h3 style="margin:0">{esc(name)}</h3>'+latest+
                      '<p style="color:#455267">'+esc(context)+'</p>'
                      +chart_fragment(key,history,chart_keys)+'</div>')
    return ('<h2>Pulso de los mercados: oro, petróleo WTI y Bitcoin</h2>'
            '<p>Comparaciones de cierre con periodos y horarios distintos. Los gráficos muestran tendencias, '
            'no precios en tiempo real. El petróleo internacional Brent queda excluido.</p>'
            +''.join(blocks))


def render_index_cards(history=None,chart_keys=None):
    """Un gráfico y una conclusión individual por cada índice económico."""
    cards=[]
    for key,name in INDICES:
        cards.append('<div style="padding:16px;border:1px solid #dde5ec;border-radius:10px;margin:12px 0">'
                     +f'<h3 style="margin:0">{esc(name)}</h3>'
                     +chart_fragment(key,history,chart_keys)
                     +'</div>')
    return ''.join(cards)

def executive_summary(data, history=None, market_news=None):
    """Resume hechos de la última sesión disponible, sin convertirlos en pronóstico."""
    assets=(history or {}).get("assets",{})
    moves=[]
    for key,label in (("sp500","S&P 500"),("nasdaq","Nasdaq Composite"),("dow","Dow Jones")):
        points=assets.get(key,{}).get("points",[])
        if len(points)<2:
            continue
        latest,previous=points[-1],points[-2]
        if (latest.get("date","") <= previous.get("date","") or not is_recent(latest["date"],7)
                or not previous.get("close")):
            continue
        change=100*(float(latest["close"])/float(previous["close"])-1)
        moves.append((label,change,latest["date"]))
    if moves:
        session=" · ".join(f"{label} {change:+.2f}% ({date})" for label,change,date in moves)
        gains=sum(change>0 for _,change,_ in moves)
        losses=sum(change<0 for _,change,_ in moves)
        tone=("predominaron avances entre los índices cubiertos" if gains>losses else
              "predominaron descensos entre los índices cubiertos" if losses>gains else
              "la dirección fue mixta entre los índices cubiertos")
        session_text=f"{session}. En esos cierres disponibles, {tone}."
    else:
        session_text="No hay suficientes cierres recientes y verificables para resumir la sesión bursátil."
    series=data.get("series",{})
    risk=[]
    for key,label,limit,suffix in (("vix","VIX",7,""),("treasury10y","Tesoro a 10 años",7,"%"),("credit","diferencial high yield",7," puntos")):
        points=series.get(key,{}).get("points",[])
        if points and is_recent(points[-1]["date"],limit):
            risk.append(f"{label} {float(points[-1]['value']):.2f}{suffix} ({points[-1]['date']})")
    risk_text=(" · ".join(risk) if risk else
               "No hay lecturas recientes verificables de volatilidad, bonos o crédito para contextualizar el riesgo.")
    catalyst_text=(f"Se seleccionaron {len(market_news)} noticias relevantes para seguimiento; su efecto debe comprobarse con la reacción de precios."
                   if market_news else
                   "No se recuperaron catalizadores recientes suficientes para atribuir causas al movimiento.")
    return ('<div style="padding:16px;border:1px solid #cfdbe8;border-radius:10px;background:#f7faff">'
            '<p style="margin:0 0 8px"><strong>Qué hizo el mercado:</strong> '+esc(session_text)+'</p>'
            '<p style="margin:8px 0"><strong>Riesgo y tasas:</strong> '+esc(risk_text)+'.</p>'
            '<p style="margin:8px 0 0"><strong>Catalizadores a vigilar:</strong> '+esc(catalyst_text)+'</p>'
            '</div>')

def macro_asset_chart(history=None, chart_keys=None):
    """Muestra un activo directamente relacionado con la lectura macroeconómica."""
    return ('<div style="margin:16px 0;padding:16px;border:1px solid #dfe5ec;border-radius:10px">'
            '<h3 style="margin-top:0">Activo macro destacado: petróleo WTI</h3>'
            '<p>Su tendencia aporta contexto sobre energía y costes; no demuestra por sí sola una trayectoria de inflación.</p>'
            +chart_fragment("wti",history,chart_keys)+'</div>')

def render(data, sec=None, refs=None, breadth=None, history=None, chart_keys=None, company_news=None, market_news=None, sec_status=None):
    now=datetime.now(ZoneInfo("America/Caracas")).strftime("%d/%m/%Y %H:%M")
    items=[]; flags=[]; news=official_news() if market_news is None else []
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
    companies=sec_company_html(sec or {},history,chart_keys,company_news)
    cleaned_news=[(item[0],item[1],item[2],item[3] if len(item)>3 else "") for item in news]
    try:
        translations=local_news([(title.split(": ",1)[-1],title.split(":",1)[0],description)
                                 for title,link,date,description in cleaned_news])
    except (ImportError,OSError,ValueError,KeyError,TypeError,IndexError) as error:
        translations={}
        print("Traductor local no disponible:",type(error).__name__)
    parts=[]
    for i,(title,link,date,description) in enumerate(cleaned_news):
        agency,_,original_title=title.partition(": ")
        translated=translations.get(i,{})
        spanish_title=(translated.get("title_es") or original_title or title).strip()
        summary=(translated.get("summary_es") or "").strip()
        # Los feeds que solo repiten el titular no aportan un resumen válido.
        simplified=lambda s: "".join(ch for ch in s.casefold() if ch.isalnum())
        repeated=bool(summary) and (simplified(summary) in simplified(spanish_title)
                                      or simplified(spanish_title) in simplified(summary))
        fact=(esc(summary) if summary and not repeated else
              "No se obtuvieron hechos adicionales verificables; el titular por sí solo no permite profundizar.")
        impact=news_market_context(title)
        parts.append('<li style="margin:14px 0;padding:12px;border-bottom:1px solid #e4eaf0">'
                     +f'<strong><a href="{esc(link)}">{esc(spanish_title)}</a></strong>'
                     +f'<p style="color:#687587;font-size:12px;margin:4px 0">{esc(agency)} · {esc(date)}</p>'
                     +'<p><strong>Qué ocurrió:</strong> '+fact+'</p>'
                     +'<p><strong>Por qué importa:</strong> '+esc(impact)+'</p>'
                     +'</li>')
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
    top_news_section=(
        '<h2>Las 5 noticias que pueden mover Wall Street</h2>'
        '<p>Selección editorial de las últimas 24 horas, con catalizadores anteriores '
        'hasta siete días si siguen siendo relevantes. Prioridad sobre 100 puntos '
        'según alcance, relevancia económica, expectativas, actualidad y fiabilidad '
        'de la fuente. No es probabilidad de movimiento ni prueba de causalidad.</p>'
        +render_top_news(market_news,translate_fn=local_translation)
        if market_news is not None else '')
    # Mantener el formato previo solo para funciones y pruebas de compatibilidad.
    legacy_news_section=(
        '<h2>Noticias y catalizadores</h2><p>Comunicados oficiales de Fed, BLS, SEC y BEA '
        'publicados en los últimos cuatro días.</p><ul>'+news_html+'</ul>'
        if market_news is None else '')
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Radar diario de Wall Street</title></head><body style="font:15px/1.55 Arial,sans-serif;color:#172334;max-width:900px;margin:auto;padding:24px"><h1>RADAR DE WALL STREET</h1><p><strong>Edición:</strong> {esc(edition_label(sec or {}))}. Las secciones sin fuentes verificadas se muestran como no disponibles.<br><strong>Fecha de elaboración (Venezuela):</strong> {esc(now)}<br><strong>Fuente de datos:</strong> archivo existente del Observatorio RM, FRED y fuentes originales indicadas en el tablero.</p><h2>Resumen ejecutivo</h2>{executive_summary(data,history,market_news)}{top_news_section}{render_market_references(refs or {},history,chart_keys)}<h2>Diagnóstico cuantitativo del mercado</h2>{market_diagnosis(data)}<h2>Macroeconomía: señales y consecuencias para el mercado</h2>{macro_story(data)}{macro_asset_chart(history,chart_keys)}<p><a href="https://fred.stlouisfed.org/">FRED</a> · <a href="https://www.federalreserve.gov/">Reserva Federal</a> · <a href="https://www.bls.gov/">BLS</a> · <a href="https://www.bea.gov/">BEA</a></p>{render_stock_breadth(breadth or {})}<h2>Índices: tendencia, gráficos y confirmación</h2>{render_index_cards(history,chart_keys)}{index_breadth(data)}<p>Gráficos históricos de índices publicados en FRED, con fecha de cada cierre. Nasdaq Composite es distinto de Nasdaq 100. No se inventan cotizaciones o soportes cuando la fuente no está disponible.</p><h2>Acciones: qué pasó ayer, esta semana y qué puede cambiar</h2><p>Se comparan cierres de la última sesión y de cinco sesiones, tendencia técnica, fuerza frente al S&amp;P 500 (cuando hay cierres coincidentes) y titulares empresariales de siete días. Las noticias son referencias a investigar, no pruebas de causalidad. Resultados contables solo como contexto secundario.</p>{companies}{legacy_news_section}<h2>Escenarios</h2><ul><li><strong>Favorable:</strong> inflación moderándose, rendimientos estables, crédito resistente y mejora de beneficios.</li><li><strong>Neutral:</strong> señales contradictorias entre inflación, empleo, rendimientos y beneficios.</li><li><strong>Adverso:</strong> presión inflacionaria, endurecimiento financiero y deterioro del empleo o beneficios.</li></ul><p>Son condiciones hipotéticas, no probabilidades calculadas.</p><h2>Control de calidad y cobertura</h2>{data_quality_summary(data, sec, len(market_news) if market_news is not None else len(news), sec_status)}<p>{esc(warnings)}</p><p style="font-size:12px;color:#555">Informe informativo; no es recomendación personalizada. Los datos se presentan con su fecha de observación. La disponibilidad y puntualidad dependen de las fuentes públicas.</p></body></html>"""
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

def build_email_message(report, sender, recipient, sec, charts=None):
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
    # Gmail elimina a menudo SVG y URLs externas, pero admite imágenes PNG CID.
    html_part=message.get_body(preferencelist=("html",))
    for key,path in (charts or {}).items():
        if f"cid:radar-{key.lower()}" not in report:
            continue
        with open(path,"rb") as image_file:
            html_part.add_related(image_file.read(),maintype="image",subtype="png",
                                  cid=f"<radar-{key.lower()}>")
    return message

def main():
    if not DATA.exists(): raise SystemExit("No existe data/market.json; ejecutar scripts/update_data.py primero")
    data=json.loads(DATA.read_text(encoding="utf-8"))
    if essential_macro_coverage(data) < 3:
        raise SystemExit("Datos esenciales insuficientes o vencidos: no se enviará un informe potencialmente engañoso")
    sec=json.loads(SEC_DATA.read_text(encoding="utf-8")) if SEC_DATA.exists() else {}
    sec_status=json.loads(SEC_STATUS.read_text(encoding="utf-8")) if SEC_STATUS.exists() else {}
    refs=json.loads(REFERENCES.read_text(encoding="utf-8")) if REFERENCES.exists() else {}
    breadth=json.loads(BREADTH.read_text(encoding="utf-8")) if BREADTH.exists() else {}
    history=json.loads(PRICE_HISTORY.read_text(encoding="utf-8")) if PRICE_HISTORY.exists() else {}
    company_news=json.loads(COMPANY_NEWS.read_text(encoding="utf-8")) if COMPANY_NEWS.exists() else {}
    top_news=json.loads(TOP_NEWS.read_text(encoding="utf-8")).get("items",[]) if TOP_NEWS.exists() else []
    try:
        charts=build_charts(history)
    except (ImportError,RuntimeError,OSError,ValueError) as error:
        print("Gráficos no disponibles:",type(error).__name__)
        charts={}
    report=render(data,sec,refs,breadth,history,charts,company_news,top_news,sec_status); OUT.parent.mkdir(parents=True,exist_ok=True)
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
    msg=build_email_message(report, user, recipient, sec, charts)
    send_email_via_gmail(msg, user, password)
    print("SMTP aceptó el informe para",recipient)

def send_email_via_gmail(message, username, app_password):
    """El servidor SMTP confirma aceptación; la recepción se verifica por separado."""
    with smtplib.SMTP_SSL("smtp.gmail.com", 465,
                          context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(username, app_password)
        smtp.send_message(message)
if __name__=="__main__": main()
