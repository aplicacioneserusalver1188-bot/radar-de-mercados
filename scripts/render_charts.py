#!/usr/bin/env python3
"""Gráficos PNG incrustables en Gmail (CID): sin URLs de imágenes de terceros."""
import math
import pathlib
from datetime import datetime,timezone
from update_price_history import COMPANIES

ROOT=pathlib.Path(__file__).resolve().parents[1]
CHART_DIR=ROOT/"reports"/"charts"
COLORS={"up":"#087e64","down":"#bd4141","flat":"#4c6278"}
# Paleta fija en todos los activos: la leyenda coincide con cada trazo.
LINE_COLORS={"price":"#000000","ma20":"#0066cc","ma50":"#dc2626","ma200":"#15803d"}

def metrics(points,now=None):
    """Medias móviles simples sobre cierres, sin extrapolar datos."""
    if not points:
        return {}
    now=now or datetime.now(timezone.utc)
    latest=points[-1]
    day=datetime.fromisoformat(latest["date"]).date()
    age=(now.date()-day).days
    if age<0 or age>7:
        return {"stale":True,"date":latest["date"]}
    values=[float(x["close"]) for x in points]
    if any(not math.isfinite(v) or v<=0 for v in values):
        return {}
    output={"date":latest["date"],"close":values[-1],"stale":False}
    for term in (20,50,200):
        if len(values)>=term:
            output["ma"+str(term)]=sum(values[-term:])/term
    if len(values)>=21:
        output["change20"]=100*(values[-1]/values[-21]-1)
    return output

def interpretation(data):
    if not data or data.get("stale"):
        return "No hay cierres recientes suficientes para evaluar la tendencia."
    above=[data["close"]>data["ma"+str(n)] for n in (20,50) if "ma"+str(n) in data]
    if len(above)<2:
        return "Información insuficiente para confirmar la tendencia mediante medias móviles."
    if all(above):
        description="El precio está sobre sus medias de 20 y 50 sesiones: impulso de corto y mediano plazo favorable."
    elif not any(above):
        description="El precio está bajo sus medias de 20 y 50 sesiones: tendencia reciente débil."
    else:
        description="El precio ofrece señales mixtas frente a las medias de 20 y 50 sesiones."
    if "ma200" in data:
        description+=(" También supera la media de 200 sesiones."
                      if data["close"]>data["ma200"] else
                      " Permanece por debajo de la media de 200 sesiones.")
    return description

def build_charts(history):
    """Genera PNG solo para series recientes y completas. Otros se omiten."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    CHART_DIR.mkdir(parents=True,exist_ok=True)
    generated={}
    for key,obj in history.get("assets",{}).items():
        points=obj.get("points",[])
        view=metrics(points)
        if not view or view.get("stale") or len(points)<20:
            continue
        values=[float(p["close"]) for p in points]
        dates=[datetime.fromisoformat(p["date"]) for p in points]
        fig,ax=plt.subplots(figsize=(7.2,2.9),dpi=110)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        shown=points[-90:]
        shown_dates=dates[-90:]
        # Las velas se dibujan solamente cuando la fuente entregó OHLC
        # completo. La línea de cierres se conserva negra por consistencia.
        has_ohlc=all(all(name in point for name in ("open","high","low","close")) for point in shown)
        if has_ohlc:
            import matplotlib.dates as mdates
            xs=mdates.date2num(shown_dates)
            for x,point in zip(xs,shown):
                opening,high,low,closing=(float(point[name]) for name in ("open","high","low","close"))
                color="#15803d" if closing>=opening else "#dc2626"
                ax.vlines(x,low,high,color=color,linewidth=.75,zorder=1)
                ax.bar(x,abs(closing-opening) or max(high-low,1)*.015,bottom=min(opening,closing),
                       width=.62,color=color,edgecolor=color,linewidth=.4,zorder=2)
        ax.plot(shown_dates,values[-90:],color=LINE_COLORS["price"],linewidth=1.05,
                alpha=.88,label="Cierre",zorder=3)
        for term in (20,50,200):
            if len(values)>=term+25:
                cumulative=[sum(values[i-term+1:i+1])/term
                            for i in range(len(values)-90,len(values)) if i>=term-1]
                xs=dates[max(len(values)-90,term-1):]
                if len(xs)==len(cumulative):
                    ax.plot(xs,cumulative,color=LINE_COLORS["ma"+str(term)],linewidth=1.3,alpha=.95,label=f"MA{term}")
        ax.grid(axis="y",color="#e7ebf0",linewidth=.7)
        ax.spines[["top","right","left"]].set_visible(False)
        ax.tick_params(axis="both",labelsize=8,length=0,pad=8)
        ax.legend(loc="upper left",fontsize=7,ncol=4,frameon=False)
        title="velas diarias y cierres" if has_ohlc else "últimos cierres disponibles"
        ax.set_title(obj.get("label",key)+" — "+title,loc="left",fontsize=11,pad=12)
        fig.autofmt_xdate(rotation=0)
        fig.tight_layout()
        path=CHART_DIR/(key.lower()+".png")
        fig.savefig(path,format="png",facecolor="white",bbox_inches="tight")
        plt.close(fig)
        generated[key]=path
    return generated

def build_macro_charts(data, keys=None):
    """Gráficos simples de las series macro: muestran observaciones, no velas ficticias."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    CHART_DIR.mkdir(parents=True,exist_ok=True)
    generated={}
    series=data.get("series",{})
    selected=keys if keys is not None else series.keys()
    for key in selected:
        obj=series.get(key,{})
        points=[]
        for point in obj.get("points",[]):
            try:
                day=datetime.fromisoformat(point["date"])
                value=float(point["value"])
                if math.isfinite(value):
                    points.append((day,value))
            except (KeyError,TypeError,ValueError):
                continue
        if len(points)<2:
            continue
        dates,values=zip(*points[-48:])
        fig,ax=plt.subplots(figsize=(5.6,2.2),dpi=105)
        fig.patch.set_facecolor("white"); ax.set_facecolor("white")
        ax.plot(dates,values,color="#1f4e79",linewidth=2.1,marker="o",markersize=2.2)
        ax.fill_between(dates,values,min(values),color="#1f4e79",alpha=.08)
        ax.grid(axis="y",color="#e7ebf0",linewidth=.7)
        ax.spines[["top","right","left"]].set_visible(False)
        ax.tick_params(axis="both",labelsize=7,length=0,pad=6)
        ax.set_title(obj.get("label",key)+" — observaciones publicadas",loc="left",fontsize=9,pad=9)
        fig.autofmt_xdate(rotation=0); fig.tight_layout()
        path=CHART_DIR/("macro_"+key.lower()+".png")
        fig.savefig(path,format="png",facecolor="white",bbox_inches="tight")
        plt.close(fig); generated["macro_"+key]=path
    return generated
