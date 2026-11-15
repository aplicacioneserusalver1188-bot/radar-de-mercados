#!/usr/bin/env python3
"""Lectura macroeconómica explicativa, sin API de pago ni datos inventados."""
import html
from datetime import datetime, timezone

def e(x): return html.escape(str(x))
def pct(x): return f"{x:+.2f}%"
def last(series,key,max_days=None,now=None):
    item=series.get(key,{})
    points=item.get("points",[])
    if not points:return None
    p=points[-1]
    try:
        date=datetime.fromisoformat(p["date"]).date()
        age=((now or datetime.now(timezone.utc)).date()-date).days
        if age<0 or (max_days is not None and age>max_days):return None
    except (TypeError,ValueError,KeyError):
        return None
    return p
def prev(series,key):
    points=series.get(key,{}).get("points",[])
    if len(points)<2 or points[-2]["date"]>=points[-1]["date"]:return None
    return points[-2]
def year_change(series,key,now=None):
    x=last(series,key,75,now)
    if not x:return None
    prior=next((p for p in reversed(series[key]["points"][:-1])
                if p["date"][:7]==f"{int(x['date'][:4])-1}{x['date'][4:7]}"),None)
    if not prior or prior["value"]<=0:return None
    return 100*(x["value"]/prior["value"]-1)
def recent_percent_change(series,key,now=None):
    x=last(series,key,75,now)
    y=prev(series,key)
    if not x or not y or y["value"]<=0:return None
    return (x["value"]/y["value"]-1)*100
def story(title,summary,reason,signal,source=None):
    # Correo compatible con Gmail: diseño basado en tabla HTML simple y sin CSS externo
    link=(f' <a href="{e(source)}" style="font-size:12px">Fuente y serie</a>'
          if source and source.startswith("https://fred.stlouisfed.org/series/") else "")
    return ('<div style="border:1px solid #dce4ed;border-radius:10px;'
            'padding:15px;margin:14px 0;background:#fff">'
            f'<h3 style="margin:0 0 8px;font-size:17px">{e(title)}</h3>'
            f'<p style="margin:7px 0"><strong>Qué está pasando:</strong> {e(summary)}</p>'
            f'<p style="margin:7px 0"><strong>Por qué importa:</strong> {e(reason)}</p>'
            f'<p style="margin:7px 0"><strong>Lectura:</strong> {e(signal)}{link}</p></div>')
def source(series,key):
    return series.get(key,{}).get("source_url","")
def macro_story(data,now=None):
    s=data.get("series",{})
    cards=[]
    contradictions=[]
    # Inflación: el índice no es una tasa; la variación anual sí.
    pce=year_change(s,"pce",now)
    core=year_change(s,"corepce",now)
    if pce is not None or core is not None:
        pieces=[]
        if pce is not None:pieces.append(f"PCE general {pce:.2f}% interanual")
        if core is not None:pieces.append(f"PCE subyacente {core:.2f}% interanual")
        readings=[v for v in (pce,core) if v is not None]
        above=all(v>2 for v in readings)
        below=all(v<2 for v in readings)
        level=("ambas medidas superan el objetivo del 2%" if len(readings)==2 and above
               else "ambas medidas están por debajo del objetivo del 2%" if len(readings)==2 and below
               else "las señales de inflación no son uniformes" if len(readings)==2
               else "la lectura disponible se compara con el objetivo de la Fed")
        cards.append(story("Inflación y política monetaria",
            "; ".join(pieces)+f". {level.capitalize()}.",
            "Una inflación persistente suele limitar el margen para recortar tipos; "
            "las tasas elevadas pueden presionar la valoración de acciones de crecimiento y bonos. "
            "No se deduce la reacción de mercado sin consenso ni evolución temporal.",
            ("Presión inflacionaria aún relevante" if above else
             "Inflación bajo la referencia del 2%" if below else
             "Señal incompleta o mixta"),
            source(s,"pce") or source(s,"corepce")))
    else:
        cards.append(story("Inflación y política monetaria",
                           "Falta una comparación interanual reciente y verificable.",
                           "El nivel de un índice no equivale a su tasa anual.",
                           "No se emite diagnóstico de inflación."))
    # IPC general: índice de consumo; la tasa calculada es interanual.
    cpi=year_change(s,"inflation",now)
    if cpi is not None:
        cards.append(story("IPC: precios al consumidor",
            f"El índice de precios al consumidor varió {pct(cpi)} interanual.",
            "Es una medida amplia de inflación de los hogares. Un dato mayor de lo "
            "esperado podría elevar las expectativas de tipos, pero no se inventa "
            "una sorpresa de mercado sin previsiones verificadas.",
            ("IPC superior al 2%" if cpi>2 else "IPC igual o inferior al 2%; "
             "su trayectoria requiere varias lecturas"),
            source(s,"inflation")))
    ppi=year_change(s,"ppi",now)
    if ppi is not None:
        cards.append(story("Costes de producción: materias primas",
            f"El índice PPI de materias primas cambió {pct(ppi)} interanual.",
            "Refleja una parte de las presiones sobre costes industriales. No "
            "representa el PPI de demanda final ni la inflación pagada por consumidores.",
            ("Aumento de costes de materias primas" if ppi>0 else
             "Descenso de costes de materias primas"),
            source(s,"ppi")))
    # Mercado laboral: tasa y variación, nunca porcentaje incorrecto.
    un=last(s,"unemployment",75,now)
    prior_un=prev(s,"unemployment")
    payroll=last(s,"payrolls",75,now)
    prior_pay=prev(s,"payrolls")
    labor=[]
    if un:
        labor.append(f"desempleo {un['value']:.1f}% ({un['date']})")
        if prior_un:
            delta=un["value"]-prior_un["value"]
            labor.append(f"{delta:+.2f} puntos frente a la lectura anterior")
    if payroll and prior_pay:
        ym=lambda p:int(p["date"][:4])*12+int(p["date"][5:7])
        if ym(payroll)-ym(prior_pay)==1:
            jobs=(payroll["value"]-prior_pay["value"])*1000
            labor.append(f"empleo no agrícola {jobs:+,.0f} puestos frente al mes anterior")
    if labor:
        direction=("sube" if un and prior_un and un["value"]>prior_un["value"] else
                   "baja" if un and prior_un and un["value"]<prior_un["value"] else
                   "sin dirección clara")
        cards.append(story("Empleo y riesgo de desaceleración",
            "; ".join(labor)+".",
            "Un debilitamiento sostenido del empleo puede perjudicar beneficios empresariales "
            "y modificar las expectativas de recortes de tipos. Un dato aislado no establece recesión.",
            f"Desempleo: {direction}; contrastar con empleo creado y solicitudes semanales.",
            source(s,"unemployment")))
    # Tipos y curva; datos fechados idénticamente.
    two=last(s,"treasury2y",7,now)
    ten=last(s,"treasury10y",7,now)
    fed=last(s,"fedfunds",45,now)
    bond=[]
    if ten:bond.append(f"bono a 10 años {ten['value']:.2f}% ({ten['date']})")
    if two:bond.append(f"bono a 2 años {two['value']:.2f}% ({two['date']})")
    if fed:bond.append(f"límite superior Fed {fed['value']:.2f}%")
    if bond:
        spread=None
        if two and ten and two["date"]==ten["date"]:
            spread=ten["value"]-two["value"]
        reading=(f"Curva 10–2 años: {spread:+.2f} puntos; "
                 +("invertida, factor histórico de cautela" if spread<0 else
                   "no invertida, sin garantizar expansión")
                 if spread is not None else
                 "Sin fechas simultáneas para calcular una curva confiable")
        cards.append(story("Bonos y coste del dinero","; ".join(bond)+".",
            "Los rendimientos condicionan el coste de financiarse y el descuento de "
            "beneficios futuros. Su dirección importa tanto como su nivel.",
            reading,source(s,"treasury10y")))
    # Crédito y volatilidad: diagnóstico conjunto.
    credit=last(s,"credit",7,now)
    credit_prev=prev(s,"credit")
    vix=last(s,"vix",7,now)
    if credit or vix:
        parts=[]
        stress=[]
        if credit:
            parts.append(f"diferencial de alto rendimiento {credit['value']:.2f} puntos")
            if credit_prev:
                delta=credit["value"]-credit_prev["value"]
                stress.append("crédito se encarece" if delta>0 else
                              "prima de riesgo se reduce" if delta<0 else
                              "prima de riesgo estable")
        if vix:
            parts.append(f"VIX {vix['value']:.1f}")
            stress.append("volatilidad alta" if vix["value"]>=25 else
                          "volatilidad moderada" if vix["value"]<20 else
                          "volatilidad intermedia")
        cards.append(story("Riesgo: crédito y volatilidad",
            "; ".join(parts)+".",
            "La ampliación de diferenciales junto con volatilidad elevada puede señalar "
            "tensión financiera. Una sola variable no confirma una caída bursátil.",
            "; ".join(stress),source(s,"credit")))
    # Actividad: sólo porcentajes calculados desde niveles comparables.
    retail=recent_percent_change(s,"retail",now)
    gdp=recent_percent_change(s,"gdp",now)
    activity=[]
    if retail is not None:activity.append(f"ventas minoristas {pct(retail)} entre lecturas")
    if gdp is not None:activity.append(f"PIB real {pct(gdp)} entre trimestres disponibles (sin anualizar)")
    if activity:
        cards.append(story("Actividad económica y consumo",
            "; ".join(activity)+".",
            "Un crecimiento sostenido puede apoyar ingresos empresariales, mientras una contracción "
            "reiterada puede debilitar beneficios; estos cambios no son sorpresas de consenso.",
            "Señales de actividad, no previsión automática del próximo trimestre.",
            source(s,"retail") or source(s,"gdp")))
    if pce is not None and pce>2 and un and prior_un and un["value"]>prior_un["value"]:
        contradictions.append("Inflación por encima del 2% y desempleo en aumento: posible tensión entre control de precios y crecimiento.")
    if not cards:
        return '<p>No hay información macroeconómica comparable reciente para emitir diagnóstico.</p>'
    close=(" ".join(contradictions) if contradictions else
           "Las lecturas son de fechas y frecuencias distintas: no representan una reacción simultánea del mercado.")
    close+=" El movimiento de acciones debe comprobarse con precios y amplitud bursátil, no inferirse de una sola cifra."
    return ('<p>Interpretación de indicadores verificados. Cada ficha distingue hechos, '
            'posibles mecanismos económicos y límites de la conclusión.</p>'
            +"".join(cards)+
            '<p style="padding:12px;border-left:4px solid #425b82;background:#f1f5fa">'
            '<strong>Diagnóstico integrado:</strong> '+e(close)+'</p>')
