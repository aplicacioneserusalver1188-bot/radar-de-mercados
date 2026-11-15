#!/usr/bin/env python3
"""Gráficos PNG incrustables en Gmail (CID): sin URLs de imágenes de terceros."""
import math
import pathlib
from datetime import datetime,timezone
from update_price_history import COMPANIES

ROOT=pathlib.Path(__file__).resolve().parents[1]
CHART_DIR=ROOT/"reports"/"charts"
COLORS={"up":"#087e64","down":"#bd4141","flat":"#4c6278"}

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
    return description+" Son señales técnicas, no predicciones."

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
        color=COLORS["up"] if "change20" in view and view["change20"]>=0 else COLORS["down"]
        ax.plot(dates[-90:],values[-90:],color=color,linewidth=2.3,label="Precio/cierre")
        for term,shade in ((20,"#3d78a8"),(50,"#b08037"),(200,"#7467a8")):
            if len(values)>=term+25:
                cumulative=[sum(values[i-term+1:i+1])/term
                            for i in range(len(values)-90,len(values)) if i>=term-1]
                xs=dates[max(len(values)-90,term-1):]
                if len(xs)==len(cumulative):
                    ax.plot(xs,cumulative,color=shade,linewidth=1.1,alpha=.85,label=f"MA{term}")
        ax.grid(axis="y",color="#e7ebf0",linewidth=.7)
        ax.spines[["top","right","left"]].set_visible(False)
        ax.tick_params(axis="both",labelsize=8,length=0,pad=8)
        ax.legend(loc="upper left",fontsize=7,ncol=4,frameon=False)
        ax.set_title(obj.get("label",key)+" — últimos cierres disponibles",loc="left",fontsize=11,pad=12)
        fig.autofmt_xdate(rotation=0)
        fig.tight_layout()
        path=CHART_DIR/(key.lower()+".png")
        fig.savefig(path,format="png",facecolor="white",bbox_inches="tight")
        plt.close(fig)
        generated[key]=path
    return generated
