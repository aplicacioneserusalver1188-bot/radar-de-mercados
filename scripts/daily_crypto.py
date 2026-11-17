#!/usr/bin/env python3
"""Radar cripto: datos públicos verificados y correo HTML, sin API de pago."""
import os, html, json, re, ssl, smtplib, pathlib, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEST = ROOT / "reports" / "crypto-latest.html"
FEEDS = [
    ("CriptoNoticias", "https://www.criptonoticias.com/feed/"),
    ("The Block", "https://www.theblock.co/rss.xml"),
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
]
HEADERS = {"User-Agent":"Mozilla/5.0 (compatible; RadarMercados/1.0; news digest)"}
def request(url, timeout=13):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        return resp.read(2_000_000)
def clean(value):
    return re.sub(r"\s+"," ",re.sub(r"<[^>]*>"," ",html.unescape(value or ""))).strip()
def local_text(elem, tag):
    for child in elem:
        if child.tag.rsplit("}",1)[-1]==tag:
            return child.text or ""
    return ""
def feeds():
    now=datetime.now(timezone.utc)
    items=[]; errors=[]
    for outlet,url in FEEDS:
        try:
            root=ET.fromstring(request(url))
            for entry in list(root.iter()):
                if entry.tag.rsplit("}",1)[-1] not in ("item","entry"):
                    continue
                title=clean(local_text(entry,"title"))
                link=local_text(entry,"link").strip()
                if not link:
                    link=next((n.attrib.get("href","") for n in entry if n.tag.rsplit("}",1)[-1]=="link" and n.attrib.get("href")),"")
                date=local_text(entry,"pubDate") or local_text(entry,"published") or local_text(entry,"updated")
                description=clean(local_text(entry,"description") or local_text(entry,"summary"))[:450]
                try:
                    published=parsedate_to_datetime(date) if "," in date else datetime.fromisoformat(date.replace("Z","+00:00"))
                    if published.tzinfo is None: continue
                    age=now-published.astimezone(timezone.utc)
                except (TypeError,ValueError,OverflowError): continue
                if not timedelta(0)<=age<=timedelta(hours=30) or not title or not link.startswith("https://"): continue
                items.append({"title":title,"url":link,"source":outlet,"date":published.astimezone(ZoneInfo("America/Caracas")).strftime("%d/%m %H:%M VET"),"description":description,"ts":published.timestamp()})
        except (OSError,ValueError,ET.ParseError) as ex:
            errors.append(outlet+": "+type(ex).__name__)
    seen=set(); output=[]
    items.sort(key=lambda x:x["ts"],reverse=True)
    for i in items:
        normalized=re.sub(r"[^a-z0-9]","",i["title"].lower())[:90]
        if normalized in seen: continue
        seen.add(normalized);output.append(i)
    # Se da preferencia a CriptoNoticias y a noticias de importancia verificables.
    ranked=sorted(output,key=lambda x:(2 if x["source"]=="CriptoNoticias" else 0)+score(x["title"]),reverse=True)
    return ranked[:10],errors

def score(title):
    t=title.lower()
    return sum((4 if w in ("bitcoin","ethereum","etf","fed","sec") else 2) for w in ("bitcoin","ethereum","etf","fed","sec","liquidat","regul","interest","inflation","cripto","crypto","solana","stablecoin") if w in t)

def market():
    # API pública de CoinGecko. Si falla, informar sin inventar cifras.
    try:
        url=("https://api.coingecko.com/api/v3/coins/markets"
             "?vs_currency=usd&ids=bitcoin,ethereum,solana,ripple&price_change_percentage=24h")
        data=json.loads(request(url,timeout=12))
        return [x for x in data if isinstance(x,dict) and x.get("current_price") is not None],None
    except (OSError,ValueError,TypeError) as ex:
        return [],type(ex).__name__

def angle(title):
    t=title.lower()
    if any(x in t for x in ("etf","fund flows","inflows","outflows","salidas","entradas")):
        return "Los flujos de ETF pueden reflejar cambios en la demanda institucional; una sola sesión no confirma una tendencia."
    if any(x in t for x in ("sec","regula","congress","senate","ley ")):
        return "Las novedades regulatorias pueden modificar costes y acceso al mercado; distinguir propuestas de normas vigentes."
    if any(x in t for x in ("liquidat","leverage","apalanc","futures")):
        return "El apalancamiento puede amplificar movimientos; vigilar cierres forzosos y volatilidad, sin atribuir causalidad automática."
    if any(x in t for x in ("fed","inflation","rates","inflación","dólar")):
        return "Los tipos y la liquidez influyen en el apetito por riesgo; verificar la reacción de mercado antes de concluir su impacto."
    if any(x in t for x in ("ethereum","ether","eth","solana","xrp")):
        return "Evaluar si el desarrollo afecta adopción, oferta o liquidez del activo; el titular por sí solo no prueba efecto en precio."
    return "Es un posible catalizador; comprobar magnitud, confirmación independiente y reacción del precio antes de tomar decisiones."

def reader_context(title):
    """Explica el concepto financiero de la noticia sin inferir una recomendación."""
    t=title.lower()
    if any(x in t for x in ("etf","fund flows","inflows","outflows","salidas","entradas")):
        return ("Un ETF de bitcoin permite obtener exposición al activo mediante participaciones cotizadas. "
                "Las entradas indican creación neta de participaciones y las salidas, rescates netos; ayudan a "
                "medir demanda institucional, pero una sola sesión no determina el próximo precio de BTC.")
    if any(x in t for x in ("liquidat","leverage","apalanc","futures")):
        return ("En derivados, el apalancamiento multiplica tanto ganancias como pérdidas. Cuando una posición no "
                "puede cubrir sus garantías, se liquida de forma automática y puede acelerar temporalmente la caída o el rebote.")
    if any(x in t for x in ("fed","inflation","rates","inflación","dólar")):
        return ("Los tipos de interés cambian el coste de financiarse y el atractivo relativo de activos sin rendimiento, "
                "como bitcoin. Tipos más altos suelen reducir el apetito por riesgo, aunque la reacción depende de las expectativas.")
    if any(x in t for x in ("sec","regula","congress","senate","ley ")):
        return ("Las normas determinan quién puede ofrecer, custodiar o negociar un activo. Una noticia regulatoria "
                "puede afectar expectativas y liquidez, pero conviene separar una propuesta de una regla ya aprobada.")
    if any(x in t for x in ("ethereum","ether","eth","solana","xrp")):
        return ("En criptoactivos distintos de bitcoin, el precio suele depender de uso de la red, actividad de desarrolladores, "
                "liquidez y competencia. El anuncio es contexto; no demuestra por sí solo un cambio de valor o tendencia.")
    return ("La noticia es información de contexto. Para usarla en una decisión conviene contrastarla con el precio, volumen, "
            "liquidez y otras fuentes antes de asumir que cambiará la tendencia.")

def render(items,prices,errors,price_error):
    now=datetime.now(ZoneInfo("America/Caracas")).strftime("%d/%m/%Y %H:%M VET")
    e=html.escape
    css="body{font-family:Arial,sans-serif;color:#1c2836;background:#f5f7fb;margin:0}main{max-width:800px;margin:auto;background:white;padding:26px}h1{color:#142e51}h2{color:#183f64;margin-top:28px}article{border-bottom:1px solid #dfe5ed;padding:12px 0}a{color:#1768ac}small{color:#5c697a}table{border-collapse:collapse;width:100%}td,th{padding:9px;text-align:left;border-bottom:1px solid #dde4ec}.note{background:#eef4fa;padding:14px;border-left:4px solid #28639a}.risk{background:#fff4e8;padding:14px}"
    parts=[f'<html lang="es"><head><meta charset="utf-8"><style>{css}</style></head><body><main>',
           '<h1>Radar Diario Integral de Criptomonedas</h1><p><strong>'+e(now)+'</strong> · Últimas 24–30 horas, según disponibilidad de fuentes.</p>',
           '<div class="note"><strong>Lectura ejecutiva:</strong> Este correo separa hechos publicados, precios observados e interpretaciones. Los titulares enlazados son la fuente; el apartado «Por qué importa» es análisis condicional, no una afirmación causal ni un consejo de inversión.</div>',
           '<h2>Tablero de mercado</h2>']
    if prices:
        parts.append('<table><tr><th>Activo</th><th>Precio USD</th><th>24 h</th></tr>')
        for p in prices:
            change=p.get("price_change_percentage_24h")
            trend=f'{change:+.2f}%' if isinstance(change,(float,int)) else 'No disponible'
            parts.append(f'<tr><td>{e(p.get("name",""))}</td><td>${p["current_price"]:,.2f}</td><td>{e(trend)}</td></tr>')
        parts.append('</table><small>Fuente: CoinGecko API pública. Cotizaciones indicativas al consultar; no son precios ejecutables.</small>')
    else:
        parts.append('<p>Precios no disponibles en la fuente pública. No se sustituyen por cifras estimadas.</p>')
    parts.append('<h2>Noticias verificadas y por qué importan</h2>')
    if not items: parts.append('<p>No se pudieron verificar noticias recientes en los feeds disponibles; el reporte evita inventar titulares.</p>')
    for i,item in enumerate(items,1):
        parts.append(f'<article><h3>{i}. {e(item["title"])}</h3><small>{e(item["source"])} · {e(item["date"])}</small>')
        if item["description"]: parts.append(f'<p><strong>Resumen publicado:</strong> {e(item["description"])}</p>')
        parts.append(f'<p><strong>Cómo leer esta noticia:</strong> {e(reader_context(item["title"]))}</p>')
        parts.append(f'<p><strong>Por qué importa:</strong> {e(angle(item["title"]))}</p>')
        parts.append(f'<p><a href="{e(item["url"],quote=True)}">Leer noticia y verificar fuente</a></p></article>')
    parts.append('<h2>Diagnóstico y escenarios 24–72 horas</h2>')
    btc=next((x for x in prices if x.get("id")=="bitcoin"),None)
    change=btc.get("price_change_percentage_24h") if btc else None
    if isinstance(change,(float,int)):
        state="presión vendedora reciente" if change < -2 else "impulso alcista reciente" if change > 2 else "variación diaria moderada"
        parts.append(f'<p><strong>Dato:</strong> BTC varió {change:+.2f}% en 24 horas. <strong>Interpretación:</strong> {state}; esta variación aislada no confirma el ciclo ni la tendencia de varios días.</p>')
    else: parts.append('<p>Sin cambio de BTC verificado, no se asigna una dirección cuantitativa.</p>')
    parts.extend(['<p><strong>Escenario favorable:</strong> mejoran los precios y se confirma la recuperación con volumen y flujos; condición pendiente de verificar.</p>',
                  '<p><strong>Escenario neutral:</strong> oscilación sin confirmación clara; evitar confundir un rebote con un cambio de tendencia.</p>',
                  '<p><strong>Escenario adverso:</strong> persisten salidas de capital y liquidaciones; aumenta el riesgo de nuevas caídas, sin inferir probabilidades numéricas.</p>',
                  '<div class="risk"><strong>Limitaciones:</strong> no se calculan flujos ETF, liquidaciones ni volumen si no se han recuperado datos homogéneos y verificables. Las noticias no sustituyen los datos. No hay traducción automática de titulares extranjeros; el análisis y las secciones están en español.</div>'])
    if errors or price_error:
        parts.append('<p><small>Fuentes temporalmente no disponibles: '+e("; ".join(errors+(['CoinGecko: '+price_error] if price_error else [])))+'</small></p>')
    parts.append('<p><small>Generado gratuitamente con fuentes públicas. No es asesoría financiera.</small></p></main></body></html>')
    return "".join(parts)

def send(content):
    user=os.environ.get("GMAIL_USER","").strip()
    password=os.environ.get("GMAIL_APP_PASSWORD","").replace(" ","")
    recipient=os.environ.get("REPORT_TO","").strip() or user
    if not user or not password or not recipient:
        raise RuntimeError("Faltan secrets GMAIL_USER, GMAIL_APP_PASSWORD o REPORT_TO")
    message=EmailMessage()
    message["From"]=user
    message["To"]=recipient
    message["Subject"]="Radar Diario de Criptomonedas | "+datetime.now(ZoneInfo("America/Caracas")).strftime("%d/%m/%Y")
    message.set_content("El informe completo está disponible en la versión HTML de este correo.")
    message.add_alternative(content,subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com",465,context=ssl.create_default_context(),timeout=25) as smtp:
        smtp.login(user,password)
        smtp.send_message(message)
    print("Gmail confirmó aceptación del envío SMTP.")

if __name__=="__main__":
    news,errors=feeds()
    prices,price_error=market()
    html_report=render(news,prices,errors,price_error)
    DEST.parent.mkdir(exist_ok=True,parents=True)
    DEST.write_text(html_report,encoding="utf-8")
    print("Reporte generado:",len(news),"noticias,",len(prices),"cotizaciones.")
    if os.getenv("RADAR_DRY_RUN","1")=="0":
        send(html_report)
    else:
        print("Modo prueba: no se envía correo.")
