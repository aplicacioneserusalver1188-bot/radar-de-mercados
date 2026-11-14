#!/usr/bin/env python3
"""Informe diario basado en las series existentes; no inventa cotizaciones ni noticias."""
import csv, html, io, json, os, pathlib, smtplib, ssl, urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "market.json"
OUT = ROOT / "reports" / "wall-street-latest.html"
SERIES = [
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
COMPANIES = [("NVDA","NVIDIA"),("MSFT","Microsoft"),("AAPL","Apple"),("AMZN","Amazon"),("GOOGL","Alphabet"),("META","Meta"),("AVGO","Broadcom"),("JPM","JPMorgan"),("TSLA","Tesla")]
def esc(v): return html.escape(str(v))
def format_point(p):
    return f"{p['value']:,.2f} ({p['date']})"
def render(data):
    now=datetime.now(ZoneInfo("America/Caracas")).strftime("%d/%m/%Y %H:%M")
    items=[]; flags=[]
    for key,label,meaning in SERIES:
        obj=data.get("series",{}).get(key,{})
        pts=obj.get("points",[])
        if pts:
            last=pts[-1]; prior=pts[-2] if len(pts)>1 else None
            diff=f"; cambio frente al dato anterior: {last['value']-prior['value']:+,.2f}" if prior else ""
            value=format_point(last)+diff
            if (datetime.now(timezone.utc).date()-datetime.fromisoformat(last["date"]).date()).days>45:
                flags.append(label+" presenta observación antigua")
        else:
            value="No disponible"; flags.append(label+" sin datos")
        items.append(f"<tr><th>{esc(label)}</th><td>{esc(value)}</td><td>{esc(meaning)}</td></tr>")
    # No se presentan resultados o perspectivas empresariales sin fuentes actualizadas.
    companies="".join(f'<li><strong>{esc(name)} ({esc(ticker)})</strong>: revisar resultados, guías y valoración en <a href="https://www.sec.gov/edgar/search/">SEC EDGAR</a>. Sin datos financieros verificados en este archivo: perspectiva no determinada.</li>' for ticker,name in COMPANIES)
    warnings="; ".join(flags) if flags else "Sin errores de disponibilidad detectados en las series incluidas."
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Radar diario de Wall Street</title></head><body style="font:15px/1.55 Arial,sans-serif;color:#172334;max-width:900px;margin:auto;padding:24px"><h1>RADAR INTEGRAL DE WALL STREET</h1><p><strong>Fecha de elaboración (Venezuela):</strong> {esc(now)}<br><strong>Fuente de datos:</strong> archivo existente del Observatorio RM, FRED y fuentes originales indicadas en el tablero.</p><h2>Resumen ejecutivo</h2><p>Lectura de los indicadores macroeconómicos disponibles. <strong>No se asigna señal alcista o bajista sin precios bursátiles, expectativas de consenso y contexto de noticias verificados.</strong> Las observaciones tienen distintas frecuencias y fechas; no deben tratarse como valores simultáneos.</p><h2>Macroeconomía, Fed, bonos, crédito y liquidez</h2><table style="border-collapse:collapse;width:100%" border="1" cellpadding="8"><tr><th>Indicador</th><th>Última lectura</th><th>Interpretación económica</th></tr>{''.join(items)}</table><p><a href="https://fred.stlouisfed.org/">FRED</a> · <a href="https://www.federalreserve.gov/">Reserva Federal</a> · <a href="https://www.bls.gov/">BLS</a> · <a href="https://www.bea.gov/">BEA</a></p><h2>Índices y sectores bursátiles</h2><p>S&P 500, Nasdaq 100, Dow Jones, Russell 2000 y sectores: <strong>sin cotizaciones verificadas en el conjunto de datos actual</strong>. No se inventan variaciones, soportes ni liderazgos.</p><h2>Empresas principales: análisis y perspectivas</h2><p>Seguimiento prioritario; se requiere integrar cotizaciones, resultados SEC, consenso y guías para emitir conclusiones empresariales sustentadas.</p><ul>{companies}</ul><h2>Noticias y catalizadores</h2><p>No se incluyen titulares no comprobados. Consultar <a href="https://www.reuters.com/markets/us/">Reuters Mercados</a>, <a href="https://www.sec.gov/">SEC</a> y <a href="https://www.federalreserve.gov/newsevents.htm">Fed — comunicados</a>. La versión ampliada deberá incorporar artículos fechados con enlace directo y contraste de fuentes.</p><h2>Escenarios</h2><p><strong>Favorable:</strong> inflación moderándose, rendimientos estables, crédito resistente y mejora de beneficios. <strong>Neutral:</strong> señales contradictorias. <strong>Adverso:</strong> presión inflacionaria, endurecimiento financiero y deterioro del empleo o beneficios. Son condiciones hipotéticas, no probabilidades calculadas.</p><h2>Control de calidad</h2><p>{esc(warnings)}</p><p style="font-size:12px;color:#555">Informe informativo; no es recomendación personalizada. Los datos se presentan con su fecha de observación. La disponibilidad y puntualidad dependen de las fuentes públicas.</p></body></html>"""
def main():
    if not DATA.exists(): raise SystemExit("No existe data/market.json; ejecutar scripts/update_data.py primero")
    data=json.loads(DATA.read_text(encoding="utf-8"))
    report=render(data); OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(report,encoding="utf-8")
    user=os.getenv("GMAIL_USER"); password=os.getenv("GMAIL_APP_PASSWORD"); recipient=os.getenv("REPORT_TO")
    if not all([user,password,recipient]):
        print("Informe generado en",OUT,"; envío omitido: faltan secretos GMAIL_USER, GMAIL_APP_PASSWORD o REPORT_TO")
        return
    msg=EmailMessage();msg["From"]=user;msg["To"]=recipient;msg["Subject"]="Radar Integral de Wall Street — "+datetime.now(ZoneInfo("America/Caracas")).strftime("%d/%m/%Y")
    msg.set_content("Informe diario de Wall Street en formato HTML adjunto al cuerpo del correo.")
    msg.add_alternative(report,subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com",465,context=ssl.create_default_context(),timeout=30) as smtp:
        smtp.login(user,password);smtp.send_message(msg)
    print("Informe enviado a",recipient)
if __name__=="__main__": main()
