#!/usr/bin/env python3
"""Traducción local del contenido de feeds oficiales; sin API ni clave de pago.

No genera análisis nuevo: únicamente traduce un extracto literal del comunicado.
"""
import re

def factual_extract(description, max_chars=560):
    """Dos primeras frases completas de la descripción institucional, sin añadir hechos."""
    original=" ".join((description or "").split())
    if not original:
        return ""
    if len(original) > max_chars:
        clip=original[:max_chars]
        ending=max(clip.rfind(". "),clip.rfind("; "),clip.rfind("! "),clip.rfind("? "))
        if ending>100:
            original=clip[:ending+1]
        else:
            original=clip.rsplit(" ",1)[0]
    sentences=re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])",original)
    return " ".join(sentences[:2]).strip()

def local_translation(text):
    """Usa modelo en-es instalado por el flujo de CI; ninguna llamada a servicio de pago."""
    if not text:
        return ""
    from argostranslate import translate
    result=translate.translate(text,"en","es")
    if not result or not result.strip():
        raise ValueError("traducción vacía")
    return result.strip()

def local_news(news, translate_fn=None):
    """Devuelve título y resumen basados solo en fuente, o vacío ante fallo."""
    translate_fn=translate_fn or local_translation
    results={}
    for i,(title,agency,description) in enumerate(news):
        excerpt=factual_extract(description)
        if not excerpt or len(excerpt)<35:
            continue
        try:
            title_es=translate_fn(title)
            summary_es=translate_fn(excerpt)
            if not title_es or not summary_es:
                continue
            results[i]={"title_es":title_es[:300],"summary_es":summary_es[:1000]}
        except (ImportError,ValueError,RuntimeError,OSError) as error:
            print("Traductor local no disponible:",type(error).__name__)
            break
    return results
