#!/usr/bin/env python3
"""Señales de 1 y 5 sesiones para acciones, sin inferir causalidad de titulares."""
import html
from render_charts import metrics, interpretation
from news_offline_es import translation_is_usable

def e(value):return html.escape(str(value))
def momentum(points,benchmark=None):
    if not points or len(points)<6:return {}
    chart=metrics(points)
    if not chart or chart.get("stale"):return {}
    if not all(p["close"]>0 for p in points[-6:]):return {}
    close=float(points[-1]["close"])
    daily=100*(close/points[-2]["close"]-1)
    weekly=100*(close/points[-6]["close"]-1)
    result={"close":close,"date":points[-1]["date"],"daily":daily,"weekly":weekly,
            "ma20":chart.get("ma20"),"ma50":chart.get("ma50"),"ma200":chart.get("ma200")}
    if (benchmark and len(benchmark)>=6 and
            benchmark[-1]["date"]==points[-1]["date"] and
            benchmark[-6]["date"]==points[-6]["date"]):
        result["sp500_weekly"]=100*(benchmark[-1]["close"]/benchmark[-6]["close"]-1)
        result["relative_weekly"]=weekly-result["sp500_weekly"]
    return result

def reading(p):
    if not p:return "Sin cierres recientes suficientes para inferir una dirección."
    daily=p["daily"];weekly=p["weekly"]
    if weekly>1 and daily>=0:
        base="Avanza en la semana y mantiene impulso en la última sesión."
    elif weekly>1 and daily<0:
        base="La semana es positiva, pero la última sesión retrocedió: posible pérdida de impulso."
    elif weekly< -1 and daily<=0:
        base="Cede en la semana y en la última sesión: presión vendedora reciente."
    elif weekly< -1 and daily>0:
        base="Semana negativa con rebote en la última sesión: rebote aún no confirma recuperación."
    else:
        base="Movimiento semanal limitado o mixto: todavía no aparece dirección concluyente."
    if p.get("ma20") and p.get("ma50"):
        if p["close"]>p["ma20"] and p["close"]>p["ma50"]:
            base+=" Sigue por encima de MA20 y MA50."
        elif p["close"]<p["ma20"] and p["close"]<p["ma50"]:
            base+=" Sigue por debajo de MA20 y MA50."
        else:
            base+=" Las medias MA20 y MA50 ofrecen señales mixtas."
    if "relative_weekly" in p:
        rel=p["relative_weekly"]
        base+=f" Frente al S&P 500, su desempeño semanal es {rel:+.1f} puntos porcentuales."
    return base

def scenarios(p):
    if not p:return "Sin cotizaciones verificables no se determina escenario."
    if p["weekly"]>1:
        return ("Continuación favorable si se mantiene sobre MA20 y conserva fuerza relativa; "
                "alerta si pierde esa referencia o vuelve a retroceder varias sesiones.")
    if p["weekly"]< -1:
        return ("Persistencia de debilidad mientras no recupere MA20; "
                "un rebote aislado no invalida el deterioro de la semana.")
    return ("Posible consolidación; un movimiento sostenido y confirmado por MA20 "
            "sería necesario para hablar de dirección más definida.")

def possible_news_impact(title,ticker):
    """Mecanismo sectorial plausible, no reacción de precio verificada."""
    t=title.casefold()
    if any(w in t for w in ("earnings","results","revenue","profit","guidance","outlook")):
        return ("Puede modificar las expectativas de ingresos y márgenes. Para determinar "
                "el efecto real faltan cifras, consenso y reacción del precio.")
    if any(w in t for w in ("chip","semiconductor","gpu","fab","ai infrastructure","data center")):
        return ("Podría afectar demanda, inversión o capacidad de producción de "
                "semiconductores e infraestructura de IA. No demuestra por sí solo "
                "cambios de beneficios ni explica una variación concreta.")
    if any(w in t for w in ("regulat","lawsuit","antitrust","investigation","tariff","export ban")):
        return ("Introduce posibles costes, restricciones o incertidumbre regulatoria. "
                "El efecto depende de su alcance y de si la noticia ya estaba descontada.")
    if any(w in t for w in ("launch","contract","order","partnership","customer","product")):
        return ("Podría modificar expectativas sobre ventas o posicionamiento competitivo; "
                "se necesita conocer el valor, calendario y rentabilidad del acuerdo.")
    if any(w in t for w in ("interest rate","fed","bond","inflation","bank")):
        return ("Podría repercutir en el coste del capital, crédito o valoración del sector. "
                "El impacto específico no está confirmado.")
    sectors={
        "NVDA":"Demanda de aceleradores de IA y márgenes",
        "MSFT":"Crecimiento de Azure, IA y gasto en infraestructura",
        "AAPL":"Ventas de dispositivos, servicios y márgenes",
        "AMZN":"AWS, comercio electrónico y margen operativo",
        "GOOGL":"Publicidad digital, nube y monetización de IA",
        "META":"Publicidad, uso de plataformas y gasto en IA",
        "AVGO":"Demanda de chips personalizados y conectividad",
        "JPM":"Crédito, tipos de interés y calidad de préstamos",
        "TSLA":"Entregas, precios, márgenes y competencia",
        "TSM":"Pedidos de fabricación avanzada y capacidad de producción",
        "SPCX":"Lanzamientos, contratos y necesidades de inversión",
    }
    return f"Vigilar {sectors.get(ticker,'beneficios y competencia').lower()}."

def company_news_html(items,translator=None,ticker=""):
    if not items:
        return '<p><strong>Noticias 7 días:</strong> No se obtuvieron titulares fechados para esta empresa; no se atribuye causa al precio.</p>'
    rows=[]
    for item in items[:2]:
        title=item.get("title","").strip()
        if not title:continue
        shown=title
        if translator:
            try:
                candidate=translator(title)
                if translation_is_usable(candidate):shown=candidate.strip()
            except (ImportError,ValueError,RuntimeError,OSError):
                pass
        url=item.get("url","")
        if not url.startswith("https://news.google.com/"):continue
        rows.append('<li><a href="'+e(url)+'">'+e(shown)+'</a>'
                    +' — '+e(item.get("source","Agregador"))+' ('+e(item.get("date",""))+')'
                    +'<p style="font-size:12px"><strong>Impacto potencial:</strong> '
                    +e(possible_news_impact(title,ticker))+'</p></li>')
    if not rows:
        return '<p>Sin noticias recientes con fuente y fecha verificables.</p>'
    return '<p><strong>Noticias de los últimos siete días:</strong></p><ul>'+''.join(rows)+'</ul>'
