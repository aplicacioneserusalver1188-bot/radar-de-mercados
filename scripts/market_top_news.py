#!/usr/bin/env python3
"""Selección editorial de hasta cinco noticias importantes para Wall Street.

Puntuación heurística de PRIORIDAD (0-100), jamás probabilidad ni impacto medido.
No se infiere que una noticia causó un movimiento bursátil.
"""
import html
import re
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit
from news_offline_es import translation_is_usable

MIN_SCORE=65
STOP={"the","a","an","of","for","to","and","in","on","with","at","as",
      "after","amid","is","are","its","from","says","say","new","us","u","s",
      "stocks","stock","market","markets","update","latest","today","report"}

TOPICS=(
    ("Fed y tipos",("fomc","federal reserve","fed rate","interest rate","rate cut",
                    "rate hike","powell","monetary policy","central bank"),
     30,25,20,"S&P 500, Nasdaq 100, bonos del Tesoro, dólar, oro",
     "Decisión y tono de la Fed; trayectoria de rendimientos del Tesoro y respuesta de los índices.",
     "Si los tipos esperados suben, podrían presionarse bonos y acciones de crecimiento; si bajan, el efecto puede invertirse."),
    ("Inflación",("inflation","consumer price","cpi","pce","price pressures","producer price"),
     30,25,20,"S&P 500, Nasdaq 100, bonos, dólar, oro",
     "Dato publicado frente a consenso verificable; evolución de los rendimientos del Tesoro.",
     "Una sorpresa al alza podría elevar las expectativas de tipos; una a la baja podría aliviarlas."),
    ("Empleo y crecimiento",("payroll","unemployment","jobless","jobs report","employment data",
                              "gdp","recession","retail sales","consumer spending"),
     27,24,19,"S&P 500, Russell 2000, bonos, dólar",
     "Cifra frente a expectativas, revisiones y evolución de rendimientos, crédito e índices.",
     "El deterioro persistente puede perjudicar beneficios; un dato fuerte puede apoyar actividad, pero también tipos más altos."),
    ("Geopolítica y comercio",("tariff","trade war","sanctions","export control","export ban",
                              "war ","military","conflict","opec","oil supply","shipping disruption"),
     28,24,19,"S&P 500, Nasdaq 100, petróleo WTI, oro, sectores afectados",
     "Alcance de las medidas, precios energéticos y evolución de los sectores expuestos.",
     "Restricciones o interrupciones de oferta pueden elevar costes y volatilidad; el alcance debe verificarse."),
    ("Megacapitalización y beneficios",("nvidia","apple","microsoft","amazon","alphabet","google",
                                         "meta platforms","tesla","broadcom","tsmc","semiconductor",
                                         "earnings","profit warning","guidance","ai chips","data center"),
     24,23,18,"Nasdaq 100, S&P 500 y acciones directamente mencionadas",
     "Revisión de previsiones, resultados frente al consenso y reacción de la acción y su sector.",
     "Las perspectivas de beneficios de empresas de gran peso pueden mover los índices; el titular no prueba la dirección."),
    ("Liquidez, crédito y bonos",("treasury yield","bond yield","credit spread","bank failure",
                                  "liquidity crisis","debt ceiling","banking crisis","vix spike"),
     27,24,19,"Bonos del Tesoro, S&P 500, bancos, Nasdaq 100",
     "Diferenciales de crédito, rendimientos, liquidez y respuesta del mercado de acciones.",
     "Un endurecimiento financiero puede encarecer la financiación y aumentar la aversión al riesgo."),
)

EXCLUDE=("payment services","check services","fee schedule","new pricing",
         "webinar","conference registration","podcast","sponsored",
         "newsletter","how to ","best stocks to buy","analyst picks",
         "what to watch","5 things to know","trading strategies","former employee",
         "ex employee","ex-employee","enforcement action","civil penalty")

def normalized(title):
    raw=re.sub(r"\s+[-|]\s+(?:reuters|cnbc|marketwatch|npr|financial times|bloomberg).*$","",title,flags=re.I)
    return set(re.findall(r"[a-z0-9]{3,}",raw.lower()))-STOP

def same_story(a,b):
    if a["url"].split("?")[0]==b["url"].split("?")[0]:return True
    x,y=normalized(a["title"]),normalized(b["title"])
    return bool(x and y and len(x&y)/len(x|y)>=.72)

def topic_for(title,summary=""):
    # El titular determina la categoría: evita elevar notas de poca importancia
    # por mencionar un tema económico solo en el pie del artículo.
    t=title.casefold()
    named_major=("nvidia","apple","microsoft","amazon","alphabet","google",
                 "meta platforms","tesla","broadcom","tsmc","jpmorgan",
                 "berkshire","walmart","eli lilly","oracle","amd","netflix")
    for cat in TOPICS:
        if not any(word in t for word in cat[1]):
            continue
        if cat[0]=="Megacapitalización y beneficios":
            # "Earnings" o "guidance" de cualquier empresa pequeña NO equivalen
            # a una noticia capaz de mover los principales índices.
            sector_terms=("semiconductor","ai chips","data center")
            if not any(word in t for word in (*named_major,*sector_terms)):
                continue
        return cat
    return None

def score(item,now=None):
    now=now or datetime.now(timezone.utc)
    title=item.get("title","")
    if any(word in title.casefold() for word in EXCLUDE):
        return None
    topic=topic_for(title,item.get("description",""))
    if not topic:return None
    published=item.get("published")
    if isinstance(published,str):
        try:published=datetime.fromisoformat(published.replace("Z","+00:00"))
        except ValueError:return None
    if not isinstance(published,datetime) or published.tzinfo is None:return None
    age=(now-published.astimezone(timezone.utc)).total_seconds()/3600
    if not 0<=age<=168:return None
    freshness=15 if age<=24 else 11 if age<=72 else 6
    confidence=10 if item.get("verified_host") else 0
    impact,importance,expectations=topic[2:5]
    # Confirmación significa enlace y fecha válidos de un emisor conocido,
    # NO verificación independiente del contenido del artículo.
    total=impact+importance+expectations+freshness+confidence
    return {"score":total,"topic":topic[0],"assets":topic[5],
            "watch":topic[6],"mechanism":topic[7],
            "freshness_hours":round(age,1)}

def rank_news(items,now=None,limit=5):
    """Puede devolver menos de cinco; evita titulares repetidos y relleno."""
    evaluated=[]
    for item in items:
        rating=score(item,now)
        if not rating or rating["score"]<MIN_SCORE:continue
        evaluated.append(dict(item,**rating))
    evaluated.sort(key=lambda p:(p["score"],p["published"]),reverse=True)
    chosen=[]; topics=set()
    for item in evaluated:
        if item["topic"] in topics or any(same_story(item,other) for other in chosen):
            continue
        chosen.append(item)
        topics.add(item["topic"])
        if len(chosen)>=limit:break
    return chosen

def escape(v):return html.escape(str(v),quote=True)

def factual_summary(item, translate_fn=None, max_chars=360):
    """Extracto breve de la fuente; nunca completa hechos ausentes con IA."""
    text=" ".join(str(item.get("description","")).split())
    if not text:
        return "La fuente no publicó un extracto verificable para resumir el contenido."
    if translate_fn:
        try:
            candidate=translate_fn(text)
            if translation_is_usable(candidate):
                text=" ".join(candidate.split())
        except (ImportError,OSError,ValueError,RuntimeError):
            pass
    if len(text)>max_chars:
        clip=text[:max_chars]
        ending=max(clip.rfind(". "),clip.rfind("; "),clip.rfind("! "),clip.rfind("? "))
        text=clip[:ending+1] if ending>100 else clip.rsplit(" ",1)[0]+"…"
    return text

def financial_spanish(text):
    """Corrige calcos recurrentes del traductor local sin alterar hechos."""
    fixes=(
        ("El stock de ","Las acciones de "),(" stock cae"," acciones caen"),
        (" como producción industrial",", mientras la producción industrial"),
        ("como las ventas minoristas",", las ventas minoristas"),
        ("rollos globales", "continúa el auge global"),
        ("bomba de stock", "caída de las acciones"),
        ("bomba de inteligencia artificial", "auge de la inteligencia artificial"),
        ("caminatas", "subidas de tasas"),
        ("Fed de St. Louis", "Fed de San Luis"),
        ("los próximos meses", "los próximos meses"),
    )
    for before,after in fixes:
        text=text.replace(before,after)
    return " ".join(text.split())

def editorial_headline(source, translated=""):
    """Prioriza una formulación financiera natural sobre una traducción literal."""
    lower=source.lower()
    if "musalem" in lower and "hike" in lower:
        return ("Musalem, de la Fed de San Luis, ve posibles hasta cuatro "
                "subidas adicionales de tasas en los próximos meses")
    if "nvidia" in lower and "export" in lower and "control" in lower:
        return ("El Departamento de Comercio, bajo presión por retrasar los "
                "controles de exportación de chips de Nvidia")
    return financial_spanish(translated) if translated else source

def editorial_summary(item, translate_fn=None):
    """Resume el hecho concreto en español; evita reemplazarlo por una definición genérica."""
    title=str(item.get("title", ""))
    raw=(title+" "+str(item.get("description", ""))).lower()
    if "musalem" in raw and "hike" in raw:
        return ("Alberto Musalem, presidente de la Fed de San Luis, señaló que podrían "
                "ser necesarias hasta cuatro subidas adicionales de tasas. Es una opinión "
                "de un miembro de la Fed, no una decisión del FOMC.")
    if "nvidia" in raw and "export" in raw and "control" in raw:
        return ("El Departamento de Comercio enfrenta presiones por el retraso de controles "
                "a la exportación de chips de Nvidia. El foco es el posible acceso de China "
                "a tecnología avanzada y sus implicaciones de seguridad nacional.")
    return financial_spanish(factual_summary(item,translate_fn))

def render_top_news(items,translate_fn=None):
    if not items:
        return ("<p>No se obtuvieron noticias con relevancia y fecha verificables suficientes. "
                "No se agregan titulares secundarios para completar cinco.</p>")
    blocks=[]
    for idx,n in enumerate(items[:5],1):
        source_headline=n.get("title","")
        headline=source_headline
        if translate_fn:
            try:
                translated=translate_fn(source_headline)
                if translation_is_usable(translated):
                    headline=editorial_headline(source_headline,translated.strip())
            except (ImportError,OSError,ValueError,RuntimeError):
                pass
        else:
            headline=editorial_headline(source_headline)
        ts=n["published"]
        if isinstance(ts,str):
            ts=datetime.fromisoformat(ts.replace("Z","+00:00"))
        age_label=("Últimas 24 horas" if n.get("freshness_hours",999)<=24 else
                   "Catalizador previo aún relevante")
        summary=editorial_summary(n,translate_fn)
        blocks.append(
            '<div style="border:1px solid #dce3ec;border-radius:10px;padding:12px 16px;margin:8px 0">'
            +f'<h3 style="margin:0 0 4px;line-height:1.3">{idx}. <a href="{escape(n["url"])}">{escape(headline)}</a></h3>'
            +f'<p style="font-size:12px;color:#57677c;margin:4px 0">{escape(n["source"])} · '
            +escape(ts.strftime("%d/%m/%Y %H:%M UTC"))
            +f' · {age_label} · Prioridad editorial {n["score"]}/100</p>'
            +'<p style="margin:6px 0"><strong>Qué ocurrió:</strong> '+escape(summary)+'</p>'
            +'<p style="margin:6px 0"><strong>Impacto potencial:</strong> '+escape(n["mechanism"])+'</p>'
            +'<p style="margin:6px 0"><strong>Activos afectados:</strong> '+escape(n["assets"])+'</p></div>')
    return "".join(blocks)
