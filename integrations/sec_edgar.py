"""Consultas públicas SEC EDGAR, módulo independiente (no modifica el radar existente)."""
import json
import os
import time
import urllib.request

BASE = "https://data.sec.gov"
AGENT = os.environ.get("SEC_USER_AGENT", "").strip()
CACHE_SECONDS = 3600
_cache = {}

def _get(path):
    if not AGENT or "@" not in AGENT:
        raise RuntimeError("Configure SEC_USER_AGENT con nombre y correo de contacto.")
    now = time.monotonic()
    entry = _cache.get(path)
    if entry and now - entry[0] < CACHE_SECONDS:
        return entry[1]
    request = urllib.request.Request(
        BASE + path,
        headers={"User-Agent": AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)
    _cache[path] = (now, data)
    return data

def company_facts(cik):
    """Devuelve hechos XBRL reales de SEC para un CIK numérico."""
    cik = str(cik)
    if not cik.isdecimal() or len(cik) > 10:
        raise ValueError("CIK inválido")
    return _get(f"/api/xbrl/companyfacts/CIK{int(cik):010d}.json")

def submissions(cik):
    """Devuelve el historial de presentaciones de una empresa."""
    cik = str(cik)
    if not cik.isdecimal() or len(cik) > 10:
        raise ValueError("CIK inválido")
    return _get(f"/submissions/CIK{int(cik):010d}.json")
