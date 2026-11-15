#!/usr/bin/env python3
"""Resúmenes periodísticos en español basados EXCLUSIVAMENTE en comunicados oficiales."""
import json, os, urllib.request

MODEL = "gemini-3.5-flash-lite"

def summarize_news(news, api_key=None):
    """Una sola petición para evitar cuotas y costes inesperados. Nunca inventar contenido."""
    key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")
    if not key or not news:
        return {}
    entries = [
        {"id":i,"titulo":title[:280],"fuente":source[:100],"descripcion_original":description[:1100]}
        for i, (title,source,description) in enumerate(news)
    ]
    instruction = (
        "Eres editor de economía. Devuelve JSON array de objetos {id,resumen_es}. "
        "Redacta para cada elemento 2 frases en español claro que resuman los hechos "
        "QUE ESTÁN EXPLÍCITAMENTE CONTENIDOS en título y descripción original. "
        "No inventes cifras, decisiones, fechas, pronósticos, reacciones bursátiles, "
        "ni causas que la fuente no mencione. Si título y descripción no permiten "
        "saber qué ocurrió, escribe exactamente 'La fuente no aporta detalles suficientes "
        "para resumir el hecho; consultar el comunicado original.' "
        "No escribas instrucciones al lector ni expresiones especulativas. "
        "Entrada: " + json.dumps(entries,ensure_ascii=False)
    )
    body=json.dumps({"contents":[{"parts":[{"text":instruction}]}],
                     "generationConfig":{"responseMimeType":"application/json",
                                         "maxOutputTokens":1800,"temperature":0.1}}).encode()
    request=urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/"+MODEL+":generateContent",
        data=body,headers={"Content-Type":"application/json","x-goog-api-key":key},
        method="POST")
    with urllib.request.urlopen(request,timeout=25) as response:
        payload=json.loads(response.read(200000))
    text="".join(part.get("text","") for part in payload["candidates"][0]["content"]["parts"])
    parsed=json.loads(text)
    if not isinstance(parsed,list): raise ValueError("respuesta Gemini inválida")
    valid={}
    for entry in parsed:
        if isinstance(entry,dict) and type(entry.get("id")) is int and isinstance(entry.get("resumen_es"),str):
            i=entry["id"]
            if 0<=i<len(news) and 30<=len(entry["resumen_es"])<=900:
                valid[i]=entry["resumen_es"].strip()
    return valid
