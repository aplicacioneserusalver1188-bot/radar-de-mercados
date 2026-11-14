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
def esc(v): return html.escape(str(v))
def format_point(p):
    return f"{p['value']:,.2f} ({p['date']})"
def official_news():
    """Últimos comunicados públicos de la Fed, con fecha y enlace; falla de forma segura."""
    url = "https://www.federalreserve.gov/feeds/press_all.xml"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ObservatorioRM/1.0 (public financial news digest)"})
        with urllib.request.urlopen(req, timeout=12) as response:
            root = ET.fromstring(response.read(1_000_000))
        result = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            if not title or not link.startswith("https://www.federalreserve.gov/"):
                continue
            try:
                dt = parsedate_to_datetime(pub).astimezone(timezone.utc)
            except (ValueError, TypeError):
                continue
            if datetime.now(timezone.utc) - dt > timedelta(days=3):
                continue
            result.append((title, link, dt.strftime("%d/%m/%Y %H:%M UTC")))
        return result[:8]
    except (OSError, ET.ParseError, ValueError) as error:
        print("Aviso: feed Fed no disponible:", type(error).__name__)
        return []

def render(data):
    now=datetime.now(ZoneInfo("America/Caracas")).strftime("%d/%m/%Y %H:%M")
    items=[]; flags=[]; news=official_news()
    for key,label,meaning in SERIES:
        obj=data.get("series",{}).get(key,{})
        pts=obj.get("points",[])
        if pts:
            last=pts[-1]; prior=pts[-2] if len(pts)>1 else None
            diff=f"; cambio frente al dato anterior: {last['value']-prior['value']:+,.2f}" if prior else ""
            value=format_point(last)+diff
            if key in ("inflation","pce","corepce","ppi"):
                previous_year=next((p for p in reversed(pts[:-1]) if p["date"][:7]==f"{int(last['date'][:4])-1}{last['date'][4:7]}"),None)
                if previous_year and previous_year["value"]:
                    value+=f"; inflación interanual: {(last['value']/previous_year['value']-1)*100:+.2f}%"
            if key=="treasury10y":
                short=data.get("series",{}).get("treasury2y",{}).get("points",[])
                if short and short[-1]["date"]==last["date"]:
                    value+=f"; diferencial 10a–2a: {last['value']-short[-1]['value']:+.2f} puntos porcentuales"
            if key=="payrolls" and prior:
                value+=f"; variación mensual: {(last['value']-prior['value'])*1000:+,.0f} empleos"
            if (datetime.now(timezone.utc).date()-datetime.fromisoformat(last["date"]).date()).days>45:
                flags.append(label+" presenta observación antigua")
        else:
            value="No disponible"; flags.append(label+" sin datos")
        items.append(f"<tr><th>{esc(label)}</th><td>{esc(value)}</td><td>{esc(meaning)}</td></tr>")
    # No se presentan resultados o perspectivas empresariales sin fuentes actualizadas.
    companies="".join(f'<li><strong>{esc(name)} ({esc(ticker)})</strong>: revisar resultados, guías y valoración en <a href="https://www.sec.gov/edgar/search/">SEC EDGAR</a>. Sin datos financieros verificados en este archivo: perspectiva no determinada.</li>' for ticker,name in COMPANIES)
    news_html = "".join(f'<li><a href="{esc(link)}">{esc(title)}</a> — {esc(date)}. Comunicado oficial; su impacto bursátil requiere contexto.</li>' for title,link,date in news)
    if not news_html:
        news_html="<li>No se recuperaron comunicados recientes verificables de la Reserva Federal.</li>"
    index_rows=[]
    for key,label in INDICES:
        points=data.get("series",{}).get(key,{}).get("points",[])
        if len(points)>=2:
            last,prior=points[-1],points[-2]
            age=(datetime.now(timezone.utc).date()-datetime.fromisoformat(last["date"]).date()).days
            if age>7:
                flags.append(label+" presenta cotización antigua ("+str(age)+" días)")
            change=(last["value"]/prior["value"]-1)*100 if prior["value"] else None
            value=f'{last["value"]:,.2f} ({last["date"]})'
            if change is not None:
                value+=f'; variación entre observaciones: {change:+.2f}%'
        else:
            value="No disponible; verificar cobertura de FRED"
        index_rows.append(f"<tr><th>{esc(label)}</th><td>{esc(value)}</td></tr>")
    warnings="; ".join(flags) if flags else "Sin errores de disponibilidad detectados en las series incluidas."
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Radar diario de Wall Street</title></head><body style="font:15px/1.55 Arial,sans-serif;color:#172334;max-width:900px;margin:auto;padding:24px"><h1>RADAR INTEGRAL DE WALL STREET</h1><p><strong>Fecha de elaboración (Venezuela):</strong> {esc(now)}<br><strong>Fuente de datos:</strong> archivo existente del Observatorio RM, FRED y fuentes originales indicadas en el tablero.</p><h2>Resumen ejecutivo</h2><p>Lectura de los indicadores macroeconómicos disponibles. <strong>No se asigna señal alcista o bajista sin precios bursátiles, expectativas de consenso y contexto de noticias verificados.</strong> Las observaciones tienen distintas frecuencias y fechas; no deben tratarse como valores simultáneos.</p><h2>Macroeconomía, Fed, bonos, crédito y liquidez</h2><table style="border-collapse:collapse;width:100%" border="1" cellpadding="8"><tr><th>Indicador</th><th>Última lectura</th><th>Interpretación económica</th></tr>{''.join(items)}</table><p><a href="https://fred.stlouisfed.org/">FRED</a> · <a href="https://www.federalreserve.gov/">Reserva Federal</a> · <a href="https://www.bls.gov/">BLS</a> · <a href="https://www.bea.gov/">BEA</a></p><h2>Índices y sectores bursátiles</h2><table border="1" cellpadding="8" style="border-collapse:collapse;width:100%"><tr><th>Índice</th><th>Última lectura y cambio</th></tr>{''.join(index_rows)}</table><p>Los datos proceden de las series públicas de FRED, cuando están disponibles. Nasdaq Composite no es Nasdaq 100. La cobertura de sectores y sus cotizaciones sigue pendiente; no se inventan soportes ni liderazgos.</p><h2>Empresas principales: análisis y perspectivas</h2><p>Seguimiento prioritario; se requiere integrar cotizaciones, resultados SEC, consenso y guías para emitir conclusiones empresariales sustentadas.</p><ul>{companies}</ul><h2>Noticias y catalizadores</h2><p>Comunicados oficiales recientes de la Reserva Federal (cuando estén disponibles):</p><ul>{news_html}</ul><p>Esta fuente no sustituye una cobertura completa de prensa económica. Consultar <a href="https://www.reuters.com/markets/us/">Reuters Mercados</a>, <a href="https://www.sec.gov/">SEC</a> y <a href="https://www.federalreserve.gov/newsevents.htm">Fed — comunicados</a>. La versión ampliada deberá incorporar artículos fechados con enlace directo y contraste de fuentes.</p><h2>Escenarios</h2><p><strong>Favorable:</strong> inflación moderándose, rendimientos estables, crédito resistente y mejora de beneficios. <strong>Neutral:</strong> señales contradictorias. <strong>Adverso:</strong> presión inflacionaria, endurecimiento financiero y deterioro del empleo o beneficios. Son condiciones hipotéticas, no probabilidades calculadas.</p><h2>Control de calidad</h2><p>{esc(warnings)}</p><p style="font-size:12px;color:#555">Informe informativo; no es recomendación personalizada. Los datos se presentan con su fecha de observación. La disponibilidad y puntualidad dependen de las fuentes públicas.</p></body></html>"""
def main():
    if not DATA.exists(): raise SystemExit("No existe data/market.json; ejecutar scripts/update_data.py primero")
    data=json.loads(DATA.read_text(encoding="utf-8"))
    if sum(bool(data.get("series",{}).get(key,{}).get("points")) for key in ("inflation","payrolls","treasury10y","vix")) < 3:
        raise SystemExit("Datos esenciales insuficientes: no se enviará un informe potencialmente engañoso")
    report=render(data); OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(report,encoding="utf-8")
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
